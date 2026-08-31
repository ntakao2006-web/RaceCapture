#include "state.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "nvs.h"
#include <new>

namespace logger {
struct StoredLap {
    uint32_t version = 1, count = 0;
    Track track{};
    double seconds = 0;
    std::array<LapPoint, LapEngine::CAPACITY> points{};
};
static StoredLap *scratch = nullptr;
static StoredLap *buffer() {
    if (!scratch) {
        void *p = heap_caps_malloc(sizeof(StoredLap), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
        if (p)
            scratch = new (p) StoredLap{};
    }
    return scratch;
}
void loadBestLap() {
    auto *saved = buffer();
    if (!saved)
        return;
    nvs_handle_t h;
    if (nvs_open_from_partition("loggercfg", "logger_v1", NVS_READONLY, &h) != ESP_OK)
        return;
    size_t n = sizeof(StoredLap);
    bool ok = nvs_get_blob(h, "best_lap", saved, &n) == ESP_OK && n == sizeof(StoredLap);
    nvs_close(h);
    if (!ok || saved->version != 1 || !(saved->track == config.track) || saved->count < 2 ||
        saved->count > LapEngine::CAPACITY || !std::isfinite(saved->seconds) ||
        saved->seconds < config.track.min_lap_s)
        return;
    for (size_t i = 0; i < saved->count; ++i) {
        const auto &p = saved->points[i];
        if (!std::isfinite(p.metres) || !std::isfinite(p.seconds) || p.metres < 0 ||
            p.seconds < 0 ||
            (i &&
             (p.metres < saved->points[i - 1].metres || p.seconds < saved->points[i - 1].seconds)))
            return;
    }
    laps->best = saved->points;
    laps->best_count = saved->count;
    laps->best_s = saved->seconds;
}
void persistBestLap() {
    auto *saved = buffer();
    if (!saved)
        return;
    {
        Guard lock(state_mutex);
        if (!laps->best_changed)
            return;
        saved->version = 1;
        saved->track = laps->track;
        saved->seconds = laps->best_s;
        saved->count = laps->best_count;
        saved->points = laps->best;
        laps->best_changed = false;
    }
    nvs_handle_t h;
    bool ok = nvs_open_from_partition("loggercfg", "logger_v1", NVS_READWRITE, &h) == ESP_OK;
    if (ok) {
        ok = nvs_set_blob(h, "best_lap", saved, sizeof(StoredLap)) == ESP_OK &&
             nvs_commit(h) == ESP_OK;
        nvs_close(h);
    }
    if (!ok)
        ESP_LOGE("laps", "Best lap persistence failed; RAM lap retained");
}
} // namespace logger
