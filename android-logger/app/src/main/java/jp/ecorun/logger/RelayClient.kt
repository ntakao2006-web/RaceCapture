package jp.ecorun.logger

import android.os.Handler
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import java.util.concurrent.TimeUnit

/**
 * Sends rows to ecorun-logger-server over `/ws/audio/<room>`, like the Ver.2
 * logger's relay mode. Tries the URLs in order; a failure moves straight to the
 * next one and only a full round of failures waits. Once on a backup it stays
 * there until that one fails (same rule as ER-7-8). Rows are live-only: while
 * disconnected they are dropped here, the CSV keeps everything.
 *
 * All methods run on [handler]'s thread; OkHttp callbacks are posted onto it.
 */
class RelayClient(private val urls: List<String>, private val clientId: String, private val handler: Handler) {
    private val client = OkHttpClient.Builder()
        .pingInterval(5, TimeUnit.SECONDS) // a dead link shows up as a missing pong within ~10 s
        .connectTimeout(10, TimeUnit.SECONDS)
        .build()
    private var socket: WebSocket? = null
    private var connected = false
    private var index = 0
    private var failuresInRow = 0
    private var stopped = false
    private var generation = 0
    private val batch = ArrayList<String>()

    var sentRows = 0L; private set
    var droppedRows = 0L; private set
    var lastError = ""; private set
    val state: String get() = when {
        urls.isEmpty() -> "送信先なし（記録のみ）"
        connected -> (if (index == 0) "主" else "予備${index}") + "へ送信中"
        else -> "接続中…（" + (if (index == 0) "主" else "予備${index}") + "）"
    }

    fun start() { if (urls.isNotEmpty()) connect() }

    fun stop() {
        stopped = true
        socket?.close(1000, "stop")
        client.dispatcher.executorService.shutdown()
    }

    fun offer(row: String) {
        if (!connected) { droppedRows++; return }
        batch.add(row)
        if (batch.size < 5) return
        val ws = socket
        // Never build a backlog on a slow link: newer rows matter more.
        if (ws == null || ws.queueSize() > 32_000) { droppedRows += batch.size }
        else if (ws.send(PodiumEncoder.samples(batch))) sentRows += batch.size
        else droppedRows += batch.size
        batch.clear()
    }

    private fun connect() {
        if (stopped) return
        val gen = ++generation
        val request = Request.Builder().url(urls[index]).build()
        socket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) = post(gen) {
                webSocket.send(PodiumEncoder.hello(clientId))
                webSocket.send(PodiumEncoder.meta())
                connected = true; failuresInRow = 0; batch.clear()
            }
            override fun onMessage(webSocket: WebSocket, text: String) {
                if (text.contains("\"type\":\"error\"")) post(gen) { lastError = text.take(160) }
            }
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) =
                post(gen) { lastError = t.toString().take(160); next() }
            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                webSocket.close(1000, null)
            }
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) = post(gen) { next() }
        })
    }

    private fun post(gen: Int, block: () -> Unit) {
        handler.post { if (gen == generation && !stopped) block() }
    }

    private fun next() {
        connected = false; socket = null; batch.clear()
        generation++ // ignore late callbacks from the old socket
        failuresInRow++
        index = (index + 1) % urls.size
        val delay = if (failuresInRow >= urls.size) { failuresInRow = 0; 3000L } else 0L
        handler.postDelayed({ connect() }, delay)
    }
}
