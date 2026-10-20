package jp.ecorun.logger

import java.security.MessageDigest

/**
 * The reference lines as one line of text, for the QR code the Ver.2 logger
 * shows (EcoCapture-Web/lap.py line_code() writes the same format). The Ver.2
 * GNSS with its active antenna is far more precise than a phone's, so its lines
 * are the single reference every phone copies.
 *
 *   ECOLINES1|c=lat,lon,bearing,width|s=...|g=...|at=<when>|src=<who>|id=XXXX
 *
 * c / s / g are the control, start and goal lines ("-" for a missing line or
 * an unknown bearing). id is the first 4 hex digits (upper case) of SHA-1 over
 * the "c=...|s=...|g=..." part exactly as written, so a phone can tell a
 * misread or a different reference.
 */
object LineCode {
    const val PREFIX = "ECOLINES1"

    data class Reference(val config: LapConfig, val id: String, val at: String, val source: String)

    class Invalid(message: String) : Exception(message)

    fun id(lines: String): String =
        MessageDigest.getInstance("SHA-1").digest(lines.toByteArray(Charsets.UTF_8))
            .take(2).joinToString("") { "%02X".format(it) }

    /** Reads [text] into lines on top of [base] (class settings are kept). */
    fun parse(text: String, base: LapConfig): Reference {
        val parts = text.trim().split("|")
        if (parts.firstOrNull() != PREFIX) throw Invalid("EcoLoggerのラインのQRではありません")
        val fields = parts.drop(1).associate { p ->
            val i = p.indexOf('=')
            if (i <= 0) throw Invalid("形式が違います：$p")
            p.substring(0, i) to p.substring(i + 1)
        }
        val lines = listOf("c", "s", "g").joinToString("|") { "$it=" + (fields[it] ?: throw Invalid("${it}が無い")) }
        val id = fields["id"] ?: throw Invalid("idが無い")
        if (id(lines) != id) throw Invalid("読み取りが壊れています（id が合わない）。もう一度読み込んでください")
        val control = gate(fields.getValue("c")) ?: throw Invalid("コントロールラインが入っていません")
        return Reference(base.copy(control = control, start = gate(fields.getValue("s")), goal = gate(fields.getValue("g"))),
            id, fields["at"] ?: "", fields["src"] ?: "")
    }

    private fun gate(v: String): Gate? {
        if (v == "-") return null
        val p = v.split(",")
        if (p.size != 4) throw Invalid("ラインの形式が違います：$v")
        val lat = p[0].toDoubleOrNull(); val lon = p[1].toDoubleOrNull()
        val bearing = if (p[2] == "-") null else p[2].toDoubleOrNull() ?: throw Invalid("向きが読めません：$v")
        val width = p[3].toDoubleOrNull()
        if (lat == null || lon == null || width == null || lat !in -90.0..90.0 || lon !in -180.0..180.0 ||
            width !in 5.0..200.0 || (bearing != null && bearing !in 0.0..<360.0)) throw Invalid("値が範囲外です：$v")
        return Gate(lat, lon, bearing, width)
    }
}
