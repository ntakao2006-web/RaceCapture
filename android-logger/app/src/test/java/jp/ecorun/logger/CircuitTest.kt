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
                      video: CircuitVideo? = null, press: Double? = null, rpm: Double? = null) =
        CircuitInput(connected = connected, rec = true, lat = lat0, lon = lon0, speedKmh = speed, currentLap = currentLap,
            elapsedMin = elapsed, lastMin = last, bestMin = best, raceMin = race, diffS = diff, lastPit = lastPit,
            startPit = startPit, oil = oil, water = water, press = press, rpm = rpm, utc = "2026-11-08T02:16:15Z", video = video)

    private fun shown(w: Warnings) = w.active().map { it.label to it.value }

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
        val w = Warnings(CircuitConfig())
        assertFalse(w.update(0.0, 121.0, 100.0))
        assertFalse(w.update(0.5, 121.0, 100.0)); assertFalse(w.on)
        assertTrue(w.update(1.0, 121.0, 100.0)); assertTrue(w.on)
        assertEquals(listOf("油温" to 121.0), shown(w))
        for (t in listOf(1.1, 5.0, 9.0)) assertFalse(w.update(t, 135.0, 100.0)) // no second level, no repeat
        assertEquals(listOf("油温" to 135.0), shown(w))
    }

    @Test
    fun warningOffFiveSecondsAfterAndAShortDipKeepsIt() {
        val w = Warnings(CircuitConfig())
        w.update(0.0, 125.0, 100.0); w.update(1.0, 125.0, 100.0)
        w.update(2.0, 118.0, 100.0)
        assertFalse(w.update(4.0, 124.0, 100.0)); assertTrue(w.on) // back up before 5 s: no new sound
        w.update(5.0, 115.0, 100.0)
        assertFalse(w.update(9.9, 115.0, 100.0)); assertTrue(w.on)
        assertFalse(w.update(10.0, 115.0, 100.0)); assertFalse(w.on)
    }

    @Test
    fun below120NothingAndWaterWarnsWhenTheOilSensorIsLost() {
        val w = Warnings(CircuitConfig())
        w.update(0.0, 119.0, 109.0); w.update(2.0, 119.0, 109.0)
        assertFalse(w.on)
        val w2 = Warnings(CircuitConfig())
        w2.update(0.0, null, 112.0); assertTrue(w2.update(1.0, null, 112.0))
        assertEquals(true to listOf("水温" to 112.0), w2.on to shown(w2))
    }

    @Test
    fun oilPressureLineFollowsTheEngineSpeed() {
        val c = CircuitConfig()
        assertNull(pressLimit(c, null))
        assertNull(pressLimit(c, 900.0))   // idle: 80 kPa hot is normal
        assertNull(pressLimit(c, 1499.0))
        assertEquals(100.0, pressLimit(c, 1500.0)!!, 1e-9)
        assertEquals(150.0, pressLimit(c, 2250.0)!!, 1e-9)
        assertEquals(200.0 to 200.0, pressLimit(c, 3000.0) to pressLimit(c, 7200.0)) // flat above 3000 rpm
        val other = CircuitConfig(oilPressWarn = listOf(2000.0 to 150.0, 4000.0 to 250.0), oilPressMinRpm = 2000.0)
        assertEquals(listOf(null, 200.0, 250.0), listOf(pressLimit(other, 1900.0), pressLimit(other, 3000.0), pressLimit(other, 6000.0)))
    }

    @Test
    fun oilPressureWarnsAfterHalfASecondOnlyWithTheEngineRunning() {
        val w = Warnings(CircuitConfig())
        assertFalse(w.update(0.0, 98.0, 88.0, 0.0, 0.0))      // engine off: 0 kPa, no warning
        assertFalse(w.update(5.0, 98.0, 88.0, 60.0, 1000.0))  // idle
        assertFalse(w.update(9.0, 98.0, 88.0, 60.0, 1000.0)); assertFalse(w.on)
        assertFalse(w.update(10.0, 98.0, 88.0, 150.0, 5000.0))
        assertFalse(w.update(10.4, 98.0, 88.0, 150.0, 5000.0)); assertFalse(w.on)
        assertTrue(w.update(10.5, 98.0, 88.0, 150.0, 5000.0))
        assertEquals(listOf("油圧" to 150.0), shown(w))
        assertFalse(w.update(11.0, 98.0, 88.0, 380.0, 5000.0)); assertTrue(w.on) // off 5 s after
        assertFalse(w.update(16.0, 98.0, 88.0, 380.0, 5000.0)); assertFalse(w.on)
        assertFalse(w.update(20.0, 98.0, 88.0, null, 5000.0)); assertFalse(w.on) // no sensor: nothing
    }

    @Test
    fun warningsSideBySideEachWithItsSound() {
        val w = Warnings(CircuitConfig())
        w.update(0.0, 122.0, 100.0, 380.0, 5000.0)
        assertTrue(w.update(1.0, 122.0, 100.0, 380.0, 5000.0))
        w.update(2.0, 124.0, 104.0, 120.0, 5000.0)
        assertTrue(w.update(2.5, 124.0, 104.0, 120.0, 5000.0)) // the oil pressure comes on: a new sound
        assertEquals(listOf("油圧" to 120.0, "油温" to 124.0), shown(w)) // oil pressure first
        w.update(3.0, 125.0, 111.0, 120.0, 5000.0)
        assertTrue(w.update(4.0, 125.0, 111.0, 120.0, 5000.0))
        assertEquals(listOf("油圧", "油温", "水温"), w.active().map { it.label })
        assertFalse(w.update(4.1, 126.0, 112.0, 110.0, 5000.0)) // all on already: no more sound
    }

    @Test
    fun theBandFlashesForAMinuteAfterEachNewWarning() {
        val w = Warnings(CircuitConfig())
        w.update(0.0, 122.0, 100.0); w.update(1.0, 122.0, 100.0) // the oil comes on at 1.0
        assertTrue(w.flashing(1.0)); assertTrue(w.flashing(60.9))
        assertFalse(w.flashing(61.0)) // then steady red
        w.update(80.0, 122.0, 100.0, 120.0, 5000.0); w.update(80.5, 122.0, 100.0, 120.0, 5000.0) // the oil pressure joins
        assertTrue(w.flashing(80.5)); assertFalse(w.flashing(140.5))
        assertFalse(Warnings(CircuitConfig(flashS = 0.0)).flashing(0.0))
        val m = CircuitModel()
        val states = (0 until 130).map { m.update(frame(oil = 125.0), it * 0.5).first }
        assertEquals(listOf(true, true), states.filter { it.warn }.take(2).map { it.warnFlash })
        assertEquals(true to false, states.last().warn to states.last().warnFlash)
    }

    @Test
    fun theBandListsEveryWarningAndTheSensorLight() {
        val m = CircuitModel()
        var s = m.update(frame(oil = 98.0), 0.0).first
        assertEquals(null to ("油温センサー" to true), s.pressSensor to s.sensor) // oil pressure not wired yet
        for (k in 0 until 12) s = m.update(frame(oil = 123.0, press = 110.0, rpm = 5200.0), 0.1 + k * 0.1).first
        assertEquals(listOf(WarnItem("油圧", "110", "kPa"), WarnItem("油温", "123", "℃")), s.warns)
        assertEquals(true to ("油温・油圧" to true), s.pressSensor to s.sensor)
        s = m.update(frame(oil = 98.0), 2.0).first // the oil pressure lost after it had come
        assertEquals(false to ("油圧センサー途絶" to false), s.pressSensor to s.sensor)
        assertEquals(WarnItem("油圧", "110", "kPa"), s.warns[0]) // last value until it goes off
        assertEquals(listOf("油温センサー途絶" to false, "油温センサー途絶" to false, "油温・油圧途絶" to false),
            listOf(sensorLight(false, null), sensorLight(false, true), sensorLight(false, false)))
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
        assertEquals(listOf<Any?>(true, listOf(WarnItem("油温", "122", "℃")), "PIT OUT"), listOf(s.warn, s.warns, s.notice))
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
    fun toneIsSixBurstsOfAboutTenSeconds() {
        assertEquals(10.25, AlarmTone.samples().size / AlarmTone.RATE.toDouble(), 0.01) // 1.5 s each, 0.25 s apart
        assertEquals(1.5, AlarmTone.samples(repeat = 1).size / AlarmTone.RATE.toDouble(), 0.01)
        val gap = AlarmTone.samples().copyOfRange((AlarmTone.RATE * 1.55).toInt(), (AlarmTone.RATE * 1.7).toInt())
        assertTrue(gap.all { it.toInt() == 0 }) // the break between bursts is silent
        val one = AlarmTone.samples(repeat = 1)
        val rate = AlarmTone.RATE
        // 15 beeps of 0.05 s, each followed by 0.05 s of silence
        for (i in 0 until 15) {
            assertTrue(one.copyOfRange((rate * (i * .1 + .01)).toInt(), (rate * (i * .1 + .04)).toInt()).any { it.toInt() != 0 })
            assertTrue(one.copyOfRange((rate * (i * .1 + .051)).toInt(), (rate * (i * .1 + .099)).toInt()).all { it.toInt() == 0 })
        }
        assertTrue(AlarmTone.samples(volume = 1.0).maxOf { kotlin.math.abs(it.toInt()) } <= 32000) // no clipping
    }
}
