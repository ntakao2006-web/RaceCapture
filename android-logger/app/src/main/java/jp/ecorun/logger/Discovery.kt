package jp.ecorun.logger

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import java.net.Inet4Address
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.NetworkInterface
import java.net.Socket
import java.util.concurrent.Callable
import java.util.concurrent.ExecutionException
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicReference

/**
 * Finds the Ver.2 logger's course-walk server (field.py, port 8082) when it is not this phone's
 * access point: on a Wi-Fi both are on, or on this phone's own hotspot with the logger as a client.
 * The hotspot gives the logger whatever address it likes and Android lets no app list the clients,
 * so every address of the phone's own /24 is tried: a port that answers /api/field/state with 200
 * to the key is the logger (32 at a time, 300 ms each: about 3 s for a /24).
 */
object Discovery {
    sealed class Result {
        /** [network] is the Wi-Fi to bind to, null on this phone's hotspot (routed without one). */
        data class Found(val host: String, val network: Network?) : Result()
        data class WrongKey(val host: String) : Result()
        data class NotFound(val searched: String) : Result()
    }

    const val PORT = 8082
    /** Mobile data, VPN, clat and loopback: never where the logger is. */
    private val SKIP = listOf("rmnet", "ccmni", "v4-", "clat", "tun", "ppp", "ipsec", "dummy", "lo", "radio", "seth")

    /** The hosts .1 to .254 of the /24 around [own], without [own] itself. */
    fun hostsAround(own: ByteArray): List<String> {
        val base = "${own[0].toInt() and 255}.${own[1].toInt() and 255}.${own[2].toInt() and 255}."
        return (1..254).filter { it != (own[3].toInt() and 255) }.map { base + it }
    }

    /** IPv4 addresses of the Wi-Fi, hotspot, USB and Ethernet interfaces, with the interface names. */
    private fun ownAddresses(): List<Pair<String, Inet4Address>> = try {
        NetworkInterface.getNetworkInterfaces().toList()
            .filter { i -> i.isUp && SKIP.none { i.name.startsWith(it) } }
            .flatMap { i -> i.inetAddresses.toList().filterIsInstance<Inet4Address>().filter { it.isSiteLocalAddress }.map { i.name to it } }
    } catch (_: Exception) { emptyList() }

    /** The Wi-Fi network whose subnet holds [host], to bind to (the default network may be LTE). */
    fun networkFor(context: Context, host: String): Network? {
        val cm = context.getSystemService(ConnectivityManager::class.java)
        val target = try { InetAddress.getByName(host) as? Inet4Address } catch (_: Exception) { null } ?: return null
        @Suppress("DEPRECATION")
        for (n in cm.allNetworks) {
            val caps = cm.getNetworkCapabilities(n) ?: continue
            if (!caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) && !caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)) continue
            val props = cm.getLinkProperties(n) ?: continue
            if (props.linkAddresses.any { la -> (la.address as? Inet4Address)?.let { sameSubnet(it, target, la.prefixLength) } == true }) return n
        }
        return null
    }

    private fun sameSubnet(a: Inet4Address, b: Inet4Address, prefix: Int): Boolean {
        val x = a.address; val y = b.address
        for (bit in 0 until prefix.coerceIn(0, 32)) {
            val m = 0x80 ushr (bit % 8)
            if ((x[bit / 8].toInt() and m) != (y[bit / 8].toInt() and m)) return false
        }
        return true
    }

    /** HTTP status of GET /api/field/state with the key, or null when nothing answers there. */
    private fun probe(host: String, key: String, network: Network?, timeoutMs: Int): Int? = try {
        Socket().use { s ->
            network?.bindSocket(s)
            s.connect(InetSocketAddress(host, PORT), timeoutMs)
            s.soTimeout = 2000
            s.getOutputStream().write(("GET /api/field/state HTTP/1.1\r\nHost: $host\r\nX-Field-Key: $key\r\n" +
                "Connection: close\r\n\r\n").toByteArray())
            s.getInputStream().bufferedReader().readLine()?.split(' ')?.getOrNull(1)?.toIntOrNull()
        }
    } catch (_: Exception) { null }

    /** Blocking (call it off the main thread): [first] (typed or last found) alone, then the subnets. */
    fun find(context: Context, key: String, first: String): Result {
        val wrong = AtomicReference<String?>(null) // a host that refused the key, for the message
        fun check(host: String, network: Network?, timeoutMs: Int): Boolean = when (probe(host, key, network, timeoutMs)) {
            200 -> true
            403 -> { wrong.set(host); false }
            else -> false
        }
        if (first.isNotEmpty()) {
            val network = networkFor(context, first)
            if (check(first, network, 1500)) return Result.Found(first, network)
        }
        val own = ownAddresses()
        // One lookup per subnet: the hosts of a /24 share the phone's network there.
        val hosts = own.flatMap { (_, a) -> val n = networkFor(context, a.hostAddress!!); hostsAround(a.address).map { it to n } }
            .distinctBy { it.first }.filter { it.first != first }
        val searched = own.joinToString("・") { (name, a) -> "$name ${a.hostAddress}/24" }.ifEmpty { "Wi-Fi・テザリングのアドレスなし" }
        if (hosts.isNotEmpty()) {
            val pool = Executors.newFixedThreadPool(32)
            try {
                return pool.invokeAny(hosts.map { (h, n) -> Callable { if (check(h, n, 300)) Result.Found(h, n) else throw IllegalStateException() } })
            } catch (_: ExecutionException) {
            } catch (_: InterruptedException) {
            } finally { pool.shutdownNow() }
        }
        return wrong.get()?.let { Result.WrongKey(it) } ?: Result.NotFound(searched)
    }
}
