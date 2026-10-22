package jp.ecorun.logger

import kotlin.math.cos
import kotlin.math.hypot

/**
 * Average-speed pacing, which is what eco-run drivers steer by: the regulation
 * distance has to be covered within the regulation time, so after every lap the
 * driver gets the average speed the next lap needs to finish exactly on time
 * (the remaining distance over the remaining time). Driving the previous lap
 * faster than its target lowers the next target, and the reverse. The time
 * aimed at is the limit less [LapConfig.marginS], since finishing even a few
 * seconds late disqualifies.
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

    /** Average speed (km/h) lap [index] needs, given the lap times before it; null once past the limit. */
    fun targetKmh(c: LapConfig, laps: List<Double>, index: Int): Double? {
        val total = c.raceDistanceM ?: return null
        val limit = plannedS(c) ?: return null
        if (lapDistanceM(c, index) == null) return null
        var done = 0.0
        for (k in 0 until index) done += lapDistanceM(c, k) ?: return null
        val left = limit - laps.take(index).sum()
        if (left <= 0) return null
        return (total - done) / left * 3.6
    }

    /** Average speed (km/h) of a finished lap from its regulation distance. */
    fun lapKmh(c: LapConfig, index: Int, seconds: Double): Double? =
        lapDistanceM(c, index)?.let { if (seconds > 0) it / seconds * 3.6 else null }

    /** Seconds ahead (+) of an even pace to the planned finish (margin included) after the first [count] laps. */
    fun bankedS(c: LapConfig, laps: List<Double>, count: Int): Double? {
        val total = c.raceDistanceM ?: return null
        val limit = plannedS(c) ?: return null
        var done = 0.0
        for (k in 0 until count) done += lapDistanceM(c, k) ?: return null
        return done / total * limit - laps.take(count).sum()
    }
}
