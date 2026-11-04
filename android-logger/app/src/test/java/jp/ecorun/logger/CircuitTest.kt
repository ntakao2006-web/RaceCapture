package jp.ecorun.logger

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

/** The same cases as RaceCapture-UNOQ/test_dash_model.py, so the phone and the DASH show the same. */
class CircuitTest {
    private val lat0 = 38.14; private val lon0 = 140.77; private val radius = 400.0

    private fun onCircle(fraction: Double): Pair<Double, Double> {
        val a = 2 * PI * fraction
        return (lat0 + radius * sin(a) / 111320.0) to (lon0 + radius * cos(a) / (111320.0 * cos(Math.toRadians(lat0))))
    }

    private fun frame(oil: Double? = 98.0, water: Double? = 88.0, connected: Boolean = true, speed: Double? = null,
                      currentLap: Double? = null, elapsed: Double? = null, last: Double? = null, best: Double? = null,
                      race: Double? = null, diff: Double? = null, lastPit: Boolean = false, startPit: Boolean = false,
                      video: CircuitVideo? = null) =
        CircuitInput(connected = connected, rec = true, lat = lat0, lon = lon0, speedKmh = speed, currentLap = currentLap,
            elapsedMin = elapsed, lastMin = last, bestMin = best, raceMin = race, diffS = diff, lastPit = lastPit,
            startPit = startPit, oil = oil, water = water, utc = "2026-11-08T02:16:15Z", video = video)

    @Test
    fun times() {
        assertEquals("1:52.34", CircuitFormat.lap(112.34))
        assertEquals("1:12.3", CircuitFormat.lap(72.39, 1)) // cut, never rounded up to the next tenth
        assertEquals("0:05.00", CircuitFormat.lap(5.0))
        assertEquals("--", CircuitFormat.lap(null))
        assertEquals("0:36:15", CircuitFormat.hms(2175.0))
        assertEquals("2:02:02", CircuitFormat.hms(7322.9))
    }

    @Test
    fun signed() {
        assertEquals("+0.41", CircuitFormat.signed(0.41))
        assertEquals("−0.84", CircuitFormat.signed(-0.84))
        assertEquals("0.00", CircuitFormat.signed(0.001))
        assertEquals("+38.4", CircuitFormat.signed(38.42))
        assertEquals("−123", CircuitFormat.signed(-123.4))
        assertEquals("--", CircuitFormat.signed(null))
    }

    @Test
    fun clockFromTheLoggerTimeInJapan() {
        assertEquals("11:16", CircuitFormat.CLOCK.format(CircuitFormat.utc("2026-11-08T02:16:15Z")))
        assertEquals("16:33", CircuitFormat.CLOCK.format(CircuitFormat.utc("2026-11-04T07:33:12.123456+00:00"))) // host_utc
        assertNull(CircuitFormat.utc("nonsense"))
    }

    @Test
    fun warningOnAfterOneSecondWithOneSound() {
        val w = TempWarning(CircuitConfig())
        assertFalse(w.update(0.0, 121.0, 100.0))
        assertFalse(w.update(0.5, 121.0, 100.0)); assertFalse(w.on)
        assertTrue(w.update(1.0, 121.0, 100.0)); assertTrue(w.on)
        assertEquals("油温" to 121.0, w.label to w.value)
        for (t in listOf(1.1, 5.0, 9.0)) assertFalse(w.update(t, 135.0, 100.0)) // no second level, no repeat
        assertEquals(135.0, w.value)
    }

    @Test
    fun warningOffFiveSecondsAfterAndAShortDipKeepsIt() {
        val w = TempWarning(CircuitConfig())
        w.update(0.0, 125.0, 100.0); w.update(1.0, 125.0, 100.0)
        w.update(2.0, 118.0, 100.0)
        assertFalse(w.update(4.0, 124.0, 100.0)); assertTrue(w.on) // back up before 5 s: no new sound
        w.update(5.0, 115.0, 100.0)
        assertFalse(w.update(9.9, 115.0, 100.0)); assertTrue(w.on)
        assertFalse(w.update(10.0, 115.0, 100.0)); assertFalse(w.on)
    }

