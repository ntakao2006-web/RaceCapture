package jp.ecorun.logger

import java.security.MessageDigest
import java.util.Locale

/**
 * This phone's settings as one line of text, to put the same settings into a spare phone
 * without typing them again (the settings screen shares / copies it and reads it back).
 * Written like [LineCode]:
 *
 *   ELCFG1|car=car2|p=wss://…|ll=0|…|id=XXXX
 *
 * The number after ELCFG is the format's version. Each part is `key=value`; in a value every
 * byte outside printable ASCII, and `%` and `|`, is written %XX (UTF-8), so the text survives a
 * QR code and a chat app. id is the first 4 hex digits of SHA-1 over everything between the
 * head and `|id=`, so a text cut short or mistyped is refused. Line breaks are ignored.
 *
 * Keys this version does not know are skipped (a newer app may add some); a higher version is
 * refused. The Wi-Fi password and the course-walk key are secrets: [encode] leaves them out
 * unless asked, and [changes] never shows them. Not in the code: the lines (they have their
 * own QR, [LineCode]), the locks, the laps and the 1G calibration, which belong to one phone.
 *
 * Nothing here touches Android: the settings screen turns [Settings] / [Race] into the
 * key-value map and back.
 */
object ConfigCode {
    const val PREFIX = "ELCFG"
    const val VERSION = 1

    class Invalid(message: String) : Exception(message)

    /**
     * One setting: [check] gives the value as it is kept (null: out of range), [show] how the
     * list of changes prints it. [race] items are the ones the race lock holds.
     */
    class Item(val key: String, val label: String, val secret: Boolean = false, val race: Boolean = false,
               val check: (String) -> String?, val show: (String) -> String)

    data class Parsed(val values: Map<String, String>, val unknown: List<String>) {
        val hasSecrets: Boolean get() = values.keys.any { ITEMS_BY_KEY.getValue(it).secret }
    }

    data class Change(val label: String, val from: String, val to: String)

    /** 2 decimals at most, no trailing zeros: 30, 12.5, 2360.11. */
    fun num(v: Double): String {
        val s = String.format(Locale.US, "%.2f", v)
        return s.trimEnd('0').trimEnd('.')
    }

    private const val EMPTY = "（空）"

    private fun text(key: String, label: String, max: Int, secret: Boolean = false) = Item(key, label, secret,
        check = { v -> v.trim().takeIf { it.length <= max && it.none { c -> c.code < 0x20 || c.code == 0x7f } } },
        show = { it.ifEmpty { EMPTY } })

    private fun choice(key: String, label: String, names: Map<String, String>, race: Boolean = false) = Item(key, label, race = race,
        check = { v -> v.takeIf { it in names } }, show = { names[it] ?: it.ifEmpty { EMPTY } })

    private fun bool(key: String, label: String, on: String = "オン", off: String = "オフ") = choice(key, label, mapOf("1" to on, "0" to off))

    /** A number in [range]; [blank]: may be empty (not set); [whole]: no fraction. */
    private fun number(key: String, label: String, range: ClosedFloatingPointRange<Double>, unit: String,
                       blank: Boolean = false, whole: Boolean = false, race: Boolean = false,
                       show: (Double) -> String = { num(it) + unit }) = Item(key, label, race = race,
        check = { v ->
            val t = v.trim()
            if (t.isEmpty()) "".takeIf { blank }
            else t.toDoubleOrNull()?.takeIf { it in range && (!whole || it == Math.rint(it)) }?.let { num(it) }
        },
        show = { v -> v.toDoubleOrNull()?.let(show) ?: EMPTY })

    private fun clock(s: Double): String {
        val cs = Math.round(s * 100)
        return String.format(Locale.US, "%d:%02d.%02d", cs / 6000, cs / 100 % 60, cs % 100)
    }

    const val CLASS = "cl"
    const val OTHER = "OTHER"
    /** Laps, time and distance are typed in only for the hand-entered class; the others carry their own. */
    private val CUSTOM = setOf("tl", "tm", "ds")

    fun marginKey(c: RaceClass) = "m_" + c.name

    /** In the order of the settings screen; the limits are the ones its save buttons use. */
    val ITEMS: List<Item> = listOf(
        choice("pf", "使い方", mapOf("ecorun" to "エコラン", "circuit" to "サーキット")),
        text("car", "車の名前", 64),
        text("p", "主サーバーのURL", 300),
        text("b", "予備サーバーのURL", 300),
        bool("ll", "ロガーへのつなぎ方", "このスマホのテザリング・同じWi-Fi", "ロガーのWi-Fi"),
        text("ls", "ロガーのWi-Fi名", 64),
        text("lp", "ロガーのWi-Fiのパスワード", 64, secret = true),
        text("lk", "コースウォーク画面の合言葉", 200, secret = true),
        text("lh", "ロガーのアドレス", 100),
        choice(CLASS, "クラス", RaceClass.entries.associate { it.name to it.code }, race = true),
    ) + RaceClass.entries.map { number(marginKey(it), "余裕（${it.code}）", 0.0..600.0, "秒", race = true) } + listOf(
        number("tl", "規定周回数", 1.0..999.0, "周", blank = true, whole = true, race = true),
        number("tm", "規定時間", 1.0..86400.0, "", blank = true, race = true, show = ::clock),
        number("ds", "規定距離", 1.0..1000000.0, "m", blank = true, race = true),
        number("ml", "最短ラップ", 5.0..7200.0, "秒"),
        number("ow", "油温の警告", 60.0..200.0, "℃"),
        number("ww", "水温の警告", 60.0..200.0, "℃"),
        number("av", "警報音の大きさ", 0.0..100.0, "%", whole = true),
        bool("ks", "画面を消さない（記録していなくても）"),
        bool("fb", "記録中は最大の明るさ"),
    )
    private val ITEMS_BY_KEY = ITEMS.associateBy { it.key }

