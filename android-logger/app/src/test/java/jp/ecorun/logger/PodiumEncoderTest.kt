package jp.ecorun.logger

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PodiumEncoderTest {
    @Test
    fun rowSkipsMissingValuesAndSetsMask() {
        val row = PodiumEncoder.row(mapOf("Interval" to 100.0, "Lat" to 35.12345678, "GPSSats" to 9.4))
        // Interval is bit 0, Lat bit 2, GPSSats bit 9.
        assertEquals("[100,35.123457,9,${1 or (1 shl 2) or (1 shl 9)}]", row)
    }

    @Test
    fun nonFiniteValuesAreDropped() {
        assertEquals("[0]", PodiumEncoder.row(mapOf("AccelX" to Double.NaN)))
    }

    @Test
    fun decimalsAreTrimmed() {
        assertEquals("1.5", PodiumEncoder.number(1.5000001, 2))
        assertEquals("-0.01", PodiumEncoder.number(-0.006, 2))
        assertEquals("1729238400123", PodiumEncoder.number(1729238400123.0, 0))
    }

    @Test
    fun metaUsesPodiumPositionNames() {
        val meta = PodiumEncoder.meta()
        assertTrue(meta.startsWith("""{"type":"podium.meta","meta":[{"nm":"Interval","ut":"ms","sr":10,"min":0,"max":0,"prec":0}"""))
        assertTrue(meta.contains(""""nm":"Latitude""""))
        assertTrue(meta.contains(""""nm":"Longitude""""))
    }

    @Test
    fun helloNamesTheLoggerRoleWithoutAudio() {
        assertEquals("""{"type":"hello","client_id":"car \"2\"","protocol":2,"role":"logger","audio_formats":[]}""",
            PodiumEncoder.hello("car \"2\""))
    }
}
