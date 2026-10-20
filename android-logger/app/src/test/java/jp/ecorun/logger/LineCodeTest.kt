package jp.ecorun.logger

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Test

class LineCodeTest {
    private val lines = "c=36.5328000,140.2263220,150.0,40|s=36.5307300,140.2280570,-,30|g=-"

    private fun code(l: String = lines) = "ECOLINES1|$l|at=2026-10-24T06:40+09:00|src=Ver.2|id=${LineCode.id(l)}"

    @Test
    fun readsTheLinesAndKeepsTheClassSettings() {
        val ref = LineCode.parse(code(), LapConfig(totalLaps = 3, timeLimitS = 987.36, minLapS = 12.0))
        assertEquals(Gate(36.5328, 140.226322, 150.0, 40.0), ref.config.control)
        assertEquals(Gate(36.53073, 140.228057, null, 30.0), ref.config.start)
        assertNull(ref.config.goal)
        assertEquals(3, ref.config.totalLaps)
        assertEquals(12.0, ref.config.minLapS, 0.0)
        assertEquals("2026-10-24T06:40+09:00", ref.at)
        assertEquals("Ver.2", ref.source)
        assertEquals(LineCode.id(lines), ref.id)
    }

    /** Same digest as Python: hashlib.sha1(lines.encode()).hexdigest()[:4].upper() */
    @Test
    fun idMatchesPython() {
        assertEquals("A9993E".take(4), LineCode.id("abc"))
    }

    /** Fixed in EcoCapture-Web test_lap.py LineCodeTest as well: both sides must agree. */
    @Test
    fun idMatchesTheVer2Side() {
        assertEquals("1600", LineCode.id(lines))
    }

    @Test
    fun aChangedValueIsRejected() {
        val tampered = code().replace("150.0", "151.0")
        assertThrows(LineCode.Invalid::class.java) { LineCode.parse(tampered, LapConfig()) }
    }

    @Test
    fun otherQrCodesAreRejected() {
        assertThrows(LineCode.Invalid::class.java) { LineCode.parse("https://example.com", LapConfig()) }
        assertThrows(LineCode.Invalid::class.java) { LineCode.parse(code("c=-|s=-|g=-"), LapConfig()) }
        assertThrows(LineCode.Invalid::class.java) { LineCode.parse(code("c=99,140,-,30|s=-|g=-"), LapConfig()) }
    }
}