    fun id(body: String): String =
        MessageDigest.getInstance("SHA-1").digest(body.toByteArray(Charsets.UTF_8))
            .take(2).joinToString("") { "%02X".format(it) }

    private fun esc(v: String): String = buildString {
        for (b in v.toByteArray(Charsets.UTF_8)) {
            val c = b.toInt() and 0xff
            if (c in 0x21..0x7e && c != '%'.code && c != '|'.code) append(c.toChar()) else append("%%%02X".format(c))
        }
    }

    private fun unesc(v: String): String {
        val out = java.io.ByteArrayOutputStream()
        var i = 0
        while (i < v.length) {
            val c = v[i]
            if (c == '%') {
                val hex = if (i + 2 < v.length) v.substring(i + 1, i + 3) else ""
                val b = hex.takeIf { it.length == 2 && it.all { h -> h in '0'..'9' || h in 'A'..'F' || h in 'a'..'f' } }?.toInt(16)
                out.write(b ?: throw Invalid("形式が違います（% の後ろが読めません）"))
                i += 3
            } else {
                if (c.code !in 0x21..0x7e) throw Invalid("形式が違います（使えない文字が入っています）")
                out.write(c.code); i++
            }
        }
        return out.toString("UTF-8")
    }

    /** True when [values] holds a secret that [encode] would put in when asked. */
    fun secretsIn(values: Map<String, String>): Boolean = ITEMS.any { it.secret && !values[it.key].isNullOrEmpty() }

    /**
     * [values] (key to value, as [Item.check] keeps them) as the text. Secrets only with
     * [secrets], and never an empty one: a phone without the key must not wipe another's.
     */
    fun encode(values: Map<String, String>, secrets: Boolean = false): String {
        val custom = values[CLASS] == OTHER
        val body = ITEMS.mapNotNull { item ->
            val v = values[item.key] ?: return@mapNotNull null
            if (item.secret && (!secrets || v.isEmpty())) return@mapNotNull null
            if (item.key in CUSTOM && !custom) return@mapNotNull null
            item.key + "=" + esc(item.check(v) ?: throw Invalid("${item.label} の値が範囲の外です"))
        }.joinToString("|")
        return "$PREFIX$VERSION|$body|id=${id(body)}"
    }

    /** Reads the text; every value has passed its [Item.check]. Throws [Invalid] with a message for the screen. */
    fun parse(text: String): Parsed {
        val t = text.filter { it != '\n' && it != '\r' }.trim()
        val head = t.substringBefore('|')
        val version = head.removePrefix(PREFIX).takeIf { head.startsWith(PREFIX) && it.isNotEmpty() && it.all(Char::isDigit) }?.toIntOrNull()
            ?: throw Invalid("EcoLoggerの設定ではありません")
        if (version > VERSION) throw Invalid("新しい版のアプリで書き出した設定です。このスマホのアプリを新しくしてから読み込んでください")
        if (version < 1) throw Invalid("EcoLoggerの設定ではありません")
        val end = t.lastIndexOf("|id=")
        if (end <= head.length) throw Invalid("途中で切れています（最後の id がありません）。全部を写し直してください")
        val body = t.substring(head.length + 1, end)
        if (!id(body).equals(t.substring(end + 4).trim(), ignoreCase = true)) {
            throw Invalid("読み取りが壊れています（id が合わない）。全部を写し直してください")
        }
        val values = LinkedHashMap<String, String>()
        val unknown = ArrayList<String>()
        for (part in body.split("|")) {
            val i = part.indexOf('=')
            if (i <= 0) throw Invalid("形式が違います")
            val key = part.substring(0, i)
            val item = ITEMS_BY_KEY[key]
            if (item == null) { unknown += key; continue }
            // The value itself is not printed: it may be a secret.
            values[key] = item.check(unesc(part.substring(i + 1))) ?: throw Invalid("${item.label} の値が範囲の外です")
        }
        if (values[CLASS] != OTHER) CUSTOM.forEach { values.remove(it) }
        if (values.isEmpty()) throw Invalid("読める項目がありません")
        return Parsed(values, unknown)
    }

    /** [incoming] without the items the race lock holds, and how many were left out. */
    fun withoutRace(incoming: Map<String, String>): Pair<Map<String, String>, Int> {
        val kept = incoming.filterKeys { !ITEMS_BY_KEY.getValue(it).race }
        return kept to incoming.size - kept.size
    }

    /** What reading [incoming] would change on a phone that has [current], in the screen's order. Secrets are not printed. */
    fun changes(current: Map<String, String>, incoming: Map<String, String>): List<Change> = ITEMS.mapNotNull { item ->
        val new = incoming[item.key] ?: return@mapNotNull null
        val old = current[item.key] ?: ""
        if (old == new) return@mapNotNull null
        if (item.secret) Change(item.label, if (old.isEmpty()) "（なし）" else "（入っている）", if (new.isEmpty()) "（なし）" else if (old.isEmpty()) "（入る）" else "（別の値になる）")
        else Change(item.label, item.show(old), item.show(new))
    }
}
