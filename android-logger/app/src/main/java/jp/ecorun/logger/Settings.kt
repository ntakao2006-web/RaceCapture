package jp.ecorun.logger

import android.content.Context

/** Server URLs (room included, `wss://…/ws/audio/<room>`) and the car name. */
class Settings(context: Context) {
    private val prefs = context.getSharedPreferences("settings", Context.MODE_PRIVATE)

    init {
        // The Podium streaming key was kept here for sending straight to Podium. That path is
        // gone (SP-9-4) and nothing reads the key any more, so a saved one is not left behind.
        if (prefs.contains("podiumKey")) prefs.edit().remove("podiumKey").apply()
    }

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
     * The Ver.2 logger as the car's position source ([LoggerLink]): its Wi-Fi
     * access point, its address there and the course-walk key (field_token).
     */
    var loggerSsid: String
        get() = prefs.getString("loggerSsid", "") ?: ""
        set(v) = prefs.edit().putString("loggerSsid", v.trim()).apply()
    var loggerPass: String
        get() = prefs.getString("loggerPass", "") ?: ""
        set(v) = prefs.edit().putString("loggerPass", v.trim()).apply()
    var loggerHost: String
        get() = prefs.getString("loggerHost", "") ?: ""
        set(v) = prefs.edit().putString("loggerHost", v.trim()).apply()
    var loggerKey: String
        get() = prefs.getString("loggerKey", "") ?: ""
        set(v) = prefs.edit().putString("loggerKey", v.trim()).apply()
    /**
     * How the phone reaches the logger: false = the logger's own access point (joined for this
     * app only); true = a Wi-Fi both are on, or this phone's hotspot with the logger as a client
     * (SUGO: the UNO Q joins the Pixel's tethering), where the logger is found by [Discovery].
     */
    var loggerLan: Boolean
        get() = prefs.getBoolean("loggerLan", false)
        set(v) = prefs.edit().putBoolean("loggerLan", v).apply()
    /** Where [Discovery] last found the logger, tried first next time. */
    var loggerFound: String
        get() = prefs.getString("loggerFound", "") ?: ""
        set(v) = prefs.edit().putString("loggerFound", v).apply()
    val loggerConfigured: Boolean get() = loggerKey.isNotEmpty() && (loggerLan || loggerSsid.isNotEmpty())
    val loggerHostOrDefault: String get() = loggerHost.ifEmpty { if (loggerLan) "" else DEFAULT_LOGGER_HOST }

    /**
     * The circuit screen ([Circuit], the spare of EcoCapture DASH) instead of the Eco Mileage
     * one. Only shows the logger's values: nothing is sent to the servers or Podium, the Ver.2
     * logger does that with the same key.
     */
    var circuit: Boolean
        get() = prefs.getString("profile", "ecorun") == "circuit"
        set(v) = prefs.edit().putString("profile", if (v) "circuit" else "ecorun").apply()
    var oilWarn: Double
        get() = prefs.getFloat("oilWarn", 120f).toDouble()
        set(v) = prefs.edit().putFloat("oilWarn", v.toFloat()).apply()
    var waterWarn: Double
        get() = prefs.getFloat("waterWarn", 110f).toDouble()
        set(v) = prefs.edit().putFloat("waterWarn", v.toFloat()).apply()
    /** The warning sound's loudness (0 to 1) on the alarm stream; the DASH's default. */
    var alarmVolume: Double
        get() = prefs.getFloat("alarmVolume", 0.8f).toDouble()
        set(v) = prefs.edit().putFloat("alarmVolume", v.toFloat()).apply()

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
        /** The logger's own address on its access point (NetworkManager's shared mode). */
        const val DEFAULT_LOGGER_HOST = "10.42.0.1"
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
