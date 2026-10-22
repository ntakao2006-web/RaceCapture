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
 * - A missed start line does not lose the race: the control line starts it
 *   instead ([LapState.startFallback]). If the car was seen standing near the
 *   start line and leaving it, its closest pass by the line after that (else
 *   the departure itself) is taken as the start and the control crossing ends
 *   lap 1; otherwise the clock starts at the control
 *   line, and is moved back to such a departure if one follows (the car went
 *   through the control line on its way to the grid).
 * - Race-day safety nets (2026-10-22 review): a line crossed after 15 min with
 *   no lap event starts a new race (laps left over from practice must not
 *   swallow the race); a lap about k times the planned length is k laps with
 *   the control line missed in between; on the final lap the control line
 *   after a missed goal (or with no goal line) ends the race; and a race
 *   started at the control line (start missed) may finish one lap early,
 *   since that first control pass was most likely the end of lap 1.
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
    /**
     * How the race was started when the start line was missed: "depart" (the
     * car leaving a stop near the start line), "control" (the control line), or
     * null (the start line itself, or no start line configured).
     */
    var startFallback: String? = null,
    /** "control" when the race ended at the control line because the goal line was missed, else null. */
    var finishFallback: String? = null,
    /** When [lapDistM] started counting: the lap start, or the first fix after the app restarted mid-lap (not saved). */
    var distFromMs: Long? = null,
)

/** One GNSS fix: GNSS UTC, position, horizontal accuracy, speed (km/h), heading. */
data class Fix(val utcMs: Long, val lat: Double, val lon: Double,
               val accM: Double? = null, val speedKmh: Double? = null, val yaw: Double? = null)

/** Values for display and the Podium lap channels (times in seconds here). */
data class LapValues(
    val count: Int, val current: Int, val lastS: Double?, val bestS: Double?, val elapsedS: Double?,
    val raceS: Double?, val lapsLeft: Int?, val finished: Boolean,
    /** This lap's running average (km/h) over the part tracked so far, null for its first 5 s. */
    val avgKmh: Double? = null,
    val startFallback: String? = null,
    val finishFallback: String? = null,
)

