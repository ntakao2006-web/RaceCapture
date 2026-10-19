package jp.ecorun.logger

import android.content.Context
import android.os.SystemClock
import org.json.JSONArray
import org.json.JSONObject

/**
 * Process-wide lap timer shared by the service (feeds fixes) and the screens
 * (show laps, set lines). Lines and lap state are saved on every change, so a
 * restarted app keeps counting the same race.
 */
object Race {
    private val lock = Any()
    private var timer: LapTimer? = null
    private lateinit var prefs: android.content.SharedPreferences

    /** Last GNSS fix (any accuracy), for "set the line here". */
    @Volatile var lastFix: Fix? = null; private set

    fun init(context: Context) = synchronized(lock) {
        if (timer != null) return
        prefs = context.applicationContext.getSharedPreferences("race", Context.MODE_PRIVATE)
        val (config, state) = try { load() } catch (_: Exception) { LapConfig(totalLaps = 3, timeLimitS = DEFAULT_LIMIT_S) to LapState() }
        timer = LapTimer(config, state) { save(it) }
    }

    fun onFix(fix: Fix) = synchronized(lock) {
        lastFix = fix
        timer?.update(fix, SystemClock.elapsedRealtime())
    }

    fun values(): LapValues? = synchronized(lock) { timer?.values(SystemClock.elapsedRealtime()) }
    fun config(): LapConfig = synchronized(lock) { timer?.config ?: LapConfig() }
    fun laps(): List<Double> = synchronized(lock) { timer?.state?.laps?.toList() ?: emptyList() }
    fun configure(c: LapConfig) = synchronized(lock) { timer?.configure(c) }
    fun reset() = synchronized(lock) { timer?.reset() }

    /** Returns false when there is no recent fix to take the position from. */
    fun setHere(target: String): Boolean = synchronized(lock) {
        val f = lastFix ?: return false
        if (System.currentTimeMillis() - f.utcMs > 5000) return false
        timer?.setHere(target, f); true
    }

    private fun gateJson(g: Gate?) = g?.let {
        JSONObject().put("lat", it.lat).put("lon", it.lon).put("width", it.widthM).apply { it.bearing?.let { b -> put("bearing", b) } }
    }
    private fun gate(o: JSONObject?) = o?.let {
        Gate(it.getDouble("lat"), it.getDouble("lon"), if (it.has("bearing")) it.getDouble("bearing") else null, it.optDouble("width", 30.0))
    }
    // isNull() is true for both a missing key and an explicit null.
    private fun JSONObject.longOrNull(k: String) = if (isNull(k)) null else getLong(k)
    private fun JSONObject.doubleOrNull(k: String) = if (isNull(k)) null else getDouble(k)

    private fun save(t: LapTimer) {
        val c = t.config; val s = t.state
        val json = JSONObject()
            .put("control", gateJson(c.control)).put("start", gateJson(c.start)).put("goal", gateJson(c.goal))
            .put("minLap", c.minLapS).put("maxLap", c.maxLapS)
            .put("totalLaps", c.totalLaps ?: JSONObject.NULL).put("limit", c.timeLimitS ?: JSONObject.NULL)
            .put("count", s.count).put("last", s.lastS ?: JSONObject.NULL).put("best", s.bestS ?: JSONObject.NULL)
            .put("lapStart", s.lapStartMs ?: JSONObject.NULL).put("raceStart", s.raceStartMs ?: JSONObject.NULL)
            .put("raceEnd", s.raceEndMs ?: JSONObject.NULL).put("finished", s.finished)
            .put("laps", JSONArray(s.laps))
        prefs.edit().putString("race", json.toString()).apply()
    }

    private fun load(): Pair<LapConfig, LapState> {
        val text = prefs.getString("race", null) ?: return LapConfig(totalLaps = 3, timeLimitS = DEFAULT_LIMIT_S) to LapState()
        val o = JSONObject(text)
        val config = LapConfig(gate(o.optJSONObject("control")), gate(o.optJSONObject("start")), gate(o.optJSONObject("goal")),
            o.optDouble("minLap", 10.0), o.optDouble("maxLap", 3600.0),
            if (o.isNull("totalLaps")) null else o.getInt("totalLaps"), o.doubleOrNull("limit"))
        val laps = o.optJSONArray("laps")
        val state = LapState(o.optInt("count"), o.doubleOrNull("last"), o.doubleOrNull("best"),
            o.longOrNull("lapStart"), o.longOrNull("raceStart"), o.longOrNull("raceEnd"), o.optBoolean("finished"),
            MutableList(laps?.length() ?: 0) { laps!!.getDouble(it) })
        return config to state
    }

    /** Honda EMC 2026, two-wheel classes: 3 laps in 16:27.36 (see [RaceClass]). */
    const val DEFAULT_LIMIT_S = 16 * 60 + 27.36
}
