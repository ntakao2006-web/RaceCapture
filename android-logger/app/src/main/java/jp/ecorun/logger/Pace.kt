package jp.ecorun.logger

import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.sin

/**
 * Average-speed pacing, which is what eco-run drivers steer by, following the
 * team's record sheet (本番用記録表.xlsx): the planned finish (the limit less
 * [LapConfig.marginS], since finishing even a few seconds late disqualifies)
 * is split into a checkpoint time at the end of every lap, in proportion to
 * the distance. Each lap's target is the average speed that reaches the next
 * checkpoint from where the car actually is, so any gap is made up within the
 * next lap (the sheet's 次目標速度). [halfTargetKmh] makes it up within the
 * first half instead (次半周目標速度), the second half then running at the plan.
 *
 * Lap distances come from the regulation distance, not from GNSS: a standing
 * start before the control line makes the first lap shorter by the start ->
 * control distance, and a goal before the control line makes the last lap
 * shorter by the goal -> control distance (both measured along the control
 * line's heading, [pastControlM]).
 * The rest of the regulation distance is shared evenly between the laps.
 */
object Pace {
    private const val M_PER_DEG = 111320.0

    private fun apart(a: Gate?, b: Gate?): Double {
        if (a == null || b == null) return 0.0
        return hypot((a.lon - b.lon) * M_PER_DEG * cos(Math.toRadians((a.lat + b.lat) / 2)), (a.lat - b.lat) * M_PER_DEG)
    }

    /** The finishing time the pacing aims at. */
    private fun plannedS(c: LapConfig) = c.timeLimitS?.let { it - c.marginS }

    /**
     * How far [g] lies past the control line along the way the cars go (m; negative before it).
     * 2026-10-25: Motegi's start and goal are in the pit lane beside the main course, and the
     * straight-line gap counted the 29 m across to the goal as 29 m less to drive: the last lap
     * was 26 m short and the outlook read ~4 s too kind (the goal is 2.3 m past the control).
     * Without a heading on the control line, the old guess: the start past it, the goal before it.
     */
    private fun pastControlM(c: LapConfig, g: Gate?, before: Boolean): Double {
        val control = c.control ?: return 0.0
        if (g == null) return 0.0
        val heading = control.bearing ?: return if (before) -apart(g, control) else apart(g, control)
        val east = (g.lon - control.lon) * M_PER_DEG * cos(Math.toRadians((g.lat + control.lat) / 2))
        val north = (g.lat - control.lat) * M_PER_DEG
        val h = Math.toRadians(heading)
        return east * sin(h) + north * cos(h)
    }

    /** Distance of lap [index] (0 = first) in metres, or null without a regulation distance and lap count. */
    fun lapDistanceM(c: LapConfig, index: Int): Double? {
        val total = c.raceDistanceM ?: return null
        val n = c.totalLaps ?: return null
        if (n <= 0 || index !in 0 until n) return null
        // A standing start past the control line shortens lap 1; a goal before it shortens the last lap.
        val start = pastControlM(c, c.start, before = false); val goal = pastControlM(c, c.goal, before = true)
        val full = (total + start - goal) / n
        var d = full
        if (index == 0) d -= start
        if (index == n - 1) d += goal
        return d
    }

    /** Planned time (s) at the end of the first [laps] laps: the sheet's 目標タイム. */
    fun checkpointS(c: LapConfig, laps: Int): Double? {
        val total = c.raceDistanceM ?: return null
        val planned = plannedS(c) ?: return null
        var done = 0.0
        for (k in 0 until laps) done += lapDistanceM(c, k) ?: return null
        return planned * done / total
    }

    /** Average speed (km/h) lap [index] needs to reach its checkpoint, given the lap times before it; null once past it. */
    fun targetKmh(c: LapConfig, laps: List<Double>, index: Int): Double? {
        val d = lapDistanceM(c, index) ?: return null
        val left = (checkpointS(c, index + 1) ?: return null) - laps.take(index).sum()
        return if (left > 0) d / left * 3.6 else null
    }

