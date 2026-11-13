package jp.ecorun.logger

/** One light: a few characters read while driving; the colour says the rest. */
data class Light(val text: String, val kind: Kind) {
    enum class Kind { OK, WARN, BAD, OFF, UNKNOWN }
}

/**
 * The Ver.2 logger's own "記録・測位・送信" lights on the eco-run screen (SPEC.md M-2), apart from the
 * phone's own 記録 and 送信 chips. Worked out here, away from the drawing, from what [LoggerFeed] last
 * got. The sending light is the logger's word (field.py send_state, the same rule and words as
 * EcoCapture DASH's send_light): the phone does not judge it again.
 */
data class LoggerLights(val rec: Light, val gnss: Light, val send: Light) {
    companion object {
        /**
         * [fresh]: the logger's frames are coming ([LoggerFeed.fresh]); without them every light is
         * "--", never the last good one. [mcu]: its Linux side receives its MCU (no fix is known
         * without it). [send]: "ok" / "warn" / "off"; null from a logger whose EcoCapture is older
         * than the item, and anything else, is not known.
         */
        fun of(fresh: Boolean, mcu: Boolean, rec: Boolean, fix: Int, send: String?): LoggerLights {
            if (!fresh) return LoggerLights(Light("記録 --", Light.Kind.UNKNOWN), Light("測位 --", Light.Kind.UNKNOWN), Light("送信 --", Light.Kind.UNKNOWN))
            return LoggerLights(
                if (rec) Light("記録中", Light.Kind.OK) else Light("記録停止", Light.Kind.BAD),
                when { !mcu -> Light("測位 --", Light.Kind.UNKNOWN); fix != 0 -> Light("測位OK", Light.Kind.OK); else -> Light("測位なし", Light.Kind.BAD) },
                when (send) {
                    "ok" -> Light("送信中", Light.Kind.OK)
                    "warn" -> Light("未送信", Light.Kind.WARN)
                    "off" -> Light("送信OFF", Light.Kind.OFF)
                    else -> Light("送信 --", Light.Kind.UNKNOWN)
                })
        }
    }
}
