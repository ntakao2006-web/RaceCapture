package jp.ecorun.logger

import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.roundToLong
import kotlin.math.sin

/**
 * GNSS lap timing, ported from the Ver.2 logger (EcoCapture-Web/lap.py) so both
 * loggers count laps the same way: a control line passed every lap, plus an
 * optional standing-start line and a goal line crossed once after the required
 * laps. See lap.py for the reasoning behind each rule. Differences:
 * - A phone's fix can be 10-25 m off (its own reported accuracy), and a few
 *   poor fixes in a row are common. So a line is taken as crossed within its
 *   half width plus that accuracy, and fixes too poor to use (over 25 m) are
 *   skipped rather than breaking the track: the last good fix and the next one
 *   up to 10 s later still count as consecutive. Both were seen missing a start
 *   line on the 2026-10-22 test ride (24 m off the centre at 18 m accuracy;
 *   and 25-47 m accuracy for the 7 s around a crossing 10 m off the centre).
 * - Persistence is left to the caller ([onChange]).
 */
data class Gate(val lat: Double, val lon: Double, val bearing: Double? = null, val widthM: Double = 30.0)

data class LapConfig(
    val control: Gate? = null,
    val start: Gate? = null,
    val goal: Gate? = null,
    val minLapS: Double = 10.0,
    val maxLapS: Double = 3600.0,
    val totalLaps: Int? = null,
    /** Regulation time in seconds (only shown to the driver, never ends the race). */
    val timeLimitS: Double? = null,
    /** Regulation distance in metres, for the average-speed pacing ([Pace]). */
    val raceDistanceM: Double? = null,
    /** Seconds the pacing aims to finish ahead of [timeLimitS] ([Settings.marginS]). */
    val marginS: Double = 0.0,
) {
    fun gate(target: String) = when (target) { "control" -> control; "start" -> start; else -> goal }
    fun withGate(target: String, g: Gate?) = when (target) {
        "control" -> copy(control = g); "start" -> copy(start = g); else -> copy(goal = g)
    }
}

data class LapState(
    var count: Int = 0,
    var lastS: Double? = null,
    var bestS: Double? = null,
    var lapStartMs: Long? = null,
    var raceStartMs: Long? = null,
    var raceEndMs: Long? = null,
    var finished: Boolean = false,
    val laps: MutableList<Double> = ArrayList(),
    /** Distance driven in the current lap (GNSS speed over time), for its running average. */
    var lapDistM: Double = 0.0,
    /**
     * Regulation lap distance over the GNSS distance of the last whole lap: GNSS
     * runs a few percent short (2.2-2.3 km against 2.38 km on the team's Motegi
     * log), so the running average is scaled to agree with the lap averages.
     */
    var distScale: Double = 1.0,
)

/** One GNSS fix: GNSS UTC, position, horizontal accuracy, speed (km/h), heading. */
data class Fix(val utcMs: Long, val lat: Double, val lon: Double,
               val accM: Double? = null, val speedKmh: Double? = null, val yaw: Double? = null)

/** Values for display and the Podium lap channels (times in seconds here). */
data class LapValues(
    val count: Int, val current: Int, val lastS: Double?, val bestS: Double?, val elapsedS: Double?,
    val raceS: Double?, val lapsLeft: Int?, val finished: Boolean,
    val lapDistM: Double = 0.0,
)

private const val EARTH_M_PER_DEG = 111320.0
private const val MAX_HACC_M = 25.0
private const val MAX_FIX_GAP_MS = 10_000L
private const val LEARN_MIN_KMH = 5.0
private const val KEEP_INSIDE = 600

private data class P(val t: Long, val x: Double, val y: Double)

private fun offset(g: Gate, f: Fix) =
    P(f.utcMs, (f.lon - g.lon) * EARTH_M_PER_DEG * cos(Math.toRadians(g.lat)), (f.lat - g.lat) * EARTH_M_PER_DEG)

