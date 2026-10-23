package jp.ecorun.logger

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.ServerSocket

/** Against a stand-in Podium on this machine (never the real one). */
class PodiumDirectTest {
    private fun waitFor(ms: Long, ok: () -> Boolean): Boolean {
        val end = System.currentTimeMillis() + ms
        while (System.currentTimeMillis() < end) { if (ok()) return true; Thread.sleep(20) }
        return ok()
    }

    @Test
    fun signsInSendsMetaThenNumberedSamples() {
        ServerSocket(0).use { server ->
            val lines = ArrayList<String>()
            val podium = Thread {
                server.accept().use { s ->
                    val input = BufferedReader(InputStreamReader(s.getInputStream()))
                    val out = s.getOutputStream()
                    lines.add(input.readLine())
                    out.write("{\"status\":\"ok\",\"utc\":1792700000000,\"lt\":0}\n".toByteArray()); out.flush()
                    repeat(3) { lines.add(input.readLine()) }
                }
            }.apply { start() }
            val direct = PodiumDirect("TESTKEY1", "127.0.0.1", server.localPort)
            try {
                assertTrue(waitFor(3000) { direct.authenticated })
                val row = PodiumEncoder.row(mapOf("Interval" to 100.0, "Utc" to 1.7927e12))
                direct.offer(row); direct.offer(row)
                podium.join(3000)
            } finally { direct.stop() }
            assertEquals(4, lines.size)
            assertTrue(lines[0].startsWith("{\"cmd\":{\"auth\":{\"deviceId\":\"TESTKEY1\",\"apiVer\":1.1"))
            assertTrue(lines[1].startsWith("{\"s\":{\"meta\":[{\"nm\":\"Interval\""))
            assertEquals("{\"s\":{\"d\":[100,1792700000000,3],\"t\":0}}", lines[2])
            assertEquals("{\"s\":{\"d\":[100,1792700000000,3],\"t\":1}}", lines[3])
        }
    }

    /** A wrong key gets no answer, only a closed connection: say so, and do not take rows. */
    @Test
    fun wrongKeyIsReportedAndNothingIsQueued() {
        ServerSocket(0).use { server ->
            Thread { server.accept().use { s -> BufferedReader(InputStreamReader(s.getInputStream())).readLine() } }.start()
            val direct = PodiumDirect("WRONGKEY", "127.0.0.1", server.localPort)
            try {
                assertTrue(waitFor(3000) { direct.lastError.isNotEmpty() })
                assertFalse(direct.authenticated)
                assertTrue(direct.lastError.contains("キー"))
                assertFalse(direct.lastError.contains("WRONGKEY"))
            } finally { direct.stop() }
        }
    }
}
