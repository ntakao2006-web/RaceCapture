#pragma once
#include <cstdio>
#include <cstdint>
#include <ctime>

namespace logger {
inline constexpr const char *LOGGER_BUILD = "logger-v1-ecocapture-20260901k";
// Absolute time is optional. Never invent a date before GNSS resolves UTC.
inline void logBaseName(char *out, size_t size, uint32_t boot, uint32_t segment,
                        int64_t boot_utc_us) {
    char date[32]{};
    if (boot_utc_us >= 1577836800000000LL && boot_utc_us < 4102444800000000LL) {
        time_t jst = time_t(boot_utc_us / 1000000 + 9 * 3600);
        tm calendar{};
        if (gmtime_r(&jst, &calendar))
            strftime(date, sizeof(date), "%Y%m%d_%H%M%S_JST_", &calendar);
    }
    snprintf(out, size, "%sL%08lX_%04lu", date,
             static_cast<unsigned long>(boot), static_cast<unsigned long>(segment));
}
} // namespace logger