/** Interpolated time when a -> b crosses the line forward within `half` of its centre. */
private fun lineCrossing(bearing: Double, half: Double, a: P, b: P): Long? {
    val rad = Math.toRadians(bearing)
    val nx = sin(rad); val ny = cos(rad)
    val d0 = a.x * nx + a.y * ny
    val d1 = b.x * nx + b.y * ny
    if (!(d0 < 0 && 0 <= d1)) return null
    val f = -d0 / (d1 - d0)
    val px = a.x + (b.x - a.x) * f; val py = a.y + (b.y - a.y) * f
    if (abs(px * ny - py * nx) > half) return null
    return (a.t + (b.t - a.t) * f).roundToLong()
}

private class Watch(val rearm: Boolean = true) {
    var armed = true
    var inside = ArrayList<P>()

    fun reset() { armed = true; inside = ArrayList() }

    fun observe(g: Gate, current: Fix) {
        if (!armed) {
            val p = offset(g, current)
            armed = hypot(p.x, p.y) > g.widthM
            inside = ArrayList()
        }
    }

    /** Returns crossing time (or null) and a learned bearing (or null). */
    fun step(g: Gate, previous: Fix, current: Fix, slack: Double = 0.0): Pair<Long?, Double?> {
        val a = offset(g, previous); val b = offset(g, current)
        if (!armed) return null to null
        val half = g.widthM / 2
        if (g.bearing != null) {
            val at = lineCrossing(g.bearing, half + slack, a, b)
            if (at != null && rearm) armed = false
            return at to null
        }
        if (hypot(b.x, b.y) <= half) {
            if (inside.isEmpty()) inside.add(a)
            inside.add(b)
            while (inside.size > KEEP_INSIDE) inside.removeAt(0)
            return null to null
        }
        if (inside.isEmpty()) return null to null
        val points = inside + b
        inside = ArrayList()
        val speed = current.speedKmh; val yaw = current.yaw
        val learned = if (speed != null && speed >= LEARN_MIN_KMH && yaw != null) ((yaw % 360) + 360) % 360 else null
        var at: Long? = null
        if (learned != null) {
            for (i in 0 until points.size - 1) at = lineCrossing(learned, g.widthM, points[i], points[i + 1]) ?: at
        }
        if (at == null) at = points.minBy { hypot(it.x, it.y) }.t
        if (rearm) armed = false
        return at to learned
    }
}

