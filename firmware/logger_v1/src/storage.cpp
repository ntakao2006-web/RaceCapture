#include "driver/sdmmc_host.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_random.h"
#include "esp_vfs_fat.h"
#include "sdmmc_cmd.h"
#include "state.h"
#include "log_format.h"
#include "esp_app_desc.h"
#include <ArduinoJson.h>
#include <string>
#include <cerrno>
#include <cstdio>
#include <fcntl.h>
#include <dirent.h>
#include <sys/stat.h>
#include <unistd.h>

namespace logger {
SemaphoreHandle_t capture_mutex = nullptr;
void requestLogging(bool enabled, bool eject) {
    Guard sd(sd_mutex);
    Guard capture(capture_mutex);
    if (!enabled && stats.sd_ready)
        return; // Retrying stop/eject must not remount an already removed card.
    stats.sd_ready = false;
    stats.sd_closed = false;
    stats.sd_eject = !enabled && eject;
    stats.logging = enabled;
}
void queueCanLog(const CanFrame &frame) {
    Guard capture(capture_mutex);
    if (stats.logging && xQueueSend(can_log_queue, &frame, 0) != pdTRUE)
        ++stats.can_drop;
}
static const char *TAG = "storage";
static sdmmc_card_t *card = nullptr;
// No client-supplied path: maintenance is confined to this mounted SD card.
static bool visitSd(const char *path, unsigned depth, bool erase, SdContents &report) {
    if (depth > 8) {
        snprintf(report.error, sizeof(report.error), "Directory depth exceeded: %s", path);
        return false;
    }
    DIR *dir = opendir(path);
    if (!dir) {
        snprintf(report.error, sizeof(report.error), "Cannot open directory: %s", path);
        return false;
    }
    bool ok = true;
    while (ok) {
        errno = 0;
        dirent *entry = readdir(dir);
        if (!entry) {
            if (errno) {
                snprintf(report.error, sizeof(report.error), "Cannot enumerate: %s", path);
                ok = false;
            }
            break;
        }
        const char *name = entry->d_name;
        if (!strcmp(name, ".") || !strcmp(name, ".."))
            continue;
        char child[256];
        int length = snprintf(child, sizeof(child), "%s/%s", path, name);
        struct stat info{};
        if (!name[0] || strchr(name, '/') || strchr(name, '\\') || strchr(name, ':') ||
            length < 0 || size_t(length) >= sizeof(child) || stat(child, &info) != 0) {
            snprintf(report.error, sizeof(report.error), "Invalid/unreadable entry in: %s", path);
            ok = false;
        } else if (S_ISDIR(info.st_mode)) {
            ok = visitSd(child, depth + 1, erase, report);
            if (ok && erase)
                ok = rmdir(child) == 0;
            if (ok)
                ++report.directories;
        } else if (S_ISREG(info.st_mode)) {
            if (erase)
                ok = unlink(child) == 0;
            if (ok) {
                ++report.files;
                report.bytes += uint64_t(info.st_size);
            }
        } else {
            ok = false;
        }
        if (!ok && !report.error[0])
            snprintf(report.error, sizeof(report.error), "Unsupported entry or removal failed: %s", child);
        vTaskDelay(pdMS_TO_TICKS(1));
    }
    if (closedir(dir) != 0 && ok) {
        snprintf(report.error, sizeof(report.error), "Cannot close directory: %s", path);
        ok = false;
    }
    return ok;
}
bool maintainSdContents(bool erase, SdContents &report) {
    Guard sd(sd_mutex);
    report = SdContents{};
    if (!card || !stats.sd_ok || stats.logging || !stats.sd_closed || stats.sd_ready ||
        uxQueueMessagesWaiting(log_queue) || uxQueueMessagesWaiting(can_log_queue)) {
        snprintf(report.error, sizeof(report.error), "Stop logging and wait for closed=true; SD must remain mounted");
        return false;
    }
    // Preflight the complete tree before deleting anything. Never format media.
    if (!visitSd("/sdcard", 0, false, report) || !erase)
        return !report.error[0];
    report = SdContents{};
    if (!visitSd("/sdcard", 0, true, report))
        return false;
    SdContents remaining;
    if (!visitSd("/sdcard", 0, false, remaining) || remaining.files || remaining.directories) {
        snprintf(report.error, sizeof(report.error), "SD is not confirmed empty after removal");
        return false;
    }
    if (mkdir("/sdcard/logs", 0775) != 0) {
        snprintf(report.error, sizeof(report.error), "Cannot recreate empty logs directory");
        return false;
    }
    return true;
}
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
static bool writeJsonFile(const char *path, JsonDocument &doc) {
    FILE *f = exclusiveFile(path);
    if (!f)
        return false;
    std::string text;
    serializeJson(doc, text);
    bool ok = !doc.overflowed() && fwrite(text.data(), 1, text.size(), f) == text.size();
    ok = syncFile(f) && ok;
    return fclose(f) == 0 && ok;
}
static bool writeMetadata(const char *base, uint32_t boot, uint32_t segment, int64_t boot_utc,
                          uint32_t revision, const Channel *meta, size_t count) {
    JsonDocument doc;
    doc["format"] = "logger_v1_csv_v1";
    doc["firmware"] = LOGGER_BUILD;
    doc["reset_reason"] = resetReasonName();
    char hash[65]{};
    const auto *app = esp_app_get_description();
    for (size_t i = 0; i < 32; ++i)
        snprintf(hash + 2 * i, 3, "%02x", app->app_elf_sha256[i]);
    doc["app_elf_sha256"] = hash;
    doc["boot_id"] = boot;
    doc["segment"] = segment;
    if (boot_utc)
        doc["estimated_boot_utc_us"] = boot_utc;
    doc["filename_timezone"] = "JST (UTC+09:00)";
    doc["schema"] = revision;
    doc["csv_row_hz"] = 100;
    {
        Guard lock(state_mutex);
        auto g = doc["gnss_at_file_open"].to<JsonObject>();
        g["verified"] = gnss_diagnostics.configuration_verified;
        if (gnss_diagnostics.profile_index < GNSS_PROFILES.size()) {
            const auto &p = GNSS_PROFILES[gnss_diagnostics.profile_index];
            g["profileId"] = p.id;
            g["systems"] = p.systems;
            g["periodMs"] = p.period_ms;
        }
    }
    doc["missing"] = "empty field; never replace with zero";
    {
        Guard lock(state_mutex);
        doc["vehicle_acquisition_at_file_open"]["obdEnabled"] = bool(vehicle_acquisition.obd_enabled);
        doc["vehicle_acquisition_at_file_open"]["toyotaSteering"] = bool(vehicle_acquisition.toyota_steering);
    }
    doc["vehicle_note"] = "Speed is CAN/OBD only; GPSSpeed is GNSS. SteeringAngle uses Toyota 0x025, verify on vehicle. Zero RPM can be valid hybrid engine-off data.";
    doc["time_note"] = "monotonic_us: since boot; utc_us: estimated Unix UTC microseconds; GPSUTC: GNSS fix Unix seconds; UTC may be unavailable";
    doc["sampling_note"] = "100Hz snapshots hold the last valid slower channel; use GPSTow to identify new GNSS fixes";
    auto level = doc["imu_level_correction"].to<JsonObject>();
    {
        Guard lock(state_mutex);
        level["enabled"] = level_calibration.enabled != 0;
        level["rollZeroDeg"] = level_calibration.roll_zero_deg;
        level["pitchZeroDeg"] = level_calibration.pitch_zero_deg;
        auto matrix = level["matrixSensorToVehicle"].to<JsonArray>();
        for (double value : level_calibration.matrix) matrix.add(value);
    }
    level["formula"] = "[LongAccel,LatAccel,VertAccel]^T = M * [GForceX,GForceY,GForceZ]^T";
    level["attitudeFormula"] = "LevelRoll/Pitch = wrap180(raw Roll/Pitch - captured zero)";
    level["capture"] = "stationary vehicle on the user-defined horizontal surface; forward axis projected perpendicular to measured gravity";
    doc["imu_axes"] = "Raw channels use BNO055 sensor axes; corrected channels use the matrix above";
    doc["imu_calibration"] = "IMUCal per row; 255 means fully calibrated";
    doc["shutdown_note"] = "Only a matching end.json confirms clean closure; no power-loss guarantee";
    doc["can_note"] = "Companion _can.csv; RX or TX_REQ, bus 1/2, monotonic receive-processing time";
    auto cols = doc["columns"].to<JsonArray>();
    for (const char *name : {"monotonic_us", "utc_us"}) {
        auto c = cols.add<JsonObject>();
        c["name"] = name;
        c["unit"] = "us";
    }
    for (size_t i = 0; i < count; ++i) {
        auto c = cols.add<JsonObject>();
        c["name"] = meta[i].name;
        c["unit"] = meta[i].unit;
        c["precision"] = meta[i].precision;
        c["nominal_hz"] = meta[i].rate;
        c["stale_ms"] = meta[i].stale_ms;
    }
    char path[128];
    snprintf(path, sizeof(path), "%s.meta.json", base);
    return writeJsonFile(path, doc);
}
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
    int64_t boot_utc = 0;
    char base[96]{};
    uint32_t start_rows = 0, start_raw = 0;
    size_t count = 0;
    FILE *csv = nullptr, *raw = nullptr;
    uint64_t last_sync = 0, last_space = 0;
    bool ok = true;
    bool stop_failed = false;
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
        if (base[0] && result && ok) {
            JsonDocument end;
            end["clean_close"] = true;
            end["boot_id"] = boot;
            end["rows"] = stats.rows.load() - start_rows;
            end["can_rows"] = stats.raw_rows.load() - start_raw;
            end["closed_monotonic_us"] = nowUs();
            if (boot_utc)
                end["estimated_boot_utc_us"] = boot_utc;
            end["cumulative_log_drops"] = stats.log_drop.load();
            end["cumulative_can_drops"] = stats.can_drop.load();
            end["cumulative_sd_errors"] = stats.sd_errors.load();
            char path[128];
            snprintf(path, sizeof(path), "%s.end.json", base);
            result = writeJsonFile(path, end);
        }
        base[0] = 0;
        return result;
    };
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(2));
        persistBestLap();
        Guard sd_lock(sd_mutex);
        if (stats.logging)
            stop_failed = false;
        if (!stats.logging && stop_failed) {
            vTaskDelay(pdMS_TO_TICKS(20));
            continue;
        }
        if (stats.sd_ready) {
            vTaskDelay(pdMS_TO_TICKS(20));
            continue;
        }
        if (!card) {
            if (!mountCard()) {
                stats.sd_ok = false;
                ++stats.sd_errors;
                vTaskDelay(pdMS_TO_TICKS(3000));
                continue;
            }
            stats.sd_ok = true;
        }
        if (!stats.logging && uxQueueMessagesWaiting(log_queue) == 0 &&
            uxQueueMessagesWaiting(can_log_queue) == 0) {
            if (!closeFiles()) {
                ++stats.sd_errors;
                stats.sd_ok = false;
                ESP_LOGE(TAG, "SD close/sync failed while stopping; files retained");
                esp_vfs_fat_sdcard_unmount("/sdcard", card);
                card = nullptr;
                // Never report safe removal after a failed flush/close.
                stats.sd_closed = false;
                stop_failed = true;
                vTaskDelay(pdMS_TO_TICKS(3000));
                continue;
            }
            {
                Guard lock(state_mutex);
                session_path[0] = 0;
            }
            stats.sd_closed = true;
            if (stats.sd_eject && card) {
                if (esp_vfs_fat_sdcard_unmount("/sdcard", card) == ESP_OK) {
                    card = nullptr;
                    stats.sd_ok = false;
                    stats.sd_ready = true;
                } else {
                    ++stats.sd_errors;
                }
            }
            vTaskDelay(pdMS_TO_TICKS(20));
            continue;
        }
        uint32_t current_revision;
        bool time_resolved = false;
        {
            Guard lock(state_mutex);
            current_revision = schema_revision;
            if (!boot_utc && fresh(nowUs(), utc_updated, 2000) &&
                utc_offset >= 1577836800000000LL && utc_offset < 4102444800000000LL) {
                boot_utc = utc_offset;
                time_resolved = true;
            }
        }
        if (!csv || revision != current_revision || time_resolved || stats.rotate.exchange(false)) {
            if (!closeFiles()) {
                ok = false;
            }
            {
                Guard lock(state_mutex);
                count = channel_count;
                revision = schema_revision;
                memcpy(meta, channels.data(), count * sizeof(Channel));
            }
            char name[80], path[128], raw_path[128];
            uint32_t file_segment = segment++;
            logBaseName(name, sizeof(name), boot, file_segment, boot_utc);
            snprintf(base, sizeof(base), "/sdcard/logs/%s", name);
            start_rows = stats.rows;
            start_raw = stats.raw_rows;
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
                ok = ok && writeMetadata(base, boot, file_segment, boot_utc, revision, meta, count);
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
            // Definitions are append-only (GNSS changes rates, never units or
            // order). Preserve queued samples across a metadata revision;
            // newly appended columns correctly become empty via Snapshot::has.
            if (sample.count > count) {
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
            if (!stats.logging)
                stop_failed = true;
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
    capture_mutex = xSemaphoreCreateMutex();
    ESP_ERROR_CHECK(sd_mutex && capture_mutex ? ESP_OK : ESP_ERR_NO_MEM);
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
