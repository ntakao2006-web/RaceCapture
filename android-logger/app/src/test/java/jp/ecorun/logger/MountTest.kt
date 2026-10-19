package jp.ecorun.logger

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.cos
import kotlin.math.sin

class MountTest {
    private val g = Mount.G

    private fun rows(m: Mount, accel: DoubleArray, n: Int, speedKmh: Double? = 0.0) =
        repeat(n) { m.onRow(accel, doubleArrayOf(0.0, 0.0, 0.0), speedKmh) }

    private fun near(expected: DoubleArray, actual: DoubleArray, tol: Double) =
        (0..2).forEach { assertEquals(expected[it], actual[it], tol) }

    /** Landscape on the dash, screen facing the driver, phone X pointing up. */
    private val upX = doubleArrayOf(1.0, 0.0, 0.0)

    @Test
    fun autoCalibrationNeedsTwoStillSeconds() {
        val m = Mount()
        rows(m, doubleArrayOf(g, 0.0, 0.0), 19)
        assertNull(m.up)
        rows(m, doubleArrayOf(g, 0.0, 0.0), 1)
        near(upX, m.up!!, 1e-9)
    }

    @Test
    fun noAutoCalibrationWithoutGnssSpeedOrWhileMoving() {
        val m = Mount()
        rows(m, doubleArrayOf(g, 0.0, 0.0), 40, speedKmh = null)
        rows(m, doubleArrayOf(g, 0.0, 0.0), 40, speedKmh = 15.0)
        assertNull(m.up)
    }

    @Test
    fun manualCalibrationWorksIndoorsAndIsKept() {
        val m = Mount()
        rows(m, doubleArrayOf(g, 0.0, 0.0), 20, speedKmh = null)
        assertTrue(m.calibrateNow())
        assertTrue(m.manual)
        // A later still period at another angle does not overwrite it, but is reported.
        rows(m, doubleArrayOf(0.0, 0.0, g), 20)
        near(upX, m.up!!, 1e-9)
        assertTrue(m.moved)
    }

    @Test
    fun manualCalibrationRefusesAShakingPhone() {
        val m = Mount()
        repeat(20) { m.onRow(doubleArrayOf(g + if (it % 2 == 0) 1.0 else -1.0, 0.0, 0.0), null, null) }
        assertFalse(m.calibrateNow())
    }

    @Test
    fun screenFacingDriverGivesCarAxes() {
        val m = Mount()
        rows(m, doubleArrayOf(g, 0.0, 0.0), 20)
        // Back of the phone (-Z) is forward, so the driver's right is -Y here.
        val v = m.vehicle(doubleArrayOf(g, -0.5 * g, -0.2 * g))!!
        near(doubleArrayOf(0.2, 0.5, 1.0), v, 1e-9)
    }

    @Test
    fun forwardIsLearnedFromGnssSpeedChanges() {
        val m = Mount()
        rows(m, doubleArrayOf(g, 0.0, 0.0), 20)
        // Phone actually turned 25 degrees on the dash: forward is between -Z and +Y.
        val a = Math.toRadians(25.0)
        val fwd = doubleArrayOf(0.0, sin(a), -cos(a))
        var t = 1_800_000_000_000L; var v = 5.0
        m.onFix(t, v, 90.0)
        repeat(30) { k ->
            val acc = if (k % 2 == 0) 0.6 else -0.5 // speeding up and slowing down, driving straight
            rows(m, DoubleArray(3) { upX[it] * g + fwd[it] * acc }, 10, speedKmh = v * 3.6)
            t += 1000; v += acc
            m.onFix(t, v, 90.0)
        }
        assertTrue(m.forwardLearned)
        near(fwd, m.forward()!!, 1e-6)
        assertEquals(25.0, m.forwardOffsetDeg()!!, 1e-4)
        val car = m.vehicle(DoubleArray(3) { upX[it] * g + fwd[it] * 2.0 })!!
        near(doubleArrayOf(2.0 / g, 0.0, 1.0), car, 1e-6)
    }

    @Test
    fun turningIsNotUsedForForward() {
        val m = Mount()
        rows(m, doubleArrayOf(g, 0.0, 0.0), 20)
        var t = 0L; var v = 5.0; var b = 0.0
        m.onFix(t, v, b)
        repeat(30) {
            rows(m, doubleArrayOf(g, 3.0, 0.0), 10, speedKmh = v * 3.6)
            t += 1000; v += 0.5; b += 20.0
            m.onFix(t, v, b)
        }
        assertFalse(m.forwardLearned)
    }

    @Test
    fun saveAndLoadRoundTrip() {
        val m = Mount()
        rows(m, doubleArrayOf(g, 0.0, 0.0), 20, speedKmh = null)
        m.calibrateNow()
        val copy = Mount().apply { load(m.save()) }
        near(m.up!!, copy.up!!, 1e-12)
        assertTrue(copy.manual)
    }
}