    @Test
    fun below120NothingAndWaterWarnsWhenTheOilSensorIsLost() {
        val w = TempWarning(CircuitConfig())
        w.update(0.0, 119.0, 109.0); w.update(2.0, 119.0, 109.0)
        assertFalse(w.on)
        val w2 = TempWarning(CircuitConfig())
        w2.update(0.0, null, 112.0); assertTrue(w2.update(1.0, null, 112.0))
        assertEquals(Triple(true, "水温", 112.0), Triple(w2.on, w2.label, w2.value))
    }

    /** Laps of the given durations round the circle; LapTime/BestLap as lap.py reports them. */
    private fun drive(ref: LapRef, laps: List<Double>, hz: Double = 10.0, until: Double? = null) {
        val times = ArrayList<Double>(); var best: Double? = null
        for ((k0, lapS) in laps.withIndex()) {
            val k = k0 + 1
            for (j in 0 until (lapS * hz).toInt()) {
                val el = j / hz
                if (until != null && k == laps.size && el > until) return
                val (lat, lon) = onCircle(el / lapS)
                ref.update(lat, lon, k.toDouble(), el, times.lastOrNull(), best)
            }
            times.add(lapS); best = times.min()
        }
    }

    @Test
    fun gapToTheBestLapAtTheSamePlace() {
        val ref = LapRef()
        drive(ref, listOf(100.0, 110.0), until = 50.0)
        assertNotNull(ref.ref); assertEquals(1, ref.ref!!.no)
        assertEquals(50.0 * (1 - 100 / 110.0), ref.delta!!, 0.15)
    }

    @Test
    fun aSlowerLapDoesNotReplaceTheBestAndTheFileSurvives() {
        val dir = Files.createTempDirectory("lapref").toFile()
        try {
            val file = File(dir, "lapref.txt")
            val ref = LapRef(file)
            drive(ref, listOf(100.0, 104.0, 98.0, 101.0), until = 40.0)
            assertEquals(3, ref.ref!!.no)
            assertEquals(40.0 * (1 - 98 / 101.0), ref.delta!!, 0.15)
            val again = LapRef(file)
            assertEquals(3, again.ref!!.no)
            val (lat, lon) = onCircle(0.25)
            assertEquals(26.0 - 24.5, again.update(lat, lon, 9.0, 26.0, 101.0, 98.0)!!, 0.15)
            assertNull(again.update(lat, lon, 9.0, 26.0, 101.0, 97.0)) // best changed (reset): not this track
        } finally { dir.deleteRecursively() }
    }

    @Test
    fun farFromTheTrackGivesNoGap() {
        val ref = LapRef()
        drive(ref, listOf(100.0, 105.0), until = 10.0)
        assertNotNull(ref.delta)
        assertNull(ref.update(lat0 + 0.01, lon0, 2.0, 11.0, 100.0, 100.0))
    }

    @Test
    fun screenValues() {
        val m = CircuitModel()
        val (s, _) = m.update(frame(currentLap = 23.0, elapsed = 72.3 / 60, last = 112.34 / 60, best = 111.12 / 60,
            race = 2175 / 60.0, diff = 0.41), 0.0)
        assertEquals(listOf("1:12.3", "1:52.34", "1:51.12", "23", "0:36:15", "11:16"),
            listOf(s.lapNow, s.last, s.best, s.lapNo, s.elapsed, s.clock))
        assertEquals("前周比 +0.41s" to Kind.SLOWER, s.lastNote to s.lastNoteKind)
        assertEquals("" to false, s.notice to s.warn)
        assertTrue(s.rec && s.gnss && s.oilSensor && !s.stale)
        assertEquals("" to null, s.video to s.videoKind) // an EcoCapture without the video summary
    }

