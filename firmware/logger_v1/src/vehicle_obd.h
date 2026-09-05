#pragma once
#include "core.h"

namespace logger {
// Separate NVS key: never change the binary layout of the existing Config blob.
struct VehicleAcquisition {
    uint32_t version = 1;
    uint8_t obd_enabled = 0, toyota_steering = 0;
    uint8_t reserved[2]{};
};
inline bool validAcquisition(const VehicleAcquisition &c) {
    return c.version == 1 && c.obd_enabled <= 1 && c.toyota_steering <= 1 &&
           c.reserved[0] == 0 && c.reserved[1] == 0;
}
struct ObdValue { uint8_t pid = 0; double value = 0; };
inline bool obdSingleFrame(const CanFrame &f) {
    return f.bus == 1 && !f.tx && !f.rtr && !f.extended && f.id >= 0x7e8 && f.id <= 0x7ef &&
           f.dlc >= 4 && f.dlc <= 8 && f.data[0] >= 3 && f.data[0] <= 7 && f.data[0] + 1 <= f.dlc;
}
inline bool decodeObd(const CanFrame &f, ObdValue &out) {
    if (!obdSingleFrame(f) || f.data[1] != 0x41) return false;
    const unsigned a = f.data[3], b = f.data[4];
    out.pid = f.data[2];
    switch (out.pid) {
    case 0x0c: if (f.data[0] < 4) return false; out.value = (a * 256 + b) / 4.0; break;
    case 0x0d: out.value = a; break;
    case 0x05: case 0x0f: case 0x5c: out.value = int(a) - 40; break;
    case 0x04: case 0x11: out.value = a * 100.0 / 255; break;
    case 0x42: if (f.data[0] < 4) return false; out.value = (a * 256 + b) / 1000.0; break;
    default: return false;
    }
    return true;
}
// opendbc Toyota STEER_ANGLE_SENSOR (0x025), signed angle + signed fraction.
// DBC Motorola start bits 3/39 translate to linear network offsets 4/32.
// Read only. Not the EPS command and not STEER_RATE (whose factor is TBD).
inline bool decodeToyotaSteering(const CanFrame &f, double &angle) {
    if (f.bus != 1 || f.tx || f.rtr || f.extended || f.id != 0x25 || f.dlc != 8) return false;
    double whole, fraction;
    if (!extract(f, 4, 12, false, true, 1.5, 0, whole) ||
        !extract(f, 32, 4, false, true, .1, 0, fraction) || fraction == -.8) return false;
    angle = whole + fraction;
    return std::abs(angle) <= 500; // Published signal range; reject sentinel/outliers.
}

// Hardware-independent bounded scheduler. All times in monotonic microseconds.
// Only Mode 01, 11-bit Classical CAN. No DTC clear, UDS, actuation or session changes.
class ObdPoller {
  public:
    struct Pid { uint8_t id; uint32_t period_ms; };
    inline static constexpr std::array<Pid, 8> pids{{
        {0x0c,250}, {0x0d,500}, {0x11,1000}, {0x04,1000},
        {0x05,2000}, {0x0f,2000}, {0x42,2000}, {0x5c,3000}}};
    uint32_t sent = 0, responses = 0, timeouts = 0, negative = 0, tx_errors = 0;
    uint32_t request_id = 0x7e0, response_id = 0;
    uint8_t supported = 0;
    bool discovering = true;
    void reset(uint64_t now) {
        *this = ObdPoller{}; next_ = now + 1000000;
    }
    bool next(uint64_t now, CanFrame &request) {
        if (waiting_ && now >= deadline_) { ++timeouts; fail(now); }
        if (waiting_ || now < next_) return false;
        if (discovering) pending_pid_ = uint8_t(page_ * 0x20);
        else {
            bool found = false;
            for (size_t n = 0; n < pids.size(); ++n) {
                const size_t i = (cursor_ + n) % pids.size();
                if ((supported & (1U << i)) && now >= due_[i]) {
                    slot_ = i; cursor_ = (i + 1) % pids.size(); pending_pid_ = pids[i].id;
                    found = true; break;
                }
            }
            if (!found) return false;
        }
        request = CanFrame{}; request.bus = 1; request.tx = true; request.us = now;
        request.id = request_id; request.dlc = 8;
        request.data[0] = 2; request.data[1] = 1; request.data[2] = pending_pid_;
        waiting_ = true; deadline_ = now + 250000; next_ = now + 100000;
        return true;
    }
    void queued() { ++sent; } // Accepted by driver, NOT proof of CAN ACK/ECU reply.
    void txFailed(uint64_t now) { ++tx_errors; fail(now); next_ = std::max(next_, now + 1000000); }
    bool receive(const CanFrame &f, ObdValue &value) {
        if (!waiting_ || f.us >= deadline_ || !obdSingleFrame(f)) return false;
        if (response_id ? f.id != response_id : request_id != 0x7df && f.id != request_id + 8)
            return false;
        if (f.data[1] == 0x7f && f.data[2] == 1) { ++negative; fail(f.us); return false; }
        if (f.data[1] != 0x41 || f.data[2] != pending_pid_) return false;
        if (discovering) {
            if (f.data[0] != 6) return false;
            const uint32_t bits = (uint32_t(f.data[3]) << 24) | (uint32_t(f.data[4]) << 16) |
                                  (uint32_t(f.data[5]) << 8) | f.data[6];
            // Functional discovery selects an ECU advertising engine RPM, not an unrelated ECU.
            if (page_ == 0 && !(bits & (1U << (32 - 0x0c)))) return false;
            response_id = f.id;
            // Some Toyota/Lexus OBD gateways answer functional discovery on
            // 0x7DF but do not route the corresponding physical request ID.
            // Keep using 0x7DF after functional discovery while accepting
            // replies only from the ECU which advertised engine RPM.
            if (request_id != 0x7df) request_id = f.id - 8;
            for (size_t i = 0; i < pids.size(); ++i) {
                const int bit = int(pids[i].id) - int(page_ * 32);
                if (bit >= 1 && bit <= 32 && (bits & (1U << (32 - bit)))) supported |= 1U << i;
            }
            ++responses; waiting_ = false; misses_ = attempts_ = 0;
            if (page_ < 2 && (bits & 1)) ++page_;
            else discovering = false;
            return false;
        }
        if (!decodeObd(f, value)) return false;
        ++responses; waiting_ = false; misses_ = 0; failures_[slot_] = 0;
        due_[slot_] = f.us + uint64_t(pids[slot_].period_ms) * 1000;
        return true;
    }
  private:
    bool waiting_ = false;
    uint8_t page_ = 0, pending_pid_ = 0, attempts_ = 0, misses_ = 0;
    size_t slot_ = 0, cursor_ = 0;
    uint64_t next_ = 0, deadline_ = 0;
    std::array<uint64_t, 8> due_{};
    std::array<uint8_t, 8> failures_{};
    void fail(uint64_t now) {
        waiting_ = false;
        if (discovering) {
            if (++attempts_ < 3) { next_ = now + 500000; return; }
            attempts_ = 0;
            if (page_ != 0) { discovering = false; return; } // Keep known supported lower pages.
            if (request_id != 0x7df) { request_id = 0x7df; next_ = now + 500000; }
            else { request_id = 0x7e0; next_ = now + 5000000; }
        } else {
            failures_[slot_] = std::min<unsigned>(5, failures_[slot_] + 1);
            due_[slot_] = now + std::min<uint64_t>(30000000, uint64_t(pids[slot_].period_ms) *
                                                  1000 * (1U << failures_[slot_]));
            if (++misses_ >= 12) {
                discovering = true; page_ = 0; response_id = 0; request_id = 0x7e0;
                supported = 0; attempts_ = misses_ = 0; next_ = now + 5000000;
            }
        }
    }
};
} // namespace logger
