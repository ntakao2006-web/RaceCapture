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

/** What the screens show; written by the service thread, read by the activities. */
object Status {
    @Volatile var running = false
    @Volatile var startedAt = 0L          // SystemClock.elapsedRealtime() at start
    @Volatile var fileName: String? = null
    @Volatile var logError = ""
    @Volatile var rows = 0L
    @Volatile var fix = 0                 // 0 none, 2 = 2D, 3 = 3D
    @Volatile var sats = 0
    @Volatile var accuracyM: Double? = null
    @Volatile var speedKmh: Double? = null
    @Volatile var fromLogger = false      // fix/sats/accuracy/speed are the Ver.2 logger's (LoggerFeed)
    @Volatile var relay: String? = null   // null: no server configured
    @Volatile var relayConnected = false
    @Volatile var relayError = ""
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
    private var direct: PodiumDirect? = null
    private var podiumKey = ""
    private var link: LoggerLink? = null
    /** When the relay was last seen not connected (null while it is), for the fallback to Podium. */
    private var serverDownSince: Long? = null
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
        Race.init(this)
        Imu.init(this)
        handler.post {
            hub = SensorHub(this, handler).also { it.start() }
            try { log = LogWriter(this, settings.carName) } catch (e: Exception) { logError = e.toString() }
            relay = if (settings.urls.isEmpty()) null
                    else RelayClient(settings.urls, settings.carName.ifEmpty { "android" }, handler).also { it.start() }
            podiumKey = settings.podiumKey
            link = if (!settings.loggerConfigured) null
                   else LoggerLink(this, settings.loggerSsid, settings.loggerPass, settings.loggerHostOrDefault,
                                   settings.loggerKey, handler).also { it.start() }
            startedAt = SystemClock.elapsedRealtime()
            nextTick = SystemClock.uptimeMillis()
            Status.startedAt = startedAt
            Status.relay = relay?.state
            Status.running = true
            tick()
        }
    }

    private fun tick() {
        val row = hub.snapshot(SystemClock.elapsedRealtime() - startedAt)
        try { log?.write(row) } catch (e: Exception) { logError = e.toString(); log = null }
        send(PodiumEncoder.row(row))
        rows++
        publish(row)
        // Fixed 100 ms grid; after a stall skip ahead instead of bursting.
        nextTick = maxOf(nextTick + 100, SystemClock.uptimeMillis())
        handler.postAtTime({ tick() }, nextTick)
    }

    /**
     * To the relay while it is connected; when no server has answered for
     * [FALLBACK_MS] (or none is set) and a Podium key is saved, straight to
     * Podium instead. Never both: the relay forwards to Podium with the same
     * key, and two senders on one key collide there.
     */
    private fun send(encoded: String) {
        val r = relay
        if (r != null && r.connected) {
            serverDownSince = null
            direct?.let { it.stop(); direct = null }
            r.offer(encoded)
            return
        }
        r?.offer(encoded) // counts the drop
        val now = SystemClock.elapsedRealtime()
        val since = serverDownSince ?: now.also { serverDownSince = it }
        if (direct == null && podiumKey.isNotEmpty() && (r == null || now - since >= FALLBACK_MS)) direct = PodiumDirect(podiumKey)
        direct?.offer(encoded)
    }

    private fun publish(row: Map<String, Double?>) {
        Status.rows = rows
        Status.fileName = log?.fileName
        Status.logError = logError
        // The screen shows the source the lap timer is using: the logger while its fixes arrive.
        Status.fromLogger = LoggerFeed.live()
        if (Status.fromLogger) {
            Status.fix = LoggerFeed.fix; Status.sats = LoggerFeed.sats
            Status.accuracyM = LoggerFeed.accuracyM; Status.speedKmh = LoggerFeed.speedKmh
        } else {
            Status.fix = row["GPSFix"]?.toInt() ?: 0
            Status.sats = row["GPSSats"]?.toInt() ?: 0
            Status.accuracyM = row["Accuracy"]
            Status.speedKmh = row["GPSSpeed"]
        }
        val r = relay; val d = direct
        Status.relay = when {
            r?.connected == true -> r.state
            d != null -> if (d.authenticated) "Podium直接" else "直接・接続中"
            else -> r?.state
        }
        Status.relayConnected = r?.connected == true || d?.authenticated == true
        Status.relayError = d?.lastError?.takeIf { it.isNotEmpty() } ?: r?.lastError ?: ""
    }

    override fun onDestroy() {
        Status.running = false
        handler.removeCallbacksAndMessages(null)
        handler.post {
            hub.stop()
            link?.stop()
            relay?.stop()
            direct?.stop()
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
        /** No relay server for this long: send straight to Podium (if a key is saved). */
        private const val FALLBACK_MS = 30_000L
        fun start(context: Context) = context.startForegroundService(Intent(context, LoggerService::class.java))
        fun stop(context: Context) = context.stopService(Intent(context, LoggerService::class.java))
    }
}
