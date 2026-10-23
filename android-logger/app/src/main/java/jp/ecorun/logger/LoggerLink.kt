package jp.ecorun.logger

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.wifi.WifiNetworkSpecifier
import android.os.Handler
import android.os.SystemClock
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/** What the Ver.2 logger last sent; written by [LoggerLink], read by the service, SensorHub and the screens. */
object LoggerFeed {
    @Volatile var configured = false
    @Volatile var wifi = false            // the logger's Wi-Fi is joined (for this app only)
    @Volatile var socket = false          // the live stream is open
    @Volatile var lastFrameAt = 0L        // elapsedRealtime of the last frame
    @Volatile var lastFixAt = 0L          // elapsedRealtime of the last new fix handed to Race
    @Volatile var mcu = false             // the logger's Linux side receives its MCU
    @Volatile var fix = 0
    @Volatile var sats = 0
    @Volatile var accuracyM: Double? = null
    @Volatile var speedKmh: Double? = null
    @Volatile var rec = false
    @Volatile var lineId: String? = null
    @Volatile var error = ""
    // The logger's own lap timer (lap.py), shown next to the phone's for comparison.
    @Volatile var lapCount: Int? = null
    @Volatile var lapsLeft: Int? = null
    @Volatile var lapFinished = false
    @Volatile var lapRunning = false
    @Volatile var totalLaps: Int? = null
    /** What the last sync (lines, required laps, reset) did, for the settings screen. */
    @Volatile var syncNote = ""

    /** The logger's frames are fresh enough to show its lap count. */
    fun fresh(now: Long = SystemClock.elapsedRealtime()) = configured && socket && now - lastFrameAt < STALE_MS

    /** The logger's position is fresh: it feeds the lap timer and the phone's own GNSS waits. */
    fun live(now: Long = SystemClock.elapsedRealtime()) = configured && now - lastFixAt < STALE_MS

    /** Why the phone's GNSS is in use, for the warning strip. */
    fun reason(now: Long = SystemClock.elapsedRealtime()): String = when {
        !wifi -> "ロガーのWi-Fiにつながっていません"
        !socket || now - lastFrameAt > STALE_MS -> "ロガーから受信できていません"
        !mcu -> "ロガーの本体（MCU）からの受信待ち"
        fix == 0 -> "ロガーが測位していません"
        else -> "ロガーの位置が届いていません"
    }

    fun reset() { wifi = false; socket = false; lastFrameAt = 0; lastFixAt = 0; mcu = false; fix = 0; sats = 0
        accuracyM = null; speedKmh = null; rec = false; lineId = null; error = ""
        lapCount = null; lapsLeft = null; lapFinished = false; lapRunning = false; totalLaps = null }

    /** Logger fixes come at 10 Hz; two seconds without one and the phone takes over. */
    const val STALE_MS = 2000L
}

/**
 * The car's dash phone takes its position from the Ver.2 logger: the logger
 * is a Wi-Fi access point without internet, joined only for this app through
 * a [WifiNetworkSpecifier], so the phone's default network stays on LTE and
 * Discord never moves to it. Frames from the logger's course-walk server
 * (field.py `/api/field/live`, 10 Hz) go to [Race] while they are fresh;
 * when they stop, [SensorHub] feeds the phone's own GNSS (see [LoggerFeed.live]).
 *
 * All methods run on [handler]'s thread; network and OkHttp callbacks are posted onto it.
 */
