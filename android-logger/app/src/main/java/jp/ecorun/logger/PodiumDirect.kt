package jp.ecorun.logger

import java.io.BufferedReader
import java.io.IOException
import java.io.InputStreamReader
import java.io.OutputStream
import java.net.InetSocketAddress
import java.net.Socket
import java.util.concurrent.ArrayBlockingQueue
import java.util.concurrent.TimeUnit

/**
 * Sends rows straight to Podium (plain TCP, one JSON per line; see
 * hardware_share_20261004_podium.md and EcoCapture-Web/podium.py) for when
 * neither relay server answers. The streaming key is entered on this phone
 * only for this. Runs on its own threads so [offer] never holds up the 100 ms
 * row loop. Live-only like the relay: rows that cannot go now are dropped
 * (the CSV keeps everything). Never put the key in [lastError] or a log.
 */
class PodiumDirect(private val key: String, private val host: String = HOST, private val port: Int = PORT) {
    @Volatile var authenticated = false; private set
    @Volatile var lastError = ""; private set
    @Volatile var sentRows = 0L; private set
    @Volatile private var running = true
    @Volatile private var socket: Socket? = null
    private val queue = ArrayBlockingQueue<String>(QUEUE)
    private val thread = Thread({ loop() }, "podium-direct").apply { isDaemon = true; start() }

    /** Queues one encoded row ([PodiumEncoder.row]); dropped unless signed in. */
    fun offer(row: String) {
        if (!authenticated) return
        while (!queue.offer(row)) queue.poll() // a slow link keeps the newest rows
    }

    fun stop() {
        running = false; authenticated = false
        try { socket?.close() } catch (_: IOException) {}
        thread.interrupt()
    }

    private fun loop() {
        while (running) {
            try {
                session()
            } catch (_: InterruptedException) {
                break
            } catch (e: Exception) {
                if (running) lastError = e.message ?: e.javaClass.simpleName
            }
            authenticated = false
            try { socket?.close() } catch (_: IOException) {}
            if (!running) break
            try { Thread.sleep(RETRY_MS) } catch (_: InterruptedException) { break }
        }
    }

    private fun session() {
        val s = Socket().also { socket = it }
        try {
            s.connect(InetSocketAddress(host, port), CONNECT_MS)
        } catch (e: IOException) {
            throw IOException("Podiumにつながりません（${e.javaClass.simpleName}）")
        }
        // Podium sends a heartbeat about every 5 s: this long without a line means the link is gone.
        s.soTimeout = SILENT_MS
        val out = s.getOutputStream()
        val input = BufferedReader(InputStreamReader(s.getInputStream(), Charsets.US_ASCII))
        send(out, PodiumEncoder.directAuth(key))
        while (true) {
            // A wrong key gets no answer: Podium just closes the connection after about 1 s.
            val line = input.readLine() ?: throw IOException("Podiumに切られました（キーが違う可能性）")
            if (!line.contains("\"status\"")) continue
            if (line.contains("\"ok\"")) break
            throw IOException("Podiumの認証に失敗しました")
        }
        send(out, PodiumEncoder.directMeta())
        queue.clear()
        authenticated = true; lastError = ""
        // Heartbeats are read (and ignored) on their own thread; silence or a close ends the session.
        Thread({
            try { while (running && input.readLine() != null) Unit } catch (_: IOException) {}
            try { s.close() } catch (_: IOException) {}
        }, "podium-heartbeat").apply { isDaemon = true; start() }
        var tick = 0L
        while (running && !s.isClosed) {
            val row = queue.poll(1, TimeUnit.SECONDS) ?: continue
            send(out, PodiumEncoder.directSample(row, tick++))
            sentRows++
        }
        if (running) throw IOException("Podiumとの接続が切れました")
    }

    private fun send(out: OutputStream, line: String) {
        out.write((line + "\n").toByteArray(Charsets.US_ASCII))
        out.flush()
    }

    companion object {
        const val HOST = "telemetry.podium.live"
        const val PORT = 8080
        private const val CONNECT_MS = 10_000
        private const val SILENT_MS = 15_000
        private const val RETRY_MS = 3_000L
        private const val QUEUE = 50
    }
}