    /** Average speed (km/h) for the first half of lap [index] that reaches the plan at its half-way point. */
    fun halfTargetKmh(c: LapConfig, laps: List<Double>, index: Int): Double? {
        val d = lapDistanceM(c, index) ?: return null
        val from = checkpointS(c, index) ?: return null
        val to = checkpointS(c, index + 1) ?: return null
        val left = (from + to) / 2 - laps.take(index).sum()
        return if (left > 0) d / 2 / left * 3.6 else null
    }

    /** Average speed (km/h) of a finished lap from its regulation distance. */
    fun lapKmh(c: LapConfig, index: Int, seconds: Double): Double? =
        lapDistanceM(c, index)?.let { if (seconds > 0) it / seconds * 3.6 else null }

    /** Seconds ahead (+) of the checkpoint after the first [count] laps: the sheet's 差. */
    fun bankedS(c: LapConfig, laps: List<Double>, count: Int): Double? =
        checkpointS(c, count)?.let { it - laps.take(count).sum() }

    /**
     * Where the race is heading (2026-10-25): the Super Cub finished 0.2 s over the limit after
     * two laps below their targets, and the screen showed "slow" in the same red as on any lap
     * below a target that has the margin in it. [spareS] is how far inside (+) or over (−) the
     * limit itself the finish comes if the rest of the race is driven at [basisKmh]; [minimumKmh]
     * is the slowest average over the rest that still makes the limit.
     */
    data class Outlook(val spareS: Double, val minimumKmh: Double?, val basisKmh: Double, val fromLastLap: Boolean,
                       /** The lap being driven, 0 = first. */
                       val lap: Int = 0)

    /** This lap's average decides once it has run this long; before that, the lap before's. */
    const val OUTLOOK_AFTER_S = 30.0

    /** Regulation distance (m) still to drive, with [doneInLapM] of lap [index] behind. */
    fun remainingM(c: LapConfig, index: Int, doneInLapM: Double): Double? {
        val n = c.totalLaps ?: return null
        if (index !in 0 until n) return null
        var left = 0.0
        for (k in index until n) left += lapDistanceM(c, k) ?: return null
        return maxOf(0.0, left - minOf(doneInLapM, lapDistanceM(c, index)!!))
    }

    /** [Outlook] for the lap being driven, or null before the start, after the goal, or without the regulation. */
    fun outlook(c: LapConfig, laps: List<Double>, v: LapValues?): Outlook? {
        if (v == null || v.finished || v.current == 0) return null
        val limit = c.timeLimitS ?: return null
        val race = v.raceS ?: return null
        val elapsed = v.elapsedS ?: return null
        val index = v.count
        val lapAvg = v.avgKmh
        val lastAvg = if (index > 0 && laps.size >= index) lapKmh(c, index - 1, laps[index - 1]) else null
        val fromLastLap = lapAvg == null || elapsed < OUTLOOK_AFTER_S
        val basis = (if (fromLastLap) lastAvg else lapAvg) ?: return null
        if (basis <= 0) return null
        val left = remainingM(c, index, (lapAvg ?: basis) / 3.6 * elapsed) ?: return null
        val time = limit - race
        return Outlook(limit - (race + left / (basis / 3.6)), if (time > 0) left / time * 3.6 else null, basis, fromLastLap, index)
    }

    /**
     * Lap 1 raises the overrun alarm only this far over (2026-10-26, ER-13): with no lap before
     * to go by, its own average decides, and the slow part of Motegi's lap 1 read up to 3 s over
     * for a minute in a lap that ended 5 s ahead (GNSS distance is good to ~3 s a lap anyway).
     */
    const val FIRST_LAP_ALARM_S = 5.0
    /** Back inside the alarm's line by this much before it goes off, so it does not flicker. */
    const val ALARM_CLEAR_S = 2.0

    /** Whether the overrun alarm (the red frame) is on, given whether it [wasOn]. */
    fun overrun(o: Outlook?, wasOn: Boolean): Boolean {
        if (o == null) return false
        val line = if (o.lap == 0) -FIRST_LAP_ALARM_S else 0.0
        return o.spareS < line || (wasOn && o.spareS < line + ALARM_CLEAR_S)
    }
}
