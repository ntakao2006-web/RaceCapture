package jp.ecorun.logger

import java.math.BigDecimal
import java.math.RoundingMode

/**
 * Same wire format as the Ver.2 logger (EcoCapture-Web/podium.py): `podium.meta`
 * lists the channels, each `podium.samples` row is the values in meta order
 * (missing ones skipped) followed by one presence bitmask per 32 channels.
 * Names, units, ranges and decimals follow podium.py so the server and Podium
 * treat both loggers alike.
 */
data class Channel(val key: String, val name: String, val unit: String,
                   val min: Double, val max: Double, val prec: Int)

object PodiumEncoder {
    val CHANNELS = listOf(
        Channel("Interval", "Interval", "ms", 0.0, 0.0, 0),
        Channel("Utc", "Utc", "ms", 0.0, 0.0, 0),
        Channel("Lat", "Latitude", "deg", -90.0, 90.0, 6),
        Channel("Lon", "Longitude", "deg", -180.0, 180.0, 6),
        Channel("Altitude", "Altitude", "m", -500.0, 9000.0, 2),
        Channel("GPSSpeed", "GPSSpeed", "km/h", 0.0, 300.0, 2),
        Channel("Speed", "Speed", "km/h", 0.0, 300.0, 2),
        Channel("Yaw", "Yaw", "deg", 0.0, 360.0, 2),
        Channel("GPSFix", "GPSFix", "", 0.0, 5.0, 0),
        Channel("GPSSats", "GPSSats", "", 0.0, 64.0, 0),
        Channel("AccelX", "AccelX", "m/s^2", -1000.0, 1000.0, 2),
        Channel("AccelY", "AccelY", "m/s^2", -1000.0, 1000.0, 2),
        Channel("AccelZ", "AccelZ", "m/s^2", -1000.0, 1000.0, 2),
        Channel("GyroX", "GyroX", "deg/s", -1000.0, 1000.0, 2),
        Channel("GyroY", "GyroY", "deg/s", -1000.0, 1000.0, 2),
        Channel("GyroZ", "GyroZ", "deg/s", -1000.0, 1000.0, 2),
        // Car axes after the mounting calibration: + accelerating / to the right / up.
        Channel("LongAccel", "LongAccel", "g", -8.0, 8.0, 3),
        Channel("LatAccel", "LatAccel", "g", -8.0, 8.0, 3),
        Channel("VertAccel", "VertAccel", "g", -8.0, 8.0, 3),
        // Lap channels as the Ver.2 logger sends them (minutes, RaceCapture names);
        // masked out until a control line is set.
        Channel("LapCount", "LapCount", "", 0.0, 10000.0, 0),
        Channel("CurrentLap", "CurrentLap", "", 0.0, 10000.0, 0),
        Channel("LapTime", "LapTime", "Min", 0.0, 60.0, 4),
        Channel("BestLap", "BestLap", "Min", 0.0, 60.0, 4),
        Channel("ElapsedTime", "ElapsedTime", "Min", 0.0, 60.0, 4),
        Channel("RaceTime", "RaceTime", "Min", 0.0, 600.0, 4),
        Channel("LapsLeft", "LapsLeft", "", 0.0, 1000.0, 0),
    )

    fun hello(clientId: String): String =
        """{"type":"hello","client_id":${quote(clientId)},"protocol":2,"role":"logger","audio_formats":[]}"""

    fun meta(): String = CHANNELS.joinToString(",", """{"type":"podium.meta","meta":[""", "]}") {
        """{"nm":${quote(it.name)},"ut":${quote(it.unit)},"sr":10,"min":${number(it.min, 0)},"max":${number(it.max, 0)},"prec":${it.prec}}"""
    }

    /** One row as a JSON array: present values in channel order, then the bitmasks. */
    fun row(values: Map<String, Double?>): String {
        val out = ArrayList<String>()
        val masks = LongArray((CHANNELS.size + 31) / 32)
        CHANNELS.forEachIndexed { i, ch ->
            val v = values[ch.key]
            if (v != null && v.isFinite()) {
                out.add(number(v, ch.prec))
                masks[i / 32] = masks[i / 32] or (1L shl (i % 32))
            }
        }
        masks.forEach { out.add(it.toString()) }
        return out.joinToString(",", "[", "]")
    }

    fun samples(rows: List<String>): String = rows.joinToString(",", """{"type":"podium.samples","samples":[""", "]}")

    /** Podium shows `prec` decimals anyway; dropping the rest keeps rows short. */
    fun number(v: Double, prec: Int): String =
        if (prec == 0) Math.round(v).toString()
        else BigDecimal(v).setScale(prec, RoundingMode.HALF_UP).stripTrailingZeros().toPlainString()

    fun quote(s: String): String {
        val b = StringBuilder("\"")
        for (c in s) when {
            c == '"' -> b.append("\\\"")
            c == '\\' -> b.append("\\\\")
            c < ' ' -> b.append(String.format("\\u%04x", c.code))
            else -> b.append(c)
        }
        return b.append('"').toString()
    }
}
