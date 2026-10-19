package jp.ecorun.logger

import kotlin.math.abs
import kotlin.math.acos
import kotlin.math.sqrt

/**
 * How the phone sits in the car, so phone-axis IMU values can be turned into
 * the car's longitudinal / lateral / vertical acceleration.
 *
 * - Up (1G calibration): the mean accelerometer reading while the car is
 *   still. Taken automatically whenever the car stands still and the phone is
 *   steady, or on demand from the settings screen (then it is kept fixed).
 * - Forward: starts as "the back of the phone faces forward" (the screen faces
 *   the driver) and is then learned from GNSS: while driving straight, the
 *   horizontal acceleration measured between two fixes is weighted by the GNSS
 *   speed change over the same interval and summed, so the sum points forward.
 *
 * Output signs: LongAccel + accelerating, LatAccel + towards the car's right,
 * VertAccel + up (about 1 G at rest), all in G.
 */
class Mount {
    var up: DoubleArray? = null; private set
    var manual = false; private set
    /** Set when, with a manual calibration, the phone at rest no longer matches it. */
    var moved = false; private set
    private val forwardSum = DoubleArray(3)
    var forwardWeight = 0.0; private set

    private val window = ArrayDeque<DoubleArray>() // last 2 s, always kept (manual calibration)
    private var stillRows = 0
    private var intervalSum = DoubleArray(3)
    private var intervalN = 0
    private var lastFix: Triple<Long, Double, Double>? = null // utc, speed m/s, bearing

    /** Feed one 0.1 s row (mean accel m/s², mean gyro deg/s, GNSS speed km/h if known). */
    fun onRow(accel: DoubleArray?, gyroDegS: DoubleArray?, speedKmh: Double?) {
        if (accel == null) return
        for (i in 0..2) intervalSum[i] += accel[i]
        intervalN++
        window.addLast(accel.copyOf())
        while (window.size > STILL_ROWS) window.removeFirst()
        // Automatic calibration needs GNSS to say the car is not moving.
        val still = speedKmh != null && speedKmh < 1.0 && (gyroDegS == null || norm(gyroDegS) < 2.0)
        stillRows = if (still) stillRows + 1 else 0
        if (stillRows < STILL_ROWS) return
        val mean = steadyMean() ?: return
        stillRows = 0 // next sample after another 2 s
        val u = unit(mean)
        val current = up
        if (manual) {
            moved = current != null && angleDeg(current, u) > MOVED_DEG
            return
        }
        if (current == null || angleDeg(current, u) > MOVED_DEG) {
            // First calibration, or the phone was re-mounted: start over.
            up = u; forwardSum.fill(0.0); forwardWeight = 0.0
        } else {
            up = unit(DoubleArray(3) { current[it] * 0.8 + u[it] * 0.2 })
        }
    }

    /** Feed each GNSS fix (speed m/s, bearing deg). */
    fun onFix(utcMs: Long, speedMs: Double?, bearing: Double?) {
        val prev = lastFix
        val n = intervalN
        val mean = if (n > 0) DoubleArray(3) { intervalSum[it] / n } else null
        intervalSum = DoubleArray(3); intervalN = 0
        if (speedMs == null) { lastFix = null; return }
        lastFix = Triple(utcMs, speedMs, bearing ?: Double.NaN)
        val u = up ?: return
        if (prev == null || mean == null || n < 5) return
        val dt = (utcMs - prev.first) / 1000.0
        if (dt !in 0.5..1.6) return
        if (speedMs < 2.0 || prev.second < 2.0) return
        if (!bearing.isFiniteOrNull() || prev.third.isNaN()) return
        var turn = abs(bearing!! - prev.third) % 360
        if (turn > 180) turn = 360 - turn
        if (turn / dt > 4.0) return // only straight driving: no centripetal part
        val dvdt = (speedMs - prev.second) / dt
        if (abs(dvdt) < 0.3) return
        val h = horizontal(mean, u)
        for (i in 0..2) forwardSum[i] += h[i] * dvdt
        forwardWeight += dvdt * dvdt
    }