    @Test
    fun videoLight() {
        val m = CircuitModel()
        var s = m.update(frame(video = CircuitVideo(true, 108.0)), 0.0).first
        assertEquals("録画 1:48" to Kind.WARN, s.video to s.videoKind) // short of a 120-minute race
        s = m.update(frame(video = CircuitVideo(true, 150.0)), 0.1).first
        assertEquals("録画 2:30" to Kind.OK, s.video to s.videoKind)
        s = m.update(frame(video = CircuitVideo(false, 150.0)), 0.2).first
        assertEquals("録画なし" to Kind.WARN, s.video to s.videoKind)
    }

    @Test
    fun waitingPitLostAndStale() {
        val m = CircuitModel()
        var s = m.update(frame(oil = null, currentLap = 0.0), 0.0).first
        assertEquals(listOf(CircuitState.WAITING, "--", "--"), listOf(s.elapsed, s.lapNow, s.lapNo))
        assertFalse(s.oilSensor)
        s = m.update(frame(currentLap = 8.0, last = 3.7, lastPit = true), 0.1).first
        assertEquals("PIT" to Kind.PIT, s.lastNote to s.lastNoteKind)
        s = m.update(null, 2.0).first; assertFalse(s.stale)
        s = m.update(null, 2.2).first; assertTrue(s.stale); assertEquals(2.1, s.staleS!!, 1e-9)
        s = m.update(frame(connected = false), 3.0).first; assertTrue(s.stale)
    }

    @Test
    fun aPitStopIsNotShownAsAWarning() {
        // what the pit lane, 11 m from the track, would give
        val m = CircuitModel(lapRef = object : LapRef() {
            override fun update(lat0: Double?, lon0: Double?, lapNo: Double?, elapsedS: Double?, lastS: Double?, bestS: Double?) = 41.5
        })
        var s = m.update(frame(currentLap = 9.0, elapsed = 0.5, speed = 120.0), 0.0).first
        assertEquals(Triple("+41.5", Kind.SLOWER, ""), Triple(s.delta, s.deltaKind, s.notice))
        s = m.update(frame(currentLap = 9.0, elapsed = 0.5, speed = 0.0, startPit = true, lastPit = true), 0.1).first // stopped in the box, past the line
        assertEquals("--" to "PIT IN", s.delta to s.notice)
        s = m.update(frame(currentLap = 9.0, elapsed = 0.5, speed = 120.0, startPit = true, lastPit = true), 0.2).first // the out lap
        assertEquals(listOf("--", null, null, "PIT OUT"), listOf(s.delta, s.deltaKind, s.deltaFrac, s.notice))
        assertEquals(Triple("PIT", Kind.PIT, false), Triple(s.lastNote, s.lastNoteKind, s.warn))
        s = m.update(frame(currentLap = 9.0, elapsed = 0.5, speed = 3.0), 0.3).first // stopped on the in lap: nothing known yet
        assertEquals("--" to "", s.delta to s.notice)
    }

    @Test
    fun theTemperatureWarningIsApartFromThePitStrip() {
        val m = CircuitModel()
        val out = { t: Double -> m.update(frame(oil = 122.0, currentLap = 9.0, elapsed = 0.5, startPit = true, lastPit = true), t) }
        val sounds = (0 until 12).map { out(it * 0.1).second }
        val s = out(1.2).first
        assertEquals(listOf<Any?>(true, "油温", "122℃", "PIT OUT"), listOf(s.warn, s.warnLabel, s.warnValue, s.notice))
        assertEquals(1, sounds.count { it })
    }

    @Test
    fun noWarningFromValuesOfADeadLink() {
        val m = CircuitModel()
        m.update(frame(oil = 135.0), 0.0)
        val (s, sound) = m.update(frame(oil = 135.0, connected = false), 1.5)
        assertEquals(false to false, s.warn to sound)
    }

    @Test
    fun toneLastsTwoSeconds() {
        assertEquals(2.0, AlarmTone.samples().size / AlarmTone.RATE.toDouble(), 0.01)
    }
}