class LapTimer(config: LapConfig = LapConfig(), val state: LapState = LapState(),
               private val onChange: (LapTimer) -> Unit = {}) {
    var config: LapConfig = config; private set
    private var previous: Fix? = null
    /** GNSS UTC of the last usable fix and the monotonic ms it arrived at. */
    var latest: Pair<Long, Long>? = null; private set
    private val watches = mapOf("start" to Watch(rearm = false), "control" to Watch(), "goal" to Watch())

    fun configure(c: LapConfig) { config = c; forgetMotion(); onChange(this) }

    fun reset() {
        state.count = 0; state.lastS = null; state.bestS = null; state.lapStartMs = null
        state.raceStartMs = null; state.raceEndMs = null; state.finished = false; state.laps.clear(); state.lapDistM = 0.0; state.distScale = 1.0
        forgetMotion(); onChange(this)
    }

    private fun forgetMotion() { previous = null; watches.values.forEach { it.reset() } }

    /** A line through [fix]; the heading is learned on the first pass unless the car is moving. */
    fun setHere(target: String, fix: Fix, widthM: Double? = null) {
        val moving = fix.speedKmh != null && fix.speedKmh >= LEARN_MIN_KMH && fix.yaw != null
        val old = config.gate(target)
        configure(config.withGate(target, Gate(fix.lat, fix.lon, if (moving) ((fix.yaw!! % 360) + 360) % 360 else null,
            widthM ?: old?.widthM ?: 30.0)))
    }

    fun values(nowMonoMs: Long): LapValues {
        val s = state
        val now = latest?.let { it.first + (nowMonoMs - it.second) }
        fun since(start: Long?) = if (start == null || now == null) null else maxOf(0.0, (now - start) / 1000.0)
        val total = config.totalLaps
        return if (s.finished) {
            LapValues(s.count, s.count, s.lastS, s.bestS, null,
                s.raceStartMs?.let { (s.raceEndMs!! - it) / 1000.0 }, total?.let { maxOf(0, it - s.count) }, true)
        } else {
            LapValues(s.count, if (s.lapStartMs != null) s.count + 1 else 0, s.lastS, s.bestS, since(s.lapStartMs),
                since(s.raceStartMs), total?.let { maxOf(0, it - s.count) }, false, s.lapDistM * s.distScale)
        }
    }

    private fun recordLap(at: Long) {
        val lap = (at - state.lapStartMs!!) / 1000.0
        state.count++; state.lastS = lap
        state.bestS = state.bestS?.let { minOf(it, lap) } ?: lap
        val ratio = Pace.lapDistanceM(config, state.laps.size)?.let { if (state.lapDistM > 0) it / state.lapDistM else null }
        if (ratio != null && ratio in 0.85..1.15) state.distScale = ratio
        state.laps.add(lap)
    }

    private fun started(at: Long) {
        if (state.finished || state.count > 0) return
        state.raceStartMs = at; state.lapStartMs = at // a later forward crossing (re-start) replaces it
        onChange(this)
    }

    private fun crossed(at: Long) {
        if (state.finished || (config.start != null && state.raceStartMs == null)) return
        val start = state.lapStartMs
        if (start == null) {
            state.lapStartMs = at
            if (state.raceStartMs == null) state.raceStartMs = at
        } else {
            val lap = (at - start) / 1000.0
            if (lap < config.minLapS) return
            if (lap <= config.maxLapS) recordLap(at)
            state.lapStartMs = at
        }
        onChange(this)
    }

    private fun finished(at: Long) {
        val start = state.lapStartMs ?: return
        if (state.finished) return
        val total = config.totalLaps
        if (total != null && state.count < total - 1) return
        if ((at - start) / 1000.0 >= config.minLapS) recordLap(at)
        state.finished = true; state.raceEndMs = at; state.lapStartMs = null
        onChange(this)
    }

    fun update(fix: Fix, nowMonoMs: Long) {
        if (fix.accM != null && fix.accM > MAX_HACC_M) {
            // Skipped, but the last good fix stays: the next good one bridges the gap.
            // Nor may a poor fix re-arm a line.
            watches.values.forEach { it.inside = ArrayList() }
            return
        }
        latest = fix.utcMs to nowMonoMs
        if (config.control == null) return
        val prev = previous
        previous = fix
        for (t in TARGETS) config.gate(t)?.let { watches.getValue(t).observe(it, fix) }
        if (prev == null || !(fix.utcMs - prev.utcMs in 1..MAX_FIX_GAP_MS)) {
            watches.values.forEach { it.inside = ArrayList() }
            return
        }
        val lapBefore = state.lapStartMs
        val slack = minOf(MAX_HACC_M, maxOf(prev.accM ?: 0.0, fix.accM ?: 0.0))
        var learnedAny = false
        for (t in listOf("start", "control", "goal")) {
            val g = config.gate(t) ?: continue
            val (at, learned) = watches.getValue(t).step(g, prev, fix, slack)
            if (learned != null) { config = config.withGate(t, g.copy(bearing = learned)); learnedAny = true }
            if (at != null) when (t) { "start" -> started(at); "control" -> crossed(at); else -> finished(at) }
        }
        addDistance(prev, fix, lapBefore)
        if (learnedAny) onChange(this)
    }

    /** Adds the part of prev -> fix driven in the current lap (all of it, or what follows a new lap's start). */
    private fun addDistance(prev: Fix, fix: Fix, lapBefore: Long?) {
        val start = state.lapStartMs ?: return
        if (state.finished) return
        if (start != lapBefore) state.lapDistM = 0.0
        val from = maxOf(start, prev.utcMs)
        if (from >= fix.utcMs) return
        val a = prev.speedKmh; val b = fix.speedKmh
        val mps = if (a != null && b != null) (a + b) / 2 / 3.6 else {
            val p = offset(Gate(prev.lat, prev.lon), fix)
            hypot(p.x, p.y) / ((fix.utcMs - prev.utcMs) / 1000.0)
        }
        state.lapDistM += mps * (fix.utcMs - from) / 1000.0
    }

    companion object {
        val TARGETS = listOf("control", "start", "goal")
    }
}
