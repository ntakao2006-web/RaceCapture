package jp.ecorun.logger

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PaceTest {
    private val limit = 16 * 60 + 27.36
    private val motegi = Race.MOTEGI.copy(totalLaps = 3, timeLimitS = limit, raceDistanceM = 6856.72)

    @Test
    fun lapDistancesAddUpToTheRegulationDistance() {
        val d = (0 until 3).map { Pace.lapDistanceM(motegi, it)!! }
        assertEquals(6856.72, d.sum(), 1e-6)
        // Standing start before the control line: the first lap is the shortest, then the last (goal before the control).
        val c = motegi.control!!; val s = motegi.start!!
        val startToControl = Math.hypot((c.lon - s.lon) * 111320.0 * Math.cos(Math.toRadians((c.lat + s.lat) / 2)), (c.lat - s.lat) * 111320.0)
        assertEquals(startToControl, d[1] - d[0], 1e-6)
        assert(d[0] < d[2] && d[2] < d[1])
        assertEquals(6856.72 / 3, Pace.lapDistanceM(motegi.copy(start = null, goal = null), 1)!!, 1e-6)
    }

    @Test
    fun firstTargetIsTheEvenPace() {
        assertEquals(6856.72 / limit * 3.6, Pace.targetKmh(motegi, emptyList(), 0)!!, 1e-9)
    }

    /** A slow lap raises the next target, and driving every lap at its target ends exactly on time. */
    @Test
    fun targetsMakeUpTheGap() {
        val first = Pace.targetKmh(motegi, emptyList(), 0)!!
        val slow = Pace.lapDistanceM(motegi, 0)!! / (first / 3.6) + 20
        val second = Pace.targetKmh(motegi, listOf(slow), 1)!!
        assert(second > first)
        val laps = mutableListOf(slow)
        for (k in 1 until 3) laps.add(Pace.lapDistanceM(motegi, k)!! / (Pace.targetKmh(motegi, laps, k)!! / 3.6))
        assertEquals(limit, laps.sum(), 1e-6)
        assertEquals(0.0, Pace.bankedS(motegi, laps, 3)!!, 1e-6)
        assertEquals(-20.0, Pace.bankedS(motegi, listOf(slow), 1)!!, 1e-6)
    }

    /** With a margin, driving every lap at its target ends the margin ahead of the limit. */
    @Test
    fun marginFinishesEarly() {
        val c = motegi.copy(marginS = 30.0)
        assertEquals(6856.72 / (limit - 30) * 3.6, Pace.targetKmh(c, emptyList(), 0)!!, 1e-9)
        val laps = mutableListOf<Double>()
        for (k in 0 until 3) laps.add(Pace.lapDistanceM(c, k)!! / (Pace.targetKmh(c, laps, k)!! / 3.6))
        assertEquals(limit - 30, laps.sum(), 1e-6)
        assertEquals(0.0, Pace.bankedS(c, laps, 3)!!, 1e-6)
    }

    /**
     * The team's record sheet (本番用記録表.xlsx, CN二輪車): 6856.72 m in 3 equal
     * laps, aiming at 16:20 against the 16:27 limit. After a 5:40 first lap the
     * sheet asks 2285.57 m / (10:53 - 5:40) for lap 2 (次目標速度, its checkpoint
     * rounded to the second) and 1142.79 m / (5:27 + 2:43 - 5:40) for its first
     * half (次半周目標速度). The gap (差) is 5:27 - 5:40.
     */
    @Test
    fun matchesTheRecordSheet() {
        val c = LapConfig(totalLaps = 3, timeLimitS = limit, raceDistanceM = 6856.72, marginS = limit - 980.0)
        val laps = listOf(340.0)
        assertEquals(2285.573 / (653 - 340) * 3.6, Pace.targetKmh(c, laps, 1)!!, 0.05)
        // The sheet rounds 5:26.67 to 5:27; that 0.3 s is worth 0.06 km/h over a half lap.
        assertEquals(1142.787 / (327 + 163.33 - 340) * 3.6, Pace.halfTargetKmh(c, laps, 1)!!, 0.1)
        assertEquals(327.0 - 340, Pace.bankedS(c, laps, 1)!!, 0.5)
        assertEquals(2285.573 / 326.667 * 3.6, Pace.targetKmh(c, emptyList(), 0)!!, 1e-3)
    }

    @Test
    fun nothingWithoutADistanceOrPastTheLimit() {
        assertNull(Pace.targetKmh(motegi.copy(raceDistanceM = null), emptyList(), 0))
        assertNull(Pace.targetKmh(motegi, listOf(limit + 1), 1))
        assertNull(Pace.lapDistanceM(motegi, 3))
    }

    /** The running lap distance integrates the GNSS speed and restarts at each control crossing. */
    @Test
    fun lapDistanceFollowsTheSpeed() {
        val north = Gate(36.5, 140.2, 0.0, 30.0)
        val lt = LapTimer(LapConfig(control = north))
        val base = 1_800_000_000_000L
        // 36 km/h = 10 m/s due north, crossing the line at t = 5 s, for 20 s.
        for (t in 0..20) lt.update(Fix(base + t * 1000L, 36.5 + (t - 5) * 10.0 / 111320.0, 140.2, 4.0, 36.0, 0.0), 0)
        assertEquals(150.0, lt.state.lapDistM, 1e-6)
    }
}
