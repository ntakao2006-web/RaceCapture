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

    val urls: List<String> get() = listOf(primaryUrl, backupUrl).filter { it.startsWith("ws://") || it.startsWith("wss://") }

    /** null until chosen once (then the two-wheel class is applied, see [RaceClass.ensure]). */
    var raceClass: RaceClass?
        get() = prefs.getString("class", null)?.let { n -> RaceClass.entries.firstOrNull { it.name == n } }
        set(v) = prefs.edit().putString("class", v?.name).apply()
}

/**
 * Honda Eco Mileage Challenge 2026 (Motegi oval) classes. The app is mainly for
 * the two-wheel and electric two-wheel classes; the four-wheel rules stay
 * selectable, and OTHER keeps whatever laps / time limit are typed in.
 */
enum class RaceClass(val label: String, val laps: Int?, val limitS: Double?, val twoWheel: Boolean) {
    TWO_WHEEL("二輪・EV二輪（3周・16:27.36）", 3, 16 * 60 + 27.36, true),
    FOUR_WHEEL("四輪（7周・39:20.11）", 7, 39 * 60 + 20.11, false),
    OTHER("その他（手入力）", null, null, false);

    /** Makes this the class: its laps and time limit, and the matching 1G calibration. */
    fun apply(context: android.content.Context) {
        Settings(context).raceClass = this
        if (laps != null) Race.configure(Race.config().copy(totalLaps = laps, timeLimitS = limitS))
        Imu.setTwoWheel(twoWheel)
    }

    companion object {
        fun ensure(context: android.content.Context): RaceClass =
            Settings(context).raceClass ?: TWO_WHEEL.also { it.apply(context) }
    }
}
