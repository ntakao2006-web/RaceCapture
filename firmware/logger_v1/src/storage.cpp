#include "driver/sdmmc_host.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_random.h"
#include "esp_vfs_fat.h"
#include "sdmmc_cmd.h"
#include "state.h"
#include <cerrno>
#include <cstdio>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

namespace logger {
static const char *TAG = "storage";
static sdmmc_card_t *card = nullptr;
static bool mountCard() {
    sdmmc_host_t host = SDMMC_HOST_DEFAULT();
    host.max_freq_khz = SDMMC_FREQ_HIGHSPEED;
    sdmmc_slot_config_t slot = SDMMC_SLOT_CONFIG_DEFAULT();
    slot.width = 4;
    slot.clk = GPIO_NUM_11;
    slot.cmd = GPIO_NUM_10;
    slot.d0 = GPIO_NUM_12;
    slot.d1 = GPIO_NUM_13;
    slot.d2 = GPIO_NUM_14;
    slot.d3 = GPIO_NUM_21;
    slot.flags |= SDMMC_SLOT_FLAG_INTERNAL_PULLUP;
    esp_vfs_fat_sdmmc_mount_config_t cfg = {};
    cfg.format_if_mount_failed = false;
    cfg.max_files = 6;
    cfg.allocation_unit_size = 32768;
    esp_err_t e = esp_vfs_fat_sdmmc_mount("/sdcard", &host, &slot, &cfg, &card);
    if (e != ESP_OK) {
        ESP_LOGE(TAG, "SD mount: %s (will retry; NEVER format)", esp_err_to_name(e));
        card = nullptr;
        return false;
    }
    if (mkdir("/sdcard/logs", 0775) != 0 && errno != EEXIST) {
        esp_vfs_fat_sdcard_unmount("/sdcard", card);
        card = nullptr;
        return false;
    }
    return true;
}
static QueueHandle_t makeQueue(size_t length, size_t item) {
    auto *control = static_cast<StaticQueue_t *>(
        heap_caps_malloc(sizeof(StaticQueue_t), MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT));
    auto *memory = static_cast<uint8_t *>(
        heap_caps_malloc(length * item, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    ESP_ERROR_CHECK(control && memory ? ESP_OK : ESP_ERR_NO_MEM);
    QueueHandle_t q = xQueueCreateStatic(length, item, memory, control);
    ESP_ERROR_CHECK(q ? ESP_OK : ESP_ERR_NO_MEM);
    return q;
}
static FILE *exclusiveFile(const char *path) {
    int fd = open(path, O_WRONLY | O_CREAT | O_EXCL, 0666);
    if (fd < 0)
        return nullptr;
    FILE *f = fdopen(fd, "w");
    if (!f)
        close(fd);
    return f;
}
static bool syncFile(FILE *f) { return f && fflush(f) == 0 && fsync(fileno(f)) == 0; }
static bool writeSnapshot(FILE *f, const Snapshot &s, const Channel *meta, size_t count) {
    if (fprintf(f, "%llu,", static_cast<unsigned long long>(s.us)) < 0)
        return false;
    if (s.utc_us && fprintf(f, "%lld", static_cast<long long>(s.utc_us)) < 0)
        return false;
    for (size_t i = 0; i < count; ++i) {
        if (fputc(',', f) == EOF)
            return false;
        if (s.has(i) && fprintf(f, "%.*f", int(meta[i].precision), s.values[i]) < 0)
            return false;
    }
    return fputc('\n', f) != EOF;
}
static bool writeCan(FILE *f, const CanFrame &c) {
    if (fprintf(f, "%llu,%u,%s,%08lX,%u,%u,%u,", static_cast<unsigned long long>(c.us), c.bus,
                c.tx ? "TX_REQ" : "RX", static_cast<unsigned long>(c.id), c.extended ? 1 : 0,
                c.rtr ? 1 : 0, c.dlc) < 0)
        return false;
    if (!c.rtr)
        for (unsigned i = 0; i < c.dlc; ++i)
            if (fprintf(f, "%02X", c.data[i]) < 0)
                return false;
    return fputc('\n', f) != EOF;
}
static void storageTask(void *) {
    auto *meta = static_cast<Channel *>(
        heap_caps_malloc(sizeof(Channel) * MAX_CHANNELS, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    auto *csv_buffer =
        static_cast<char *>(heap_caps_malloc(32768, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    auto *can_buffer =
        static_cast<char *>(heap_caps_malloc(32768, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    ESP_ERROR_CHECK(meta && csv_buffer && can_buffer ? ESP_OK : ESP_ERR_NO_MEM);
    uint32_t boot = esp_random(), segment = 0, revision = 0;
    size_t count = 0;
    FILE *csv = nullptr, *raw = nullptr;
    uint64_t last_sync = 0, last_space = 0;
    bool ok = true;
    Snapshot sample;
    CanFrame frame;
    auto closeFiles = [&]() {
        bool result = true;
        if (csv) {
            result = syncFile(csv) && result;
            result = (fclose(csv) == 0) && result;
            csv = nullptr;
        }
        if (raw) {
            result = syncFile(raw) && result;
            result = (fclose(raw) == 0) && result;
            raw = nullptr;
        }
        return result;
    };
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(2));
        persistBestLap();
        Guard sd_lock(sd_mutex);
        if (!card) {
            if (!mountCard()) {
                stats.sd_ok = false;
                ++stats.sd_errors;
                vTaskDelay(pdMS_TO_TICKS(3000));
                continue;
            }
            stats.sd_ok = true;
        }
        if (!stats.logging) {
            if (!closeFiles()) {
                ++stats.sd_errors;
                stats.sd_ok = false;
                ESP_LOGE(TAG, "SD close/sync failed while stopping; files retained");
                esp_vfs_fat_sdcard_unmount("/sdcard", card);
                card = nullptr;
            }
            {
                Guard lock(state_mutex);
                session_path[0] = 0;
            }
            while (xQueueReceive(log_queue, &sample, 0) == pdTRUE) {
            }
            while (xQueueReceive(can_log_queue, &frame, 0) == pdTRUE) {
            }
            vTaskDelay(pdMS_TO_TICKS(20));
            continue;
        }
        uint32_t current_revision;
        {
            Guard lock(state_mutex);
            current_revision = schema_revision;
        }
        if (!csv || revision != current_revision || stats.rotate.exchange(false)) {
            if (!closeFiles()) {
                ok = false;
            }
            {
                Guard lock(state_mutex);
                count = channel_count;
                revision = schema_revision;
                memcpy(meta, channels.data(), count * sizeof(Channel));
            }
            char base[96], path[128], raw_path[128];
            snprintf(base, sizeof(base), "/sdcard/logs/L%08lX_%04lu",
                     static_cast<unsigned long>(boot), static_cast<unsigned long>(segment++));
            snprintf(path, sizeof(path), "%s.csv", base);
            snprintf(raw_path, sizeof(raw_path), "%s_can.csv", base);
            csv = exclusiveFile(path);
            raw = exclusiveFile(raw_path);
            ok = ok && csv && raw;
            if (ok) {
                setvbuf(csv, csv_buffer, _IOFBF, 32768);
                setvbuf(raw, can_buffer, _IOFBF, 32768);
                ok = fprintf(csv, "monotonic_us,utc_us") > 0;
                for (size_t i = 0; i < count && ok; ++i)
                    ok = fprintf(csv, ",%s", meta[i].name) > 0;
                ok = ok && fputc('\n', csv) != EOF &&
                     fprintf(raw, "monotonic_us,bus,direction,id,extended,rtr,dlc,data\n") > 0;
                ok = ok && syncFile(csv) && syncFile(raw);
                if (ok) {
                    Guard lock(state_mutex);
                    snprintf(session_path, sizeof(session_path), "%s", path);
                }
                ESP_LOGI(TAG, "SD session %s: %u channels, schema %lu", path, unsigned(count),
                         static_cast<unsigned long>(revision));
            }
            last_sync = nowUs();
        }
        for (unsigned i = 0; i < 32 && ok && xQueueReceive(log_queue, &sample, 0) == pdTRUE; ++i) {
            if (sample.revision != revision) {
                ++stats.log_drop;
                continue;
            }
            ok = writeSnapshot(csv, sample, meta, count);
            if (ok)
                ++stats.rows;
            else
                ++stats.log_drop;
        }
        for (unsigned i = 0; i < 256 && ok && xQueueReceive(can_log_queue, &frame, 0) == pdTRUE;
             ++i) {
            ok = writeCan(raw, frame);
            if (ok)
                ++stats.raw_rows;
            else
                ++stats.can_drop;
        }
        uint64_t now = nowUs();
        if (ok && now - last_sync >= 500000) {
            ok = syncFile(csv) && syncFile(raw);
            if (ok)
                ++stats.syncs;
            last_sync = now;
        }
        if (ok && now - last_space >= 1000000) {
            uint64_t total_bytes = 0, free_bytes = 0;
            if (esp_vfs_fat_info("/sdcard", &total_bytes, &free_bytes) != ESP_OK ||
                free_bytes < 2 * 1024 * 1024) {
                ok = false;
                errno = ENOSPC;
            }
            struct stat info = {};
            if (fstat(fileno(csv), &info) == 0 && info.st_size > 256 * 1024 * 1024)
                stats.rotate = true;
            if (fstat(fileno(raw), &info) == 0 && info.st_size > 256 * 1024 * 1024)
                stats.rotate = true;
            last_space = now;
        }
        stats.sd_ok = ok;
        if (!ok) {
            ++stats.sd_errors;
            ESP_LOGE(TAG, "SD write/sync/space failure errno=%d; existing files retained", errno);
            closeFiles();
            esp_vfs_fat_sdcard_unmount("/sdcard", card);
            card = nullptr;
            ok = true;
            vTaskDelay(pdMS_TO_TICKS(3000));
        }
    }
}
void startStorage() {
    sd_mutex = xSemaphoreCreateMutex();
    ESP_ERROR_CHECK(sd_mutex ? ESP_OK : ESP_ERR_NO_MEM);
    log_queue = makeQueue(512, sizeof(Snapshot));
    can_log_queue = makeQueue(8192, sizeof(CanFrame));
    lua_can_queue = makeQueue(1024, sizeof(CanFrame));
    // Acquisition/sampling (priority 5) must preempt CSV formatting and SD I/O.
    // A writer above them can otherwise skip a 40 ms GNSS epoch in the snapshot log.
    ESP_ERROR_CHECK(xTaskCreate(storageTask, "sd_logger", 8192, nullptr, 4, nullptr) == pdPASS
                        ? ESP_OK
                        : ESP_ERR_NO_MEM);
}
} // namespace logger
