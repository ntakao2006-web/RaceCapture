package jp.ecorun.logger

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File
import kotlin.math.cos
import kotlin.math.sin

/**
 * [Pace.outlook] (2026-10-25, ER-13): the Super Cub finished 16:27.56 against the 16:27.36 limit.
 * Replaying that race, the outlook has to say "over the limit" early in lap 2, not at the goal.
 */
class OutlookTest {
    private val limit = 16 * 60 + 27.36

    /**
     * The lines of that race (reference 0115) as far as the pacing sees them: the control line
     * heading 154.2 deg, the start 293.2 m past it (38.1 m to the side, in the pit lane) and the
     * goal 2.3 m past it (28.6 m to the side). Placed around an arbitrary point, since only the
     * distances count (the real positions stay out of the repository).
     */
    private fun at(along: Double, side: Double): Gate {
        val c = Race.MOTEGI.control!!; val h = Math.toRadians(154.2)
        val east = along * sin(h) + side * cos(h); val north = along * cos(h) - side * sin(h)
        return Gate(c.lat + north / 111320.0, c.lon + east / (111320.0 * cos(Math.toRadians(c.lat))), 154.2, 30.0)
    }
    private val race0115 = LapConfig(control = at(0.0, 0.0), start = at(293.2, 38.1), goal = at(2.3, 28.6),
        totalLaps = 3, timeLimitS = limit, raceDistanceM = 6856.72, marginS = 30.0)

    /** Laps from the lines along the way the cars go: the last lap is 2.3 m longer, not 29 m shorter. */
    @Test
    fun lapDistancesFollowTheControlHeading() {
        val d = (0 until 3).map { Pace.lapDistanceM(race0115, it)!! }
        assertEquals(6856.72, d.sum(), 1e-6)
        assertEquals(293.2, d[1] - d[0], 0.05)
        assertEquals(2.3, d[2] - d[1], 0.05)
        // Without a heading on the control line, the straight-line guess as before.
        val noHeading = race0115.copy(control = race0115.control!!.copy(bearing = null))
        assertEquals(Math.hypot(293.2, 38.1), Pace.lapDistanceM(noHeading, 1)!! - Pace.lapDistanceM(noHeading, 0)!!, 0.05)
    }

    private fun values(count: Int, elapsed: Double, race: Double, avg: Double?) =
        LapValues(count, count + 1, null, null, elapsed, race, 3 - count, false, avg)

    /** Every lap at the even pace that aims for the margin: the outlook is the margin, all along. */
    @Test
    fun evenPaceKeepsTheMargin() {
        val v = 6856.72 / (limit - 30) * 3.6
        val laps = (0 until 2).map { Pace.lapDistanceM(race0115, it)!! / (v / 3.6) }
        for ((count, elapsed) in listOf(0 to 40.0, 1 to 120.0, 2 to 300.0)) {
            val o = Pace.outlook(race0115, laps, values(count, elapsed, laps.take(count).sum() + elapsed, v))!!
            assertEquals(30.0, o.spareS, 1e-6)
            assertTrue(o.minimumKmh!! < v)
        }
    }

    /** In a lap's first 30 s the lap before decides (this lap's average is still noise). */
    @Test
    fun earlyInALapTheLastLapDecides() {
        val laps = listOf(287.9)
        val o = Pace.outlook(race0115, laps, values(1, 10.0, 297.9, 40.0))!!
        assertTrue(o.fromLastLap)
        assertEquals(Pace.lapKmh(race0115, 0, 287.9)!!, o.basisKmh, 1e-9)
        // On lap 1 there is no lap before: nothing until 30 s in.
        assertNull(Pace.outlook(race0115, emptyList(), values(0, 10.0, 10.0, 30.0)))
        assertNotNull(Pace.outlook(race0115, emptyList(), values(0, 30.0, 30.0, 30.0)))
    }

    @Test
    fun nothingBeforeTheStartOrAfterTheGoal() {
        assertNull(Pace.outlook(race0115, emptyList(), LapValues(0, 0, null, null, null, null, 3, false)))
        assertNull(Pace.outlook(race0115, listOf(1.0, 2.0, 3.0), LapValues(3, 3, null, null, null, 987.0, 0, true)))
        assertNull(Pace.outlook(race0115.copy(timeLimitS = null), emptyList(), values(0, 60.0, 60.0, 25.0)))
        // Past the limit: still the overrun, but no speed makes it any more.
        val o = Pace.outlook(race0115, listOf(300.0, 360.0), values(2, 340.0, limit + 1, 24.0))!!
        assertTrue(o.spareS < 0)
        assertNull(o.minimumKmh)
    }

    /** Crossing times of 2026-10-25 from the start (s): control, control, goal. */
    private val passes = listOf(287.855, 640.805, 987.564)

