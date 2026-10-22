package jp.ecorun.logger

import android.content.ContentValues
import android.content.Context
import android.os.Environment
import android.provider.MediaStore
import java.io.BufferedWriter
import java.io.OutputStreamWriter
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * One CSV per run in Download/EcoLogger, written regardless of the network.
 * Download/ is visible over USB and survives uninstalling the app.
 */
class LogWriter(context: Context, carName: String) {
    val fileName: String
    private val out: BufferedWriter
    private var lastFlush = 0L

    init {
        val stamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        val safeCar = carName.replace(Regex("[^A-Za-z0-9_-]"), "_").ifEmpty { "car" }
        fileName = "EL_${safeCar}_$stamp.csv"
        val values = ContentValues().apply {
            put(MediaStore.Downloads.DISPLAY_NAME, fileName)
            put(MediaStore.Downloads.MIME_TYPE, "text/csv")
            put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/EcoLogger")
        }
        val resolver = context.contentResolver
        val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
            ?: error("cannot create $fileName")
        out = BufferedWriter(OutputStreamWriter(resolver.openOutputStream(uri, "w")!!, Charsets.UTF_8))
        out.write(COLUMNS.joinToString(",") + "\n")
    }

    fun write(row: Map<String, Double?>) {
        out.write(COLUMNS.joinToString(",") { key ->
            row[key]?.let { PodiumEncoder.number(it, if (key == "Lat" || key == "Lon") 7 else if (key in MINUTES) 5 else if (key in G_COLUMNS) 4 else 3) } ?: ""
        })
        out.write("\n")
        // Flush once a second: a sudden power cut loses at most that much.
        val now = System.currentTimeMillis()
        if (now - lastFlush >= 1000) { out.flush(); lastFlush = now }
    }

    fun close() = out.close()

    companion object {
        private val G_COLUMNS = setOf("LongAccel", "LatAccel", "VertAccel")
        private val MINUTES = setOf("LapTime", "BestLap", "ElapsedTime", "RaceTime")
        val COLUMNS = listOf("Interval", "Utc", "Lat", "Lon", "Altitude", "GPSSpeed", "Yaw", "Accuracy",
            "GPSFix", "GPSSats", "AccelX", "AccelY", "AccelZ", "GyroX", "GyroY", "GyroZ",
            "LongAccel", "LatAccel", "VertAccel", "LapCount", "CurrentLap", "LapTime", "BestLap", "ElapsedTime", "RaceTime", "LapsLeft")
    }
}
