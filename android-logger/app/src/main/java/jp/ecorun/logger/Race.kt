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
        val (config, state) = try { load() } catch (_: Exception) { MOTEGI.copy(totalLaps = 3, timeLimitS = DEFAULT_LIMIT_S, raceDistanceM = DEFAULT_DISTANCE_M) to LapState() }
        timer = LapTimer(config, state) { save(it) }
        locked = prefs.getBoolean("locked", false)
        classLocked = prefs.getBoolean("classLocked", false)
        reference = prefs.getString("refId", null)?.let { Ref(it, prefs.getString("refAt", "") ?: "", prefs.getString("refSrc", "") ?: "") }
    }

    fun onFix(fix: Fix) = synchronized(lock) {
        lastFix = fix
        timer?.update(fix, SystemClock.elapsedRealtime())
    }

    fun values(): LapValues? = synchronized(lock) { timer?.values(SystemClock.elapsedRealtime()) }
    fun config(): LapConfig = synchronized(lock) { timer?.config ?: LapConfig() }
    fun laps(): List<Double> = synchronized(lock) { timer?.state?.laps?.toList() ?: emptyList() }
    fun configure(c: LapConfig) = synchronized(lock) { timer?.configure(c) }
    /** Clears the laps; done just before the race, so the lines and the class settings get locked as well. */
    fun reset() = synchronized(lock) { timer?.reset(); locked = true; classLocked = true; saveLock() }

    /** Between the start and the goal: the driver screen then guards the settings button. */
    fun racing(): Boolean = synchronized(lock) { timer?.state?.let { it.raceStartMs != null && !it.finished } ?: false }

    /**
     * Lap timing has begun (started, counting or finished) since the last reset. Until then the
     * lines and the required laps follow the Ver.2 logger ([LoggerLink]); after it nothing does.
     */
    fun timingStarted(): Boolean = synchronized(lock) {
        timer?.state?.let { it.raceStartMs != null || it.lapStartMs != null || it.count > 0 || it.finished } ?: false
    }

    /** The Ver.2 reference the lines came from (QR), or null for lines set on this phone. */
    data class Ref(val id: String, val at: String, val source: String)

    var reference: Ref? = null; private set
    /** Locked lines cannot be changed from the screen until unlocked (long press + confirm). */
    var locked = false; private set

    /** Takes the lines from a Ver.2 QR code and locks them. Throws [LineCode.Invalid]. */
    fun importReference(text: String): Ref = synchronized(lock) {
        val t = timer ?: throw LineCode.Invalid("まだ準備できていません")
        val r = LineCode.parse(text, t.config)
        t.configure(r.config)
        val ref = Ref(r.id, r.at, r.source)
        reference = ref; locked = true; saveLock()
        ref
    }

    fun setLocked(on: Boolean) = synchronized(lock) { locked = on; saveLock() }

    /** Locked class settings (class, laps, time, distance, margin) cannot be changed from the screen until unlocked. */
    var classLocked = false; private set
    fun setClassLocked(on: Boolean) = synchronized(lock) { classLocked = on; saveLock() }

    /** Lines changed on this phone are no longer the Ver.2 reference. */
    private fun ownLines() { reference = null; saveLock() }

    private fun saveLock() {
        prefs.edit().putBoolean("locked", locked).putBoolean("classLocked", classLocked).putString("refId", reference?.id).putString("refAt", reference?.at)
            .putString("refSrc", reference?.source).apply()
    }

    /** Line edits from the screen; refused while locked. */
    fun setGate(target: String, g: Gate?): Boolean = synchronized(lock) {
        if (locked) return false
        timer?.configure(config().withGate(target, g)); ownLines(); true
    }

    /** Returns false when there is no recent fix to take the position from, or the lines are locked. */
    fun setHere(target: String): Boolean = synchronized(lock) {
        if (locked) return false
        ownLines()
        val f = lastFix ?: return false
        if (System.currentTimeMillis() - f.utcMs > 5000) return false
        // A line taken from a poor fix would be off by as much: wait for the phone to settle.
        if ((f.accM ?: Double.MAX_VALUE) > HERE_MAX_ACC_M) return false
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
            .put("distance", c.raceDistanceM ?: JSONObject.NULL).put("margin", c.marginS)
            .put("count", s.count).put("last", s.lastS ?: JSONObject.NULL).put("best", s.bestS ?: JSONObject.NULL)
            .put("lapStart", s.lapStartMs ?: JSONObject.NULL).put("raceStart", s.raceStartMs ?: JSONObject.NULL)
            .put("raceEnd", s.raceEndMs ?: JSONObject.NULL).put("finished", s.finished)
            .put("laps", JSONArray(s.laps)).put("lapDist", s.lapDistM).put("distScale", s.distScale)
            .put("startFallback", s.startFallback ?: JSONObject.NULL).put("finishFallback", s.finishFallback ?: JSONObject.NULL)
        prefs.edit().putString("race", json.toString()).apply()
    }

    private fun load(): Pair<LapConfig, LapState> {
        val text = prefs.getString("race", null) ?: return MOTEGI.copy(totalLaps = 3, timeLimitS = DEFAULT_LIMIT_S, raceDistanceM = DEFAULT_DISTANCE_M) to LapState()
        val o = JSONObject(text)
        val config = LapConfig(gate(o.optJSONObject("control")), gate(o.optJSONObject("start")), gate(o.optJSONObject("goal")),
            o.optDouble("minLap", 10.0), o.optDouble("maxLap", 3600.0),
            if (o.isNull("totalLaps")) null else o.getInt("totalLaps"), o.doubleOrNull("limit"), o.doubleOrNull("distance"),
            o.optDouble("margin", 0.0))
        val laps = o.optJSONArray("laps")
        val state = LapState(o.optInt("count"), o.doubleOrNull("last"), o.doubleOrNull("best"),
            o.longOrNull("lapStart"), o.longOrNull("raceStart"), o.longOrNull("raceEnd"), o.optBoolean("finished"),
            MutableList(laps?.length() ?: 0) { laps!!.getDouble(it) }, o.optDouble("lapDist", 0.0), o.optDouble("distScale", 1.0),
            if (o.isNull("startFallback")) null else o.getString("startFallback"),
            if (o.isNull("finishFallback")) null else o.getString("finishFallback"))
        return config to state
    }

    /** Honda EMC 2026, two-wheel classes: 3 laps in 16:27.36 (see [RaceClass]). */
    const val DEFAULT_LIMIT_S = 16 * 60 + 27.36
    const val DEFAULT_DISTANCE_M = 6856.72
    /** "Set the line here" takes no fix less accurate than this (m). */
    const val HERE_MAX_ACC_M = 10.0

    /**
     * Rough lines for the national final (Motegi oval), picked by the user on
     * Google Maps on 2026-10-19 ("たしか"): all on the west straight, north to
     * south goal - control - start. Cars run counter-clockwise, i.e. south here,
     * so a lap is start -> round the oval -> control, and the final lap leaves
     * for the goal before the control line. This matches the regulation
     * distances (7 laps 16389.68 m, 3 laps 6856.72 m: one lap ~2383 m, the goal
     * ~290 m before the start). Heading 150 deg (SSE, along the straight) and a
     * 40 m width so a point 10-20 m off still catches the car. To be replaced
     * on the course walk with "set here".
     */
    val MOTEGI = LapConfig(
        control = Gate(36.532800, 140.226322, 150.0, 40.0),
        start = Gate(36.530730, 140.228057, 150.0, 40.0),
        goal = Gate(36.533566, 140.226005, 150.0, 40.0),
    )

    /** Puts the Motegi lines in, keeping the class settings. */
    fun useMotegiLines() {
        synchronized(lock) {
            val t = timer ?: return
            if (locked) return
            ownLines()
            t.configure(t.config.copy(control = MOTEGI.control, start = MOTEGI.start, goal = MOTEGI.goal))
        }
    }
}