    /** Manual 1G calibration from the last rows; null when the phone is not steady. */
    fun calibrateNow(): Boolean {
        val mean = steadyMean() ?: return false
        up = unit(mean); manual = true; moved = false
        return true
    }

    fun clearCalibration() {
        up = null; manual = false; moved = false; forwardSum.fill(0.0); forwardWeight = 0.0; stillRows = 0
    }

    val forwardLearned: Boolean get() = forwardWeight >= MIN_FORWARD_WEIGHT

    fun forward(): DoubleArray? {
        val u = up ?: return null
        if (forwardLearned) {
            val f = horizontal(forwardSum, u)
            if (norm(f) > 1e-6) return unit(f)
        }
        // Screen facing the driver: the back of the phone (-Z) points forward.
        val back = horizontal(doubleArrayOf(0.0, 0.0, -1.0), u)
        if (norm(back) > 0.3) return unit(back)
        return unit(horizontal(doubleArrayOf(0.0, 1.0, 0.0), u)) // lying flat: top edge forward
    }

    /** Angle between the learned forward and the screen-facing guess, for the settings screen. */
    fun forwardOffsetDeg(): Double? {
        val u = up ?: return null
        if (!forwardLearned) return null
        val back = horizontal(doubleArrayOf(0.0, 0.0, -1.0), u)
        if (norm(back) < 0.3) return null
        return angleDeg(unit(back), forward()!!)
    }

    /** (LongAccel, LatAccel, VertAccel) in G, or null before the 1G calibration. */
    fun vehicle(accel: DoubleArray): DoubleArray? {
        val u = up ?: return null
        val f = forward() ?: return null
        val r = cross(f, u)
        return doubleArrayOf(dot(accel, f) / G, dot(accel, r) / G, dot(accel, u) / G)
    }

    fun save(): DoubleArray = doubleArrayOf(*(up ?: DoubleArray(3)), if (up != null) 1.0 else 0.0,
        if (manual) 1.0 else 0.0, *forwardSum, forwardWeight)

    fun load(a: DoubleArray) {
        if (a.size != 9) return
        up = if (a[3] != 0.0) a.copyOfRange(0, 3) else null
        manual = a[4] != 0.0
        for (i in 0..2) forwardSum[i] = a[5 + i]
        forwardWeight = a[8]
    }

    private fun steadyMean(): DoubleArray? {
        if (window.size < STILL_ROWS) return null
        val mean = DoubleArray(3) { i -> window.sumOf { it[i] } / window.size }
        val steady = (0..2).all { i -> sqrt(window.sumOf { (it[i] - mean[i]).let { d -> d * d } } / window.size) < 0.08 }
        if (!steady || abs(norm(mean) - G) > 0.6) return null
        return mean
    }

    private fun Double?.isFiniteOrNull() = this != null && this.isFinite()

    companion object {
        const val G = 9.80665
        const val STILL_ROWS = 20          // 2 s of rows
        const val MOVED_DEG = 10.0
        const val MIN_FORWARD_WEIGHT = 3.0 // about a dozen 0.5 m/s² speed changes

        fun dot(a: DoubleArray, b: DoubleArray) = a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
        fun norm(a: DoubleArray) = sqrt(dot(a, a))
        fun unit(a: DoubleArray): DoubleArray { val n = norm(a); return DoubleArray(3) { a[it] / n } }
        fun cross(a: DoubleArray, b: DoubleArray) =
            doubleArrayOf(a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
        fun horizontal(a: DoubleArray, up: DoubleArray): DoubleArray { val d = dot(a, up); return DoubleArray(3) { a[it] - d * up[it] } }
        fun angleDeg(a: DoubleArray, b: DoubleArray) = Math.toDegrees(acos((dot(a, b) / (norm(a) * norm(b))).coerceIn(-1.0, 1.0)))
    }
}
