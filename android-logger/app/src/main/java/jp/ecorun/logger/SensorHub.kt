package jp.ecorun.logger

import android.annotation.SuppressLint
import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.location.GnssStatus
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Handler
import android.os.SystemClock

/**
 * Collects the phone's GNSS and IMU and hands out one snapshot per 100 ms row.
 * IMU values are averaged over the row so a 10 Hz row is not just one noisy
 * reading. Axes are the phone's own (see android-logger/README.md).
 */
class SensorHub(context: Context, private val handler: Handler) : SensorEventListener, LocationListener {
    private val locations = context.getSystemService(LocationManager::class.java)
    private val sensors = context.getSystemService(SensorManager::class.java)
    private val lock = Any()

    private var location: Location? = null
    private var satsUsed = 0
    private val accel = DoubleArray(3)
    private val gyro = DoubleArray(3)
    private var accelN = 0
    private var gyroN = 0

    private val gnss = object : GnssStatus.Callback() {
        override fun onSatelliteStatusChanged(status: GnssStatus) {
            var used = 0
            for (i in 0 until status.satelliteCount) if (status.usedInFix(i)) used++
            synchronized(lock) { satsUsed = used }
        }
    }

    @SuppressLint("MissingPermission") // The service only starts after the permission is granted.
    fun start() {
        locations.requestLocationUpdates(LocationManager.GPS_PROVIDER, 100L, 0f, this, handler.looper)
        locations.registerGnssStatusCallback(gnss, handler)
        sensors.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)?.let {
            sensors.registerListener(this, it, SensorManager.SENSOR_DELAY_GAME, handler)
        }
        sensors.getDefaultSensor(Sensor.TYPE_GYROSCOPE)?.let {
            sensors.registerListener(this, it, SensorManager.SENSOR_DELAY_GAME, handler)
        }
    }

    fun stop() {
        locations.removeUpdates(this)
        locations.unregisterGnssStatusCallback(gnss)
        sensors.unregisterListener(this)
    }

    override fun onLocationChanged(l: Location) {
        synchronized(lock) { location = l }
        Race.onFix(Fix(l.time, l.latitude, l.longitude,
            if (l.hasAccuracy()) l.accuracy.toDouble() else null,
            if (l.hasSpeed()) l.speed * 3.6 else null,
            if (l.hasBearing()) l.bearing.toDouble() else null))
    }

    override fun onSensorChanged(e: SensorEvent) {
        synchronized(lock) {
            when (e.sensor.type) {
                Sensor.TYPE_ACCELEROMETER -> { for (i in 0..2) accel[i] += e.values[i].toDouble(); accelN++ }
                Sensor.TYPE_GYROSCOPE -> { for (i in 0..2) gyro[i] += Math.toDegrees(e.values[i].toDouble()); gyroN++ }
            }
        }
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}

    /** Values for one row, keyed like [PodiumEncoder.CHANNELS], plus accuracy for the file. */
    fun snapshot(intervalMs: Long): Map<String, Double?> = synchronized(lock) {
        val out = HashMap<String, Double?>()
        out["Interval"] = intervalMs.toDouble()
        val l = location
        val ageMs = if (l == null) Long.MAX_VALUE
                    else (SystemClock.elapsedRealtimeNanos() - l.elapsedRealtimeNanos) / 1_000_000
        if (l != null && ageMs < 3000) {
            // GNSS time of the fix moved forward by its age, so rows between
            // 1 Hz fixes still carry increasing UTC (Podium needs a GNSS Utc).
            out["Utc"] = (l.time + ageMs).toDouble()
            out["Lat"] = l.latitude
            out["Lon"] = l.longitude
            if (l.hasAltitude()) out["Altitude"] = l.altitude
            if (l.hasSpeed()) { out["GPSSpeed"] = l.speed * 3.6; out["Speed"] = l.speed * 3.6 }
            if (l.hasBearing()) out["Yaw"] = l.bearing.toDouble()
            if (l.hasAccuracy()) out["Accuracy"] = l.accuracy.toDouble()
            out["GPSFix"] = if (l.hasAltitude()) 3.0 else 2.0
        } else {
            out["GPSFix"] = 0.0
        }
        out["GPSSats"] = satsUsed.toDouble()
        if (accelN > 0) {
            out["AccelX"] = accel[0] / accelN; out["AccelY"] = accel[1] / accelN; out["AccelZ"] = accel[2] / accelN
        }
        if (gyroN > 0) {
            out["GyroX"] = gyro[0] / gyroN; out["GyroY"] = gyro[1] / gyroN; out["GyroZ"] = gyro[2] / gyroN
        }
        accel.fill(0.0); gyro.fill(0.0); accelN = 0; gyroN = 0
        if (Race.config().control != null) Race.values()?.let { v ->
            out["LapCount"] = v.count.toDouble(); out["CurrentLap"] = v.current.toDouble()
            out["LapTime"] = v.lastS?.div(60); out["BestLap"] = v.bestS?.div(60)
            out["ElapsedTime"] = v.elapsedS?.div(60); out["RaceTime"] = v.raceS?.div(60)
            out["LapsLeft"] = v.lapsLeft?.toDouble()
        }
        out
    }
}
