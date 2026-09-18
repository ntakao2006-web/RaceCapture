#include "ncec.h"
#include "state.h"
#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "driver/twai.h"
#include "esp_log.h"

namespace logger {
static spi_device_handle_t mcp = nullptr, led = nullptr;
static const char *TAG = "can";
static FanProbe fan;
static ObdPoller obd; // CAN1 task owns the scheduler; CAN2 never accesses it.
static bool transact(const uint8_t *tx, uint8_t *rx, size_t size) {
    spi_transaction_t t = {};
    t.length = size * 8;
    t.tx_buffer = tx;
    t.rx_buffer = rx;
    return spi_device_polling_transmit(mcp, &t) == ESP_OK;
}
static bool readMany(uint8_t reg, uint8_t *data, size_t n) {
    uint8_t tx[32] = {3, reg}, rx[32] = {};
    if (n > 30 || !transact(tx, rx, n + 2))
        return false;
    memcpy(data, rx + 2, n);
    return true;
}
static uint8_t readReg(uint8_t reg) {
    uint8_t v = 255;
    readMany(reg, &v, 1);
    return v;
}
static bool writeMany(uint8_t reg, const uint8_t *data, size_t n) {
    uint8_t tx[32] = {2, reg};
    if (n > 30)
        return false;
    memcpy(tx + 2, data, n);
    return transact(tx, nullptr, n + 2);
}
static bool writeReg(uint8_t reg, uint8_t value) { return writeMany(reg, &value, 1); }
static bool modify(uint8_t reg, uint8_t mask, uint8_t value) {
    uint8_t tx[] = {5, reg, mask, value};
    return transact(tx, nullptr, sizeof(tx));
}
static bool mode(uint8_t value) {
    if (!modify(0x0f, 0xe0, value))
        return false;
    for (unsigned i = 0; i < 50; ++i) {
        if ((readReg(0x0e) & 0xe0) == value)
            return true;
        vTaskDelay(pdMS_TO_TICKS(2));
    }
    return false;
}
static bool initMcp() {
    gpio_set_level(GPIO_NUM_4, 0);
    vTaskDelay(pdMS_TO_TICKS(10));
    gpio_set_level(GPIO_NUM_4, 1);
    vTaskDelay(pdMS_TO_TICKS(10));
    uint8_t reset = 0xc0;
    transact(&reset, nullptr, 1);
    vTaskDelay(pdMS_TO_TICKS(10));
    if ((readReg(0x0e) & 0xe0) != 0x80)
        return false;
    const uint8_t timing[] = {0x03, 0xb7, 0x80}; // CNF3..1, 20MHz/500kbps, sample 80%
    bool ok = writeMany(0x28, timing, 3) && writeReg(0x60, 0x64) &&
              writeReg(0x70, 0x60) && // accept all, rollover
              writeReg(0x2b, 0x23) && writeReg(0x2c, 0) && modify(0x0f, 0x08, 0x08) && mode(0);
    return ok;
}
static void writeLed(uint8_t bits) {
    spi_transaction_t t = {};
    t.length = 8;
    t.tx_buffer = &bits;
    if (spi_device_acquire_bus(led, portMAX_DELAY) != ESP_OK)
        return;
    if (spi_device_polling_transmit(led, &t) == ESP_OK) {
        gpio_set_level(GPIO_NUM_45, 1);
        gpio_set_level(GPIO_NUM_45, 0);
    }
    spi_device_release_bus(led);
}
void onCan(const CanFrame &f) {
    if (stats.bench_status == 1 && !f.extended && !f.rtr && f.id == 0x6ef && f.dlc == 8 &&
        !memcmp(f.data, "LGRTEST", 7)) {
        if (f.bus == 1)
            ++stats.bench_vehicle_rx;
        else if (f.bus == 2)
            ++stats.bench_hub_rx;
    }
    if (f.bus == 1)
        ++stats.can1_rx;
    else
        ++stats.can2_rx;
    queueCanLog(f);
    if (xQueueSend(lua_can_queue, &f, 0) != pdTRUE)
        ++stats.lua_drop;
    Guard lock(state_mutex);
    for (const auto &m : config.mappings)
        if (m.enabled && m.bus == f.bus && m.id == f.id && m.extended == f.extended) {
            double value;
            if (extract(f, m.bit, m.width, m.little, m.signed_value, m.scale, m.offset, value)) {
                if (m.channel < channel_count) {
                    channels[m.channel].stale_ms = m.stale_ms;
                    putChannel(m.channel, value, f.us);
                }
            }
        }
    if (f.bus != 1 || f.rtr || f.extended)
        return;
    static NcDecoder nc;
    if (config.nc_profile && !vehicle_acquisition.toyota_steering) {
        static constexpr unsigned target[] = {RPM, SPEED, WATER_TEMP, THROTTLE, INTAKE_TEMP,
            WHEEL_FL, WHEEL_FR, WHEEL_RL, WHEEL_RR, ACCEL_PEDAL, ACCEL_PEDAL_BACKUP,
            BRAKE_PEDAL, AC_REQUEST, CLUTCH_DISENGAGED, WATER_TEMP_BACKUP, FUEL_LEVEL_RAW,
            PARKING_BRAKE, FUEL_LEVEL};
        nc.decode(f.id, f.data, f.dlc, f.us, [&](NcSignal signal, double value) {
            putChannel(target[signal], value, f.us);
        });
    } else nc.reset();
    double angle;
    if (vehicle_acquisition.toyota_steering && decodeToyotaSteering(f, angle)) {
        ++stats.steering_rx;
        putChannel(STEERING_ANGLE, angle, f.us);
    }
    fan.receive(f);
    ObdValue value;
    const bool accepted = vehicle_acquisition.obd_enabled
        ? !stats.obd_fault && obd.receive(f, value) : decodeObd(f, value);
    if (accepted) {
        unsigned channel = RPM;
        switch (value.pid) {
        case 0x0c: channel = RPM; break;
        case 0x0d: channel = SPEED; break;
        case 0x05: channel = WATER_TEMP; break;
        case 0x04: channel = ENGINE_LOAD; break;
        case 0x11: channel = THROTTLE; break;
        case 0x0f: channel = INTAKE_TEMP; break;
        case 0x42: channel = BATT_VOLT; break;
        case 0x5c: channel = OIL_TEMP; break;
        }
        // Native NCEC values keep their full precision and rate while OBD fills extra channels.
        if (config.nc_profile && !vehicle_acquisition.toyota_steering &&
            (channel == RPM || channel == SPEED || channel == WATER_TEMP || channel == THROTTLE || channel == INTAKE_TEMP)) return;
        channels[channel].stale_ms = channel == RPM || channel == SPEED ? 1500 : 6500;
        putChannel(channel, value.value, f.us); // Zero RPM is valid in EV/idle-stop operation.
    }
}
static bool sendObdRequest(const CanFrame &frame) {
    if (!allowedObdRequest(frame)) return false;
    twai_message_t request = {};
    request.identifier = frame.id;
    request.data_length_code = 8;
    request.ss = 1; // Single shot: no automatic retransmit storm on an unacknowledged bus.
    memcpy(request.data, frame.data, 8);
    return twai_transmit(&request, 0) == ESP_OK;
}
static void can1Task(void *) {
    twai_general_config_t g =
        TWAI_GENERAL_CONFIG_DEFAULT(GPIO_NUM_2, GPIO_NUM_1, TWAI_MODE_LISTEN_ONLY);
    g.rx_queue_len = 256;
    g.tx_queue_len = 1;
    g.intr_flags = ESP_INTR_FLAG_IRAM;
    twai_timing_config_t t = TWAI_TIMING_CONFIG_500KBITS();
    twai_filter_config_t f = TWAI_FILTER_CONFIG_ACCEPT_ALL();
    if (twai_driver_install(&g, &t, &f) != ESP_OK || twai_start() != ESP_OK) {
        ++stats.can1_errors;
        vTaskDelete(nullptr);
        return;
    }
    stats.can1_ok = true;
    stats.vehicle_listen_only = true;
    ESP_LOGI(TAG, "CAN1 ATA6561 J5: 500k; saved acquisition setting follows");
    uint64_t last = 0, last_request = 0;
    uint32_t revision = UINT32_MAX;
    uint32_t driver_errors = 0;
    obd.reset(nowUs()); fan.reset(nowUs());
    while (true) {
        bool enabled;
        {
            Guard lock(state_mutex);
            enabled = vehicle_acquisition.obd_enabled;
            if (revision != stats.acquisition_revision.load()) {
                revision = stats.acquisition_revision;
                stats.obd_fault = false;
                obd.reset(nowUs()); fan.reset(nowUs());
            }
        }
        const bool active = enabled && !stats.obd_fault;
        const auto desired = active ? TWAI_MODE_NORMAL : TWAI_MODE_LISTEN_ONLY;
        if (g.mode != desired) {
            twai_status_info_t state{};
            const bool known = twai_get_status_info(&state) == ESP_OK;
            const bool stopped = known && (state.state != TWAI_STATE_RUNNING || twai_stop() == ESP_OK);
            if (!stopped || twai_driver_uninstall() != ESP_OK) {
                stats.can1_ok = false;
                stats.bench_status = 3;
                gpio_set_direction(GPIO_NUM_2, GPIO_MODE_INPUT);
                vTaskDelete(nullptr);
                return;
            }
            g.mode = desired;
            if (twai_driver_install(&g, &t, &f) != ESP_OK || twai_start() != ESP_OK) {
                stats.can1_ok = false;
                stats.bench_status = 3;
                gpio_set_direction(GPIO_NUM_2, GPIO_MODE_INPUT);
                vTaskDelete(nullptr);
                return;
            }
            stats.vehicle_listen_only = !active;
            driver_errors = 0;
        }
        uint64_t now = nowUs();
        if (enabled && !stats.obd_fault) {
            CanFrame request;
            if (now-last_request>=100000 && !fan.busy(now)) {
                const bool probe=config.nc_profile && !vehicle_acquisition.toyota_steering && obd.idle() && fan.next(now,request);
                if (probe || obd.next(now, request)) {
                    last_request=now;
                    if (sendObdRequest(request)) { if(probe)++fan.sent;else obd.queued(); queueCanLog(request); }
                    else { if(probe)fan.failed(now);else obd.txFailed(now); }
                }
            }
        }
        twai_message_t msg = {};
        if (twai_receive(&msg, pdMS_TO_TICKS(10)) == ESP_OK) {
            CanFrame frame;
            frame.us = nowUs();
            frame.id = msg.identifier;
            frame.dlc = std::min<uint8_t>(msg.data_length_code, 8);
            frame.bus = 1;
            frame.extended = msg.extd;
            frame.rtr = msg.rtr;
            if (!frame.rtr)
                memcpy(frame.data, msg.data, frame.dlc);
            onCan(frame);
        }
        if (nowUs() - last > 100000) {
            twai_status_info_t s = {};
            if (twai_get_status_info(&s) == ESP_OK) {
                const uint32_t errors = s.bus_error_count + s.rx_overrun_count + s.rx_missed_count;
                stats.can1_errors += errors - driver_errors;
                driver_errors = errors;
                stats.can1_ok = s.state == TWAI_STATE_RUNNING;
                if (s.state == TWAI_STATE_BUS_OFF || (enabled &&
                    (s.tx_error_counter >= 96 || s.rx_error_counter >= 96))) {
                    stats.obd_fault = true; // No unattended recovery/retry on a vehicle bus.
                    ESP_LOGE(TAG, "OBD stopped: CAN error threshold; explicit re-enable required");
                }
            }
            stats.obd_sent = obd.sent+fan.sent; stats.obd_responses = obd.responses+fan.responses;
            for(unsigned i=0;i<2;++i) { stats.fan_raw[i]=fan.raw[i]; stats.fan_updated_ms[i]=fan.updated[i]/1000; }
            stats.fan_responses=fan.responses; stats.fan_timeouts=fan.timeouts; stats.fan_negative=fan.negative;
            stats.obd_request_id = obd.request_id; stats.obd_response_id = obd.response_id;
            stats.obd_timeouts = obd.timeouts; stats.obd_negative = obd.negative;
            stats.obd_tx_errors = obd.tx_errors; stats.obd_supported = obd.supported;
            stats.obd_discovering = obd.discovering;
            last = nowUs();
        }
    }
}
static bool receiveMcp(unsigned buffer) {
    uint8_t data[14];
    uint8_t base = buffer ? 0x70 : 0x60;
    if (!readMany(base, data, sizeof(data)))
        return false;
    CanFrame frame;
    frame.us = nowUs();
    frame.bus = 2;
    frame.extended = data[2] & 8;
    frame.id = (unsigned(data[1]) << 3) | (data[2] >> 5);
    if (frame.extended)
        frame.id =
            (frame.id << 18) | (unsigned(data[2] & 3) << 16) | (unsigned(data[3]) << 8) | data[4];
    frame.dlc = std::min<uint8_t>(data[5] & 15, 8);
    frame.rtr = data[0] & 8;
    if (!frame.rtr)
        memcpy(frame.data, data + 6, frame.dlc);
    if (!modify(0x2c, uint8_t(1U << buffer), 0))
        return false;
    onCan(frame);
    return true;
}
static bool transmitMcp(const CanFrame &f) {
    if (readReg(0x30) & 8)
        return false;
    uint8_t data[13] = {uint8_t(f.id >> 3), uint8_t((f.id & 7) << 5), 0, 0, f.dlc};
    memcpy(data + 5, f.data, f.dlc);
    if (!writeReg(0x30, 0) || !writeMany(0x31, data, sizeof(data)))
        return false;
    uint8_t rts = 0x81;
    return transact(&rts, nullptr, 1);
}
static void can2Task(void *) {
    gpio_set_direction(GPIO_NUM_4, GPIO_MODE_OUTPUT);
    gpio_set_direction(GPIO_NUM_45, GPIO_MODE_OUTPUT);
    gpio_set_level(GPIO_NUM_45, 0);
    gpio_set_direction(GPIO_NUM_47, GPIO_MODE_INPUT);
    spi_bus_config_t bus = {};
    bus.mosi_io_num = 40;
    bus.miso_io_num = 41;
    bus.sclk_io_num = 39;
    bus.quadwp_io_num = bus.quadhd_io_num = -1;
    bus.data4_io_num = bus.data5_io_num = bus.data6_io_num = bus.data7_io_num = -1;
    bus.max_transfer_sz = 64;
    ESP_ERROR_CHECK(spi_bus_initialize(SPI2_HOST, &bus, SPI_DMA_DISABLED));
    spi_device_interface_config_t dev = {};
    dev.clock_speed_hz = 5000000;
    dev.mode = 0;
    dev.spics_io_num = 42;
    dev.queue_size = 1;
    ESP_ERROR_CHECK(spi_bus_add_device(SPI2_HOST, &dev, &mcp));
    dev.spics_io_num = -1;
    dev.clock_speed_hz = 1000000;
    ESP_ERROR_CHECK(spi_bus_add_device(SPI2_HOST, &dev, &led));
    bool ready = false;
    uint64_t health = 0, led_time = 0, last_round = 0, next_tx = 0;
    size_t channel = 0;
    Snapshot outgoing;
    bool tx_pending = false;
    unsigned bench_stage = 0;
    uint64_t bench_time = 0;
    while (true) {
        uint64_t now = nowUs();
        if (!ready) {
            ready = initMcp();
            stats.can2_ok = ready;
            if (!ready) {
                ++stats.can2_errors;
                writeLed(3);
                vTaskDelay(pdMS_TO_TICKS(1000));
                continue;
            }
            ESP_LOGI(TAG, "CAN2 MCP25625 J4: 500k, 20MHz crystal, LEDs share SPI safely");
        }
        if (gpio_get_level(GPIO_NUM_47) == 0) {
            uint8_t flags = readReg(0x2c);
            for (unsigned i = 0; i < 2; ++i)
                if (flags & (1U << i))
                    if (!receiveMcp(i))
                        ++stats.can2_errors;
        }
        if (now - health >= 100000) {
            uint8_t errors = readReg(0x2d);
            if (errors & 0xc0) {
                ++stats.can_drop;
                modify(0x2d, 0xc0, 0);
            }
            if (errors & 0x20) {
                ++stats.can2_errors;
                ready = false;
            }
            modify(0x2c, 0x20, 0);
            health = now;
        }
        if (tx_pending && !(readReg(0x30) & 8)) {
            uint8_t ctrl = readReg(0x30);
            if (ctrl & 0x70)
                ++stats.hub_tx_errors;
            else
                ++stats.hub_tx;
            tx_pending = false;
        }
        // Explicit desk-only check: MCP internal loopback then one one-shot external frame.
        // Vehicle TWAI enables ACK only during this explicit, bounded desk test.
        if (stats.bench_request.exchange(false) && bench_stage == 0) {
            stats.bench_vehicle_rx = 0;
            stats.bench_hub_rx = 0;
            stats.bench_status = 1;
            bench_time = now;
            bench_stage = 1;
            writeReg(0x0f, 0x48);
        }
        auto benchFrame = [&]() {
            CanFrame f;
            f.us = now;
            f.bus = 2;
            f.tx = true;
            f.id = 0x6ef;
            f.dlc = 8;
            memcpy(f.data, "LGRTEST", 7);
            f.data[7] = 1;
            bool sent = transmitMcp(f);
            if (sent)
                queueCanLog(f);
            return sent;
        };
        if (bench_stage == 1 && now - bench_time > 10000 && !stats.vehicle_listen_only) {
            if ((readReg(0x0e) & 0xe0) == 0x40 && benchFrame()) {
                bench_stage = 2;
                bench_time = now;
            } else {
                writeReg(0x0f, 0x08);
                stats.bench_status = 3;
                bench_stage = 0;
            }
        } else if (bench_stage == 2 && now - bench_time > 50000) {
            writeReg(0x0f, 0x08);
            bench_stage = 3;
            bench_time = now;
        } else if (bench_stage == 3 && now - bench_time > 10000) {
            if ((readReg(0x0e) & 0xe0) == 0 && benchFrame()) {
                bench_stage = 4;
                bench_time = now;
            } else {
                stats.bench_status = 3;
                bench_stage = 0;
            }
        } else if (bench_stage == 4 && now - bench_time > 100000) {
            stats.bench_status = stats.bench_vehicle_rx > 0 && stats.bench_hub_rx > 0 ? 2 : 3;
            bench_stage = 0;
        }
        if (bench_stage && now - bench_time > 500000) {
            writeReg(0x0f, 0x08);
            stats.bench_status = 3;
            bench_stage = 0;
        }
        bool broadcast;
        unsigned hz, base;
        {
            Guard lock(state_mutex);
            broadcast = config.hub_broadcast;
            hz = config.broadcast_hz;
            base = config.broadcast_base;
        }
        if (broadcast && bench_stage == 0 && now >= next_tx && !tx_pending) {
            if (channel >= outgoing.count && now - last_round >= 1000000 / hz) {
                outgoing = takeSnapshot();
                channel = 0;
                last_round = now;
            }
            if (channel < outgoing.count) {
                CanFrame frame;
                frame.bus = 2;
                frame.tx = true;
                frame.us = now;
                frame.id = base + channel;
                frame.dlc = 8;
                frame.data[0] = 1;
                frame.data[1] = uint8_t(channel);
                frame.data[2] = outgoing.has(channel) ? 1 : 0;
                frame.data[3] = uint8_t(outgoing.revision);
                float v = outgoing.has(channel) ? float(outgoing.values[channel]) : 0;
                if (!std::isfinite(v)) {
                    frame.data[2] = 0;
                    v = 0;
                }
                uint32_t bits;
                memcpy(&bits, &v, 4);
                put32(frame.data + 4, bits);
                if (transmitMcp(frame)) {
                    tx_pending = true;
                    queueCanLog(frame);
                } else
                    ++stats.hub_tx_errors;
                ++channel;
                next_tx = now + 2000; // hard cap: 500 frames/s
            }
        }
        if (now - led_time >= 50000) {
            writeLed(uint8_t(stats.led_bits.load()));
            led_time = now;
        }
        vTaskDelay(pdMS_TO_TICKS(1));
    }
}
void startCan() {
    ESP_ERROR_CHECK(xTaskCreate(can1Task, "vehicle_can", 6144, nullptr, 7, nullptr) == pdPASS
                        ? ESP_OK
                        : ESP_ERR_NO_MEM);
    ESP_ERROR_CHECK(xTaskCreate(can2Task, "hub_can_led", 8192, nullptr, 7, nullptr) == pdPASS
                        ? ESP_OK
                        : ESP_ERR_NO_MEM);
}
} // namespace logger
