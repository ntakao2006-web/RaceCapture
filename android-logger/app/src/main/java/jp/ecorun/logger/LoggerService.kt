package jp.ecorun.logger

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.HandlerThread
import android.os.Handler
import android.os.IBinder
import android.os.PowerManager
import android.os.SystemClock

/** What the screen shows; written by the service thread, read by the activity. */
object Status {
    @Volatile var running = false
    @Volatile var text = "停止中"
}

/**
 * Foreground service (type location) so recording and sending go on with the
 * screen off. Builds one row every 100 ms: CSV first, then the relay.
 */
class LoggerService : Service() {
    private lateinit var thread: HandlerThread
    private lateinit var handler: Handler
    private lateinit var hub: SensorHub
    private var log: LogWriter? = null
    private var relay: RelayClient? = null
    private var wakeLock: PowerManager.WakeLock? = null
    private var startedAt = 0L
    private var nextTick = 0L
    private var rows = 0L
    private var logError = ""

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel(CHANNEL, "記録中", NotificationManager.IMPORTANCE_LOW))
        startForeground(1, notification(), ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION)

        // Keep the CPU (and so the IMU listeners) awake with the screen off.
        wakeLock = getSystemService(PowerManager::class.java)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "ecologger:run").apply { acquire() }

        thread = HandlerThread("logger").apply { start() }
        handler = Handler(thread.looper)
        val settings = Settings(this)
        handler.post {
            hub = SensorHub(this, handler).also { it.start() }
            try { log = LogWriter(this, settings.carName) } catch (e: Exception) { logError = e.toString() }
            relay = RelayClient(settings.urls, settings.carName.ifEmpty { "android" }, handler).also { it.start() }
            startedAt = SystemClock.elapsedRealtime()
            nextTick = SystemClock.uptimeMillis()
            Status.running = true
            tick()
        }
    }

    private fun tick() {
        val row = hub.snapshot(SystemClock.elapsedRealtime() - startedAt)
        try { log?.write(row) } catch (e: Exception) { logError = e.toString(); log = null }
        relay?.offer(PodiumEncoder.row(row))
        rows++
        if (rows % 5 == 0L) Status.text = describe(row)
        // Fixed 100 ms grid; after a stall skip ahead instead of bursting.
        nextTick = maxOf(nextTick + 100, SystemClock.uptimeMillis())
        handler.postAtTime({ tick() }, nextTick)
    }

    private fun describe(row: Map<String, Double?>): String {
        val fix = when (row["GPSFix"]?.toInt()) { 3 -> "3D測位"; 2 -> "2D測位"; else -> "測位待ち" }
        val r = relay
        return buildString {
            append("GNSS：$fix・衛星${row["GPSSats"]?.toInt() ?: 0}")
            row["Accuracy"]?.let { append("・精度±%.1fm".format(it)) }
            append("\n速度：%.1f km/h".format(row["GPSSpeed"] ?: 0.0))
            append("\n記録：").append(log?.let { "${it.fileName}（${rows}行）" } ?: "できていません $logError")
            if (r != null) {
                append("\n送信：${r.state}・送った行 ${r.sentRows}・捨てた行 ${r.droppedRows}")
                if (r.lastError.isNotEmpty()) append("\n最後のエラー：${r.lastError}")
            }
        }
    }

    override fun onDestroy() {
        Status.running = false
        Status.text = "停止中"
        handler.removeCallbacksAndMessages(null)
        handler.post {
            hub.stop()
            relay?.stop()
            try { log?.close() } catch (_: Exception) {}
            thread.quitSafely()
        }
        wakeLock?.release()
        super.onDestroy()
    }

    private fun notification(): Notification {
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        return Notification.Builder(this, CHANNEL)
            .setContentTitle("EcoLogger 記録中")
            .setContentText("画面を消しても記録・送信を続けます")
            .setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .setContentIntent(open)
            .setOngoing(true)
            .build()
    }

    companion object {
        private const val CHANNEL = "run"
        fun start(context: Context) = context.startForegroundService(Intent(context, LoggerService::class.java))
        fun stop(context: Context) = context.stopService(Intent(context, LoggerService::class.java))
    }
}
