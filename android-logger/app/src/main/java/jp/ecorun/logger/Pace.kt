package jp.ecorun.logger

import kotlin.math.cos
import kotlin.math.hypot

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
 * shorter by the goal -> control distance (both measured between the lines).
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

    /** Distance of lap [index] (0 = first) in metres, or null without a regulation distance and lap count. */
    fun lapDistanceM(c: LapConfig, index: Int): Double? {
        val total = c.raceDistanceM ?: return null
        val n = c.totalLaps ?: return null
        if (n <= 0 || index !in 0 until n) return null
        val shortStart = apart(c.start, c.control); val shortGoal = apart(c.goal, c.control)
        val full = (total + shortStart + shortGoal) / n
        var d = full
        if (index == 0) d -= shortStart
        if (index == n - 1) d -= shortGoal
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
}