class LoggerLink(context: Context, private val ssid: String, private val pass: String,
                 private val host: String, private val key: String, private val handler: Handler) {
    private val cm = context.getSystemService(ConnectivityManager::class.java)
    private var network: Network? = null
    private var client: OkHttpClient? = null
    private var socket: WebSocket? = null
    private var stopped = false
    private var requested = false
    private var generation = 0
    private var lastUtc = 0L

    private val callback = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(n: Network) { handler.post { if (!stopped) { network = n; LoggerFeed.wifi = true; LoggerFeed.error = ""; open() } } }
        override fun onLost(n: Network) { handler.post { if (network == n) { network = null; LoggerFeed.wifi = false; close(); rerequest(3000) } } }
        override fun onUnavailable() { handler.post { LoggerFeed.error = "ロガーのWi-Fiが見つかりません"; requested = false; rerequest(10_000) } }
    }

    fun start() {
        LoggerFeed.reset()
        LoggerFeed.configured = true
        current = this
        request()
    }

    fun stop() {
        stopped = true
        if (current === this) current = null
        close()
        if (requested) try { cm.unregisterNetworkCallback(callback) } catch (_: IllegalArgumentException) {}
        requested = false
        LoggerFeed.reset()
        LoggerFeed.configured = false
    }

    private fun request() {
        if (stopped || requested) return
        val spec = WifiNetworkSpecifier.Builder().setSsid(ssid).apply { if (pass.isNotEmpty()) setWpa2Passphrase(pass) }.build()
        val req = NetworkRequest.Builder()
            .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
            .removeCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .setNetworkSpecifier(spec)
            .build()
        try {
            cm.requestNetwork(req, callback)
            requested = true
        } catch (e: RuntimeException) {
            LoggerFeed.error = e.toString().take(120)
            handler.postDelayed({ request() }, 10_000)
        }
    }

    /** Drops the old request and asks again, so the system looks for the access point anew. */
    private fun rerequest(delayMs: Long) {
        if (requested) try { cm.unregisterNetworkCallback(callback) } catch (_: IllegalArgumentException) {}
        requested = false
        handler.postDelayed({ request() }, delayMs)
    }

    private fun open() {
        val n = network ?: return
        close()
        val gen = ++generation
        val c = OkHttpClient.Builder()
            .socketFactory(n.socketFactory) // this Wi-Fi only, whatever the default network is
            .dns(object : okhttp3.Dns { override fun lookup(hostname: String) = n.getAllByName(hostname).toList() })
            .pingInterval(2, TimeUnit.SECONDS)
            .connectTimeout(3, TimeUnit.SECONDS)
            .build()
        client = c
        val request = Request.Builder().url("ws://$host:8082/api/field/live?k=$key").build()
        socket = c.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) { post(gen) { LoggerFeed.socket = true; LoggerFeed.error = "" } }
            override fun onMessage(webSocket: WebSocket, text: String) { post(gen) { frame(text) } }
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                post(gen) {
                    LoggerFeed.error = if (response?.code == 403) "合言葉が違います" else t.toString().take(120)
                    retry()
                }
            }
            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) { webSocket.close(1000, null) }
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) { post(gen) { retry() } }
        })
    }

    private fun post(gen: Int, block: () -> Unit) {
        handler.post { if (gen == generation && !stopped) block() }
    }

    private fun retry() {
        close()
        handler.postDelayed({ if (network != null && socket == null) open() }, 1000)
    }

    private fun close() {
        generation++
        socket?.cancel(); socket = null
        client?.dispatcher?.executorService?.shutdown(); client = null
        LoggerFeed.socket = false
    }

    private fun frame(text: String) {
        val j = try { JSONObject(text) } catch (_: Exception) { return }
        val now = SystemClock.elapsedRealtime()
        fun num(k: String): Double? = if (j.isNull(k)) null else j.optDouble(k).takeIf { !it.isNaN() }
        LoggerFeed.lastFrameAt = now
        LoggerFeed.mcu = j.optBoolean("connected")
        LoggerFeed.fix = num("fix")?.toInt() ?: 0
        LoggerFeed.sats = num("sats")?.toInt() ?: 0
        LoggerFeed.accuracyM = num("hacc_m")
        LoggerFeed.speedKmh = num("speed")
        LoggerFeed.rec = j.optBoolean("rec")
        LoggerFeed.lineId = if (j.isNull("line_id")) null else j.optString("line_id")
        LoggerFeed.totalLaps = num("total_laps")?.toInt()
        j.optJSONObject("lap")?.let { lap ->
            LoggerFeed.lapCount = if (lap.isNull("count")) null else lap.optInt("count")
            LoggerFeed.lapsLeft = if (lap.isNull("laps_left")) null else lap.optInt("laps_left")
            LoggerFeed.lapFinished = lap.optBoolean("finished")
            LoggerFeed.lapRunning = lap.optBoolean("running")
        }
        follow(if (j.isNull("line_code")) null else j.optString("line_code"), now)
        val utc = num("utc")?.toLong(); val lat = num("lat"); val lon = num("lon")
        if (utc == null || lat == null || lon == null || LoggerFeed.fix == 0 || utc == lastUtc) return
        lastUtc = utc
        LoggerFeed.lastFixAt = now
        Race.onFix(Fix(utc, lat, lon, LoggerFeed.accuracyM, LoggerFeed.speedKmh, num("yaw")))
    }

    /**
     * Before the lap timing starts, the logger is the reference: its lines replace the
     * phone's when they differ, and the phone's required laps (tied to the class's time
     * and distance) go to the logger. Once timing has started nothing changes either way.
     */
    private fun follow(code: String?, now: Long) {
        if (Race.timingStarted()) return
        if (code != null && LoggerFeed.lineId != null && LoggerFeed.lineId != Race.reference?.id) {
            try {
                val r = Race.importReference(code)
                LoggerFeed.syncNote = "ロガーのライン（基準${r.id}）を読み込みました"
            } catch (e: LineCode.Invalid) {
                LoggerFeed.syncNote = "ロガーのラインを読めません：${e.message}"
            }
        }
        val laps = Race.config().totalLaps
        if (laps != null && laps != LoggerFeed.totalLaps && LoggerFeed.lapCount == 0 && !LoggerFeed.lapRunning && now - lastTotalAt > 5000) {
            lastTotalAt = now
            send("/api/field/total", JSONObject().put("total_laps", laps)) { ok, msg ->
                LoggerFeed.syncNote = if (ok) "ロガーの規定周回数を${laps}周にしました" else "ロガーの規定周回数を変えられません：$msg"
            }
        }
    }
    private var lastTotalAt = 0L

    /** The lap reset on the phone resets the logger's laps too ([done] runs on [handler]'s thread). */
    fun resetLogger(done: (Boolean, String) -> Unit) = handler.post {
        send("/api/field/reset", JSONObject()) { ok, msg -> done(ok, msg) }
    }

    /** POST to the logger's course-walk API over its Wi-Fi; [done] gets (ok, message) on [handler]'s thread. */
    private fun send(path: String, body: JSONObject, done: (Boolean, String) -> Unit) {
        val c = client
        if (c == null || !LoggerFeed.socket) { done(false, "ロガーにつながっていません"); return }
        val request = Request.Builder().url("http://$host:8082$path")
            .header("X-Field-Key", key).header("X-EcoCapture", "1")
            .post(body.toString().toRequestBody("application/json".toMediaType())).build()
        c.newCall(request).enqueue(object : okhttp3.Callback {
            override fun onFailure(call: okhttp3.Call, e: java.io.IOException) { handler.post { done(false, e.toString().take(80)) } }
            override fun onResponse(call: okhttp3.Call, response: Response) {
                val code = response.code; response.close()
                handler.post { done(code == 200, if (code == 200) "" else "HTTP $code") }
            }
        })
    }

    companion object {
        /** The running link (set by the service), for the reset button on the settings screen. */
        @Volatile var current: LoggerLink? = null
    }
}
