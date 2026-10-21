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
