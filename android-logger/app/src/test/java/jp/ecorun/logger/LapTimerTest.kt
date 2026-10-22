package jp.ecorun.logger

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class LapTimerTest {
    private val lat0 = 36.5
    private val lon0 = 140.2
    private val mPerDegLat = 111320.0

    /** A fix [northM] metres north of the line centre at time [t] seconds, heading north. */
    private fun fix(t: Double, northM: Double, kmh: Double? = 20.0, yaw: Double? = 0.0, acc: Double? = 4.0) =
        Fix((1_800_000_000_000L + t * 1000).toLong(), lat0 + northM / mPerDegLat, lon0, acc, kmh, yaw)

    private fun timer(config: LapConfig) = LapTimer(config)

    private fun LapTimer.feed(vararg fixes: Fix) = fixes.forEach { update(it, it.utcMs) }

    /** Crosses the line northwards at time [t] (+-1 s), then drives away to re-arm. */
    private fun LapTimer.pass(t: Double) = feed(fix(t - 0.5, -5.0), fix(t + 0.5, 5.0), fix(t + 1.5, 40.0))

    private val north = Gate(lat0, lon0, bearing = 0.0, widthM = 30.0)

    @Test
    fun countsLapsOnADirectedLine() {
        val lt = timer(LapConfig(control = north))
        lt.pass(0.0); lt.pass(60.0); lt.pass(125.0)
        assertEquals(2, lt.state.count)
        assertEquals(65.0, lt.state.lastS!!, 0.01)
        assertEquals(60.0, lt.state.bestS!!, 0.01)
    }

    @Test
    fun wrongDirectionDoesNotCount() {
        val lt = timer(LapConfig(control = north))
        lt.pass(0.0)
        lt.feed(fix(59.5, 5.0), fix(60.5, -5.0), fix(61.5, -40.0)) // southwards
        assertEquals(0, lt.state.count)
    }

    @Test
    fun jitterOnTheLineDoesNotAddLaps() {
        val lt = timer(LapConfig(control = north, minLapS = 5.0))
        lt.feed(fix(-0.5, -5.0), fix(0.5, 5.0))
        // Still near the line (never a width away): stays disarmed.
        lt.feed(fix(20.0, -3.0), fix(21.0, 3.0), fix(22.0, -3.0), fix(23.0, 3.0))
        assertEquals(0, lt.state.count)
    }

    @Test
    fun shortLapIsIgnored() {
        val lt = timer(LapConfig(control = north, minLapS = 10.0))
        lt.pass(0.0); lt.pass(6.0)
        assertEquals(0, lt.state.count)
        lt.pass(30.0)
        assertEquals(1, lt.state.count)
        assertEquals(30.0, lt.state.lastS!!, 0.01)
    }

    @Test
    fun learnsTheDirectionOnTheFirstPass() {
        val lt = timer(LapConfig(control = north.copy(bearing = null)))
        lt.feed(fix(0.0, -20.0), fix(1.0, -5.0), fix(2.0, 5.0), fix(3.0, 20.0))
        assertEquals(0.0, lt.config.control!!.bearing!!, 0.001)
        assertEquals(1_800_000_001_500L, lt.state.lapStartMs) // interpolated between 1 s and 2 s
    }

    @Test
    fun fixesTooFarApartAreNotJoined() {
        val lt = timer(LapConfig(control = north))
        lt.feed(fix(0.0, -5.0), fix(2.0, 5.0))
        assertNull(lt.state.lapStartMs)
    }

    @Test
    fun poorAccuracyFixIsSkipped() {
        val lt = timer(LapConfig(control = north))
        lt.feed(fix(0.0, -5.0), fix(1.0, 5.0, acc = 40.0))
        assertNull(lt.state.lapStartMs)
    }

    @Test
    fun startLineStartsTheRaceAndControlBeforeItIsIgnored() {
        val start = Gate(lat0 - 200 / mPerDegLat, lon0, bearing = 0.0)
        val lt = timer(LapConfig(control = north, start = start))
        lt.pass(0.0)
        assertNull(lt.state.raceStartMs)
        lt.feed(fix(10.0, -205.0), fix(11.0, -195.0))
        assertEquals(1_800_000_010_500L, lt.state.raceStartMs)
        lt.pass(70.0) // start to first control pass is lap 1
        assertEquals(1, lt.state.count)
        assertEquals(59.5, lt.state.lastS!!, 0.01)
    }

    @Test
    fun goalIsIgnoredUntilTheFinalLap() {
        val goal = Gate(lat0 + 300 / mPerDegLat, lon0, bearing = 0.0)
        val lt = timer(LapConfig(control = north, goal = goal, totalLaps = 3))
        fun crossGoal(t: Double) = lt.feed(fix(t - 0.5, 295.0), fix(t + 0.5, 305.0), fix(t + 1.5, 340.0))
        lt.pass(0.0)
        crossGoal(30.0)
        assertFalse(lt.state.finished)
        lt.pass(60.0); lt.pass(120.0)
        crossGoal(150.0)
        assertTrue(lt.state.finished)
        assertEquals(3, lt.state.count)
        assertEquals(150.0, (lt.state.raceEndMs!! - lt.state.raceStartMs!!) / 1000.0, 0.01)
        val v = lt.values(0)
        assertEquals(0, v.lapsLeft)
        assertTrue(v.finished)
    }

    @Test
    fun runningClocksAdvanceFromTheLastFix() {
        val lt = timer(LapConfig(control = north))
        lt.pass(0.0)
        val lastMono = lt.latest!!.second
        val v = lt.values(lastMono + 2000)
        assertEquals(1, v.current)
        assertEquals(3.5, v.elapsedS!!, 0.01) // last fix at +1.5 s, crossing at 0 s, plus 2 s
    }

    /**
     * Three-lap race on the Motegi lines (Race.MOTEGI): south along the west
     * straight through each line, the goal on the final lap before the control.
     */
    @Test
    fun threeLapRaceOnTheMotegiLines() {
        val cfg = LapConfig(
            control = Gate(36.532800, 140.226322, 150.0, 40.0),
            start = Gate(36.530730, 140.228057, 150.0, 40.0),
            goal = Gate(36.533566, 140.226005, 150.0, 40.0),
            totalLaps = 3, timeLimitS = 16 * 60 + 27.36)
        val lt = LapTimer(cfg)
        val base = 1_800_000_000_000L
        // Drive 7 m/s along 150 deg through [g], from 20 m before to 20 m after it, 8 m off its centre.
        fun through(g: Gate, t0: Double) {
            val mLat = 1 / 111320.0; val mLon = 1 / (111320.0 * Math.cos(Math.toRadians(g.lat)))
            val n = Math.cos(Math.toRadians(150.0)); val e = Math.sin(Math.toRadians(150.0))
            for (k in -3..3) {
                val d = k * 7.0
                val lat = g.lat + (d * n + 8 * -e) * mLat; val lon = g.lon + (d * e + 8 * n) * mLon
                lt.update(Fix(base + ((t0 + k) * 1000).toLong(), lat, lon, 4.0, 25.0, 150.0), 0)
            }
        }
        // Waiting on the grid a few metres before the start line: jitter must not start the clock early.
        through(cfg.start!!, 0.0)   // a jitter "crossing" while waiting
        through(cfg.start, 60.0)    // the real departure
        assertEquals(base + 60_000, lt.state.raceStartMs)
        through(cfg.goal!!, 360.0); through(cfg.control!!, 373.0)   // lap 1
        through(cfg.goal, 693.0); through(cfg.control, 706.0)       // lap 2: goal ignored
        assertEquals(2, lt.state.count)
        assertFalse(lt.state.finished)
        through(cfg.goal, 1020.0)                                  // lap 3 ends at the goal
        assertTrue(lt.state.finished)
        assertEquals(3, lt.state.count)
        assertEquals(960.0, (lt.state.raceEndMs!! - lt.state.raceStartMs!!) / 1000.0, 0.01)
        assertEquals(listOf(313.0, 333.0, 314.0), lt.state.laps.map { Math.round(it).toDouble() })
    }
}
