package jp.ecorun.logger

import android.content.Context

/** Server URLs (room included, `wss://…/ws/audio/<room>`) and the car name. */
class Settings(context: Context) {
    private val prefs = context.getSharedPreferences("settings", Context.MODE_PRIVATE)

    var primaryUrl: String
        get() = prefs.getString("primary", "") ?: ""
        set(v) = prefs.edit().putString("primary", v.trim()).apply()
    var backupUrl: String
        get() = prefs.getString("backup", "") ?: ""
        set(v) = prefs.edit().putString("backup", v.trim()).apply()
    var carName: String
        get() = prefs.getString("car", "") ?: ""
        set(v) = prefs.edit().putString("car", v.trim()).apply()

    /**
     * Podium streaming key, only for sending straight to Podium when no relay
     * server answers ([PodiumDirect]). Kept in this app's private storage and
     * never shown again once saved.
     */
    var podiumKey: String
        get() = prefs.getString("podiumKey", "") ?: ""
        set(v) = prefs.edit().putString("podiumKey", v.trim()).apply()

    val urls: List<String> get() = listOf(primaryUrl, backupUrl).filter { it.startsWith("ws://") || it.startsWith("wss://") }

    /** Keep the screen on whenever the driver screen is open, not only while recording. */
    var keepScreenOn: Boolean
        get() = prefs.getBoolean("keepScreenOn", true)
        set(v) = prefs.edit().putBoolean("keepScreenOn", v).apply()
    /** Full brightness while recording, so the screen reads in sunshine (costs battery). */
    var fullBrightness: Boolean
        get() = prefs.getBoolean("fullBrightness", true)
        set(v) = prefs.edit().putBoolean("fullBrightness", v).apply()

    /** null until chosen once (then the CN motorcycle class is applied, see [RaceClass.ensure]). */
    var raceClass: RaceClass?
        get() = prefs.getString("class", null)?.let { n -> RaceClass.entries.firstOrNull { it.name == n } }
        set(v) = prefs.edit().putString("class", v?.name).apply()

    /**
     * Seconds to finish ahead of the time limit (a few seconds late disqualifies),
     * kept per class because the cars and the two-wheelers take it differently.
     */
    fun marginS(c: RaceClass): Double = prefs.getFloat("margin_${c.name}", DEFAULT_MARGIN_S.toFloat()).toDouble()
    fun setMarginS(c: RaceClass, s: Double) = prefs.edit().putFloat("margin_${c.name}", s.toFloat()).apply()

    companion object {
        const val DEFAULT_MARGIN_S = 30.0
    }
}

/**
 * Classes of the Honda Eco Mileage Challenge 2026 national final (Motegi oval),
 * as named in the regulation (EMC2026Regulation_ver2, chapter 2, article 1-1-4):
 * CN groups I-IV run 7 laps (16,389.68 m) in 39:20.11; the two-seater,
 * CN motorcycle and electric motorcycle classes run 3 laps (6,856.72 m) in
 * 16:27.36. The regulation has no short codes; [code] is ours for the screen.
 * The team's classes this year come first (CNG3 = the kosen CN fuel class,
 * CN two-wheel, EV two-wheel). OTHER keeps whatever laps / time are typed in.
 */
enum class RaceClass(val code: String, val official: String, val laps: Int?, val limitS: Double?, val twoWheel: Boolean,
                     val distanceM: Double? = if (laps == 7) 16389.68 else if (laps == 3) 6856.72 else null) {
    CNG3("CNG3", "CNグループⅢ（大学・短大・高専・専門学校生クラス）", 7, 39 * 60 + 20.11, false),
    CN_MOTORCYCLE("CN二輪", "CN二輪車クラス", 3, 16 * 60 + 27.36, true),
    EV_MOTORCYCLE("EV二輪", "電動二輪車クラス", 3, 16 * 60 + 27.36, true),
    CNG1("CNG1", "CNグループⅠ（中学生クラス）", 7, 39 * 60 + 20.11, false),
    CNG2("CNG2", "CNグループⅡ（高校生クラス）", 7, 39 * 60 + 20.11, false),
    CNG4("CNG4", "CNグループⅣ（一般クラス）", 7, 39 * 60 + 20.11, false),
    CN_TWO_SEATER("CN2人乗り", "CN2人乗りクラス", 3, 16 * 60 + 27.36, false),
    OTHER("その他", "手入力（周回数・規定時間を自分で入れる）", null, null, false);

    val label: String get() = if (laps == null) "$code：$official" else
        "$code：$official　${laps}周・" + DashboardView.clock(limitS!!, false) + ".%02d".format(Math.round((limitS % 1) * 100).toInt())

    /** Makes this the class: its laps and time limit, and the matching 1G calibration. */
    fun apply(context: android.content.Context) {
        val settings = Settings(context)
        settings.raceClass = this
        val c = Race.config().copy(marginS = settings.marginS(this))
        Race.configure(if (laps != null) c.copy(totalLaps = laps, timeLimitS = limitS, raceDistanceM = distanceM) else c)
        Imu.setTwoWheel(twoWheel)
    }

    companion object {
        fun ensure(context: android.content.Context): RaceClass {
            val settings = Settings(context)
            val c = settings.raceClass ?: return CN_MOTORCYCLE.also { it.apply(context) }
            // Classes chosen before the regulation distance and the margin were kept get them here.
            val cfg = Race.config()
            val fixed = cfg.copy(raceDistanceM = c.distanceM ?: cfg.raceDistanceM, marginS = settings.marginS(c))
            if (fixed != cfg) Race.configure(fixed)
            return c
        }
    }
}