private const val EARTH_M_PER_DEG = 111320.0
private const val MAX_HACC_M = 25.0
private const val MAX_FIX_GAP_MS = 10_000L
private const val LEARN_MIN_KMH = 5.0
private const val KEEP_INSIDE = 600
/** A stop within this distance of the start line, then moving off, is taken as the start if the line is missed. */
private const val DEPART_NEAR_M = 60.0
private const val STOPPED_KMH = 3.0
private const val MOVING_KMH = 5.0
/** No lap event for this long, then a line crossing: a new race (the old laps were practice). */
private const val STALE_MS = 15 * 60_000L
/** A lap this many times its planned length (or, without one, the median lap) hides missed control lines. */
private const val MISSED_LAP_FACTOR = 1.6

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
        if (hypot(b.x, b.y) <= half + slack) {
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
    /**
     * For a missed start line: the last time the car stood near it, and then the
     * estimated start, its closest pass by the line after moving off (on the
     * 2026-10-22 ride it stopped 40 m short, so moving off was 9.5 s early).
     */
    private var stoppedNearStartMs: Long? = null
    private var departMs: Long? = null
    private var nearestStartM: Double? = null

    fun configure(c: LapConfig) { config = c; forgetMotion(); onChange(this) }

    fun reset() {
        clearLaps()
        stoppedNearStartMs = null; departMs = null; nearestStartM = null
        forgetMotion(); onChange(this)
    }

    /** Back to before the start; the line watches and a departure being tracked are kept. */
    private fun clearLaps() {
        state.count = 0; state.lastS = null; state.bestS = null; state.lapStartMs = null
        state.raceStartMs = null; state.raceEndMs = null; state.finished = false; state.laps.clear(); state.lapDistM = 0.0; state.distScale = 1.0
        state.startFallback = null; state.finishFallback = null; state.distFromMs = null
    }

    private fun lastEventMs() = listOfNotNull(state.raceEndMs, state.lapStartMs, state.raceStartMs).maxOrNull()

    /** Laps or a race exist, and nothing has happened for [STALE_MS] before [at]. */
    private fun stale(at: Long) = lastEventMs()?.let { at - it > STALE_MS } ?: false

    private fun newRaceIfStale(at: Long) { if (stale(at)) clearLaps() }

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
                s.raceStartMs?.let { (s.raceEndMs!! - it) / 1000.0 }, total?.let { maxOf(0, it - s.count) }, true,
                startFallback = s.startFallback, finishFallback = s.finishFallback)
        } else {
            val tracked = since(s.distFromMs)
            LapValues(s.count, if (s.lapStartMs != null) s.count + 1 else 0, s.lastS, s.bestS, since(s.lapStartMs),
                since(s.raceStartMs), total?.let { maxOf(0, it - s.count) }, false,
                tracked?.let { if (it >= 5) s.lapDistM * s.distScale / it * 3.6 else null }, s.startFallback)
        }
    }

    private fun recordLap(at: Long) {
        val lap = (at - state.lapStartMs!!) / 1000.0
        state.count++; state.lastS = lap
        state.bestS = state.bestS?.let { minOf(it, lap) } ?: lap
        val whole = state.distFromMs == state.lapStartMs // not resumed part way after a restart
        val ratio = Pace.lapDistanceM(config, state.laps.size)?.let { if (whole && state.lapDistM > 0) it / state.lapDistM else null }
        if (ratio != null && ratio in 0.85..1.15) state.distScale = ratio
        state.laps.add(lap)
    }

    private fun started(at: Long) {
        newRaceIfStale(at)
        if (state.finished || state.count > 0) return
        state.raceStartMs = at; state.lapStartMs = at // a later forward crossing (re-start) replaces it
        state.startFallback = null
        onChange(this)
    }

    private fun crossed(at: Long) {
        newRaceIfStale(at)
        if (state.finished) return
        if (config.start != null && state.raceStartMs == null) return startFromControl(at)
        // Started at the control line on the way to the grid, then left the grid with the start line missed again.
        val depart = departMs
        if (state.startFallback == "control" && state.count == 0 && depart != null && depart > state.lapStartMs!!) {
            state.raceStartMs = depart; state.lapStartMs = depart; state.startFallback = "depart"
        }
        val start = state.lapStartMs
        if (start == null) {
            state.lapStartMs = at
            if (state.raceStartMs == null) state.raceStartMs = at
        } else {
            val lap = (at - start) / 1000.0
            if (lap < config.minLapS) return
            if (lap <= config.maxLapS) {
                // Control lines missed in between: share the time out evenly over the laps it held.
                val k = lapsIn(lap)
                for (i in 1..k) {
                    if (i > 1) state.distFromMs = null // the distance belonged to all of them
                    val end = start + (at - start) * i / k
                    recordLap(end)
                    state.lapStartMs = end
                }
            }
            state.lapStartMs = at
            val total = config.totalLaps
            if (total != null && state.count >= total) {
                // The final lap ended at the control line: the goal line was missed, or there is none.
                state.finished = true; state.raceEndMs = at; state.lapStartMs = null
                if (config.goal != null) state.finishFallback = "control"
            }
        }
        onChange(this)
    }

    /** How many laps a control-to-control time of [lap] s holds (1 unless control lines were missed). */
    private fun lapsIn(lap: Double): Int {
        val index = state.laps.size
        val planned = Pace.checkpointS(config, index + 1)?.let { end -> Pace.checkpointS(config, index)?.let { end - it } }
        val expected = planned ?: state.laps.sorted().let { if (it.isEmpty()) null else it[it.size / 2] } ?: return 1
        if (lap < MISSED_LAP_FACTOR * expected) return 1
        var k = Math.round(lap / expected).toInt().coerceAtLeast(2)
        config.totalLaps?.let { k = k.coerceAtMost(maxOf(1, it - state.count)) }
        return k
    }

    /** The start line was missed: start from a departure near it (lap 1 ends here), else from this control crossing. */
    private fun startFromControl(at: Long) {
        val depart = departMs
        if (depart != null && (at - depart) / 1000.0 in config.minLapS..config.maxLapS) {
            state.raceStartMs = depart; state.lapStartMs = depart; state.startFallback = "depart"
            recordLap(at)
        } else {
            state.raceStartMs = at; state.startFallback = "control"
        }
        state.lapStartMs = at
        onChange(this)
    }

    /** Watches for the car standing near the start line and moving off, until the race has a lap. */
    private fun watchDeparture(fix: Fix) {
        val g = config.start ?: return
        val speed = fix.speedKmh ?: return
        val racing = state.finished || state.count > 0 || (state.raceStartMs != null && state.startFallback == null)
        if (racing && !stale(fix.utcMs)) return
        val p = offset(g, fix)
        val d = hypot(p.x, p.y)
        if (speed < STOPPED_KMH && d <= DEPART_NEAR_M) stoppedNearStartMs = fix.utcMs
        else if (speed >= MOVING_KMH) stoppedNearStartMs?.let { departMs = it; nearestStartM = null; stoppedNearStartMs = null }
        if (departMs != null && speed >= MOVING_KMH && d <= DEPART_NEAR_M && d < (nearestStartM ?: Double.MAX_VALUE)) {
            nearestStartM = d; departMs = fix.utcMs
        }
    }

    private fun finished(at: Long) {
        newRaceIfStale(at)
        val start = state.lapStartMs ?: return
        if (state.finished) return
        val total = config.totalLaps
        // Started at the control line (start missed): that pass was most likely the end of lap 1, one lap uncounted.
        val uncounted = if (state.startFallback == "control") 1 else 0
        if (total != null && state.count < total - 1 - uncounted) return
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
        watchDeparture(fix)
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
        if (start != lapBefore) { state.lapDistM = 0.0; state.distFromMs = start }
        // Resumed part way through the lap (the app restarted): average over what is tracked from here.
        if (state.distFromMs == null) { state.lapDistM = 0.0; state.distFromMs = prev.utcMs }
        val from = maxOf(state.distFromMs!!, prev.utcMs)
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