    /**
     * The race replayed once a second from its speed record (supercub_20261025_speed.csv, made by
     * tools/race_replay/race_csv.py), with the lap distance integrated and scaled the way
     * [LapTimer] does, and the lap times it counted.
     */
    private fun replay(): List<Pair<Int, Pace.Outlook?>> {
        val speed = javaClass.getResource("/supercub_20261025_speed.csv")!!.readText().lines().drop(1)
            .filter { it.isNotBlank() }.map { it.split(",")[1].toDouble() }
        val out = ArrayList<Pair<Int, Pace.Outlook?>>()
        var dist = 0.0; var scale = 1.0
        for (s in 1 until speed.size) {
            val count = passes.count { it <= s }
            if (count == 3) break
            val lapStart = if (count == 0) 0.0 else passes[count - 1]
            if (s - 1 < lapStart) {
                val whole = (dist + (speed[s - 1] + speed[s]) / 2 / 3.6 * (lapStart - (s - 1)))
                val ratio = Pace.lapDistanceM(race0115, count - 1)!! / whole
                if (ratio in 0.85..1.15) scale = ratio
                dist = (speed[s - 1] + speed[s]) / 2 / 3.6 * (s - lapStart)
            } else dist += (speed[s - 1] + speed[s]) / 2 / 3.6
            val elapsed = s - lapStart
            val laps = passes.take(count).mapIndexed { k, t -> t - (if (k == 0) 0.0 else passes[k - 1]) }
            out.add(s to Pace.outlook(race0115, laps, values(count, elapsed, s.toDouble(), if (elapsed >= 5) dist * scale / elapsed * 3.6 else null)))
        }
        return out
    }

    @Test
    fun theSuperCubRaceShowsTheOverrunInLap2() {
        val run = replay()
        // Lap 1 ended ahead of the limit. Its slow middle (2:39-3:18, ~20 km/h for a minute)
        // read just over the limit for a while: by at most a couple of seconds, inside the yellow.
        assertTrue(run.first { it.first == 287 }.second!!.spareS > 0)
        assertTrue(run.filter { it.first < 288 }.all { (it.second?.spareS ?: 0.0) > -3 })
        // The overrun shows within 2 minutes of lap 2 (about 6:20)...
        val first = run.first { it.first >= 288 && (it.second?.spareS ?: 1.0) < 0 }.first
        assertTrue("first overrun at $first s", first in 289..420)
        // ...and holds to the goal: the alarm would have stayed on for the last 10 minutes.
        assertTrue(run.filter { it.first >= first }.all { it.second!!.spareS < 0 })
        // Just before the goal it read 0.8 s over; the race ended 0.2 s over.
        assertEquals(-0.2, run.last().second!!.spareS, 1.0)
        // Lap 3 needed 24.8 km/h just to make the limit and its average never got there: the tile
        // read red ("規定に間に合わない") all lap, not merely "slow".
        assertEquals(24.77, run.first { it.first == 641 }.second!!.minimumKmh!!, 0.05)
        assertTrue(run.filter { it.first >= 641 + 30 }.all { it.second!!.basisKmh < it.second!!.minimumKmh!! })
    }

    /**
     * The same race through [LapTimer] itself from the recorded fixes: runs only where the race
     * record is (drive_logs/ holds positions and is kept out of the repository).
     */
    @Test
    fun theSuperCubRaceThroughTheLapTimer() {
        val root = File(System.getProperty("user.dir")!!).let { if (File(it, "drive_logs").isDirectory) it else it.parentFile.parentFile }
        val fixes = File(root, "drive_logs/20261025_race_server/supercub_fixes.csv")
        val lines = File(root, "drive_logs/lap_backup_20261025/lap_restore_motegi.json")
        assumeTrue(fixes.isFile && lines.isFile)
        val json = lines.readText()
        fun gate(prefix: String): Gate {
            val m = Regex(prefix + """"lat": ([\d.]+), "lon": ([\d.]+), "bearing": ([\d.]+), "width_m": ([\d.]+)""").find(json)!!
            val (lat, lon, b, w) = m.destructured
            return Gate(lat.toDouble(), lon.toDouble(), b.toDouble(), w.toDouble())
        }
        val config = race0115.copy(control = gate("""\{"enabled": true, """), start = gate(""""start": \{"""), goal = gate(""""goal": \{"""))
        val lt = LapTimer(config)
        var firstOver: Double? = null
        for (row in fixes.readLines().drop(1)) {
            val c = row.split(",")
            val fix = Fix(c[0].toLong(), c[1].toDouble(), c[2].toDouble(), c[3].toDoubleOrNull(), c[4].toDouble())
            lt.update(fix, fix.utcMs)
            val v = lt.values(fix.utcMs)
            val o = Pace.outlook(config, lt.state.laps, v)
            if (firstOver == null && v.count >= 1 && o != null && o.spareS < 0) firstOver = v.raceS
        }
        assertTrue(lt.state.finished)
        assertEquals(3, lt.state.count)
        assertEquals(987.56, (lt.state.raceEndMs!! - lt.state.raceStartMs!!) / 1000.0, 1.5)
        assertTrue("first overrun at $firstOver s", firstOver!! in 289.0..420.0)
    }
}
