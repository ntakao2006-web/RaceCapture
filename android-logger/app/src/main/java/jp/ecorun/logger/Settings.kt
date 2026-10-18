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
}
