package jp.ecorun.logger

import android.content.Context
import org.json.JSONArray

/**
 * Process-wide [Mount] shared by the service (feeds rows and fixes) and the
 * settings screen (manual 1G calibration, status). Saved so the calibration
 * survives restarts; the phone is expected to stay in its holder.
 */
object Imu {
    private val lock = Any()
    private val mount = Mount()
    private var prefs: android.content.SharedPreferences? = null
    private var rowsSinceSave = 0

    fun init(context: Context) {
        synchronized(lock) {
            if (prefs != null) return
            val p = context.applicationContext.getSharedPreferences("imu", Context.MODE_PRIVATE)
            prefs = p
            try {
                p.getString("mount", null)?.let { s -> val a = JSONArray(s); mount.load(DoubleArray(a.length()) { a.getDouble(it) }) }
            } catch (_: Exception) {}
        }
    }

    /** Returns (LongAccel, LatAccel, VertAccel) in G for this row, or null before calibration. */
    fun onRow(accel: DoubleArray?, gyro: DoubleArray?, speedKmh: Double?): DoubleArray? = synchronized(lock) {
        mount.onRow(accel, gyro, speedKmh)
        if (++rowsSinceSave >= 300) save() // every 30 s: keeps auto calibration and forward learning
        accel?.let { mount.vehicle(it) }
    }

    fun onFix(utcMs: Long, speedMs: Double?, bearing: Double?) = synchronized(lock) { mount.onFix(utcMs, speedMs, bearing) }

    fun calibrateNow(): Boolean = synchronized(lock) { mount.calibrateNow().also { if (it) save() } }

    fun clear() = synchronized(lock) { mount.clearCalibration(); save() }

    /** One line for the settings screen. */
    fun describe(): String = synchronized(lock) {
        val up = when {
            mount.up == null -> "1G：まだ（停車中に自動で取るか、下のボタンで）"
            mount.manual && mount.moved -> "1G：手動で校正済み。ただし今の向きと10°以上違います（付け直した？）"
            mount.manual -> "1G：手動で校正済み"
            else -> "1G：停車中に自動で校正済み"
        }
        val fwd = when {
            mount.up == null -> ""
            mount.forwardLearned -> "　前方：GNSSで校正済み" + (mount.forwardOffsetDeg()?.let { "（画面の向きから %.0f°）".format(it) } ?: "")
            else -> "　前方：画面の向きから推定（走ると加減速からGNSSで校正）"
        }
        up + fwd
    }

    private fun save() {
        rowsSinceSave = 0
        prefs?.edit()?.putString("mount", JSONArray(mount.save().toList()).toString())?.apply()
    }
}
