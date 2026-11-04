package jp.ecorun.logger

import java.io.File
import java.time.Instant
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.floor
import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin

/*
 * The circuit screen (SUGO 120-minute endurance, task_sugo_20261108_breakdown.md SG-2-8): the
 * spare of EcoCapture DASH (RaceCapture-UNOQ/dash_model.py) for when the car's monitor or the
 * DASH fails. It shows what the DASH shows, worked out the same way from the same values, which
 * the Ver.2 logger sends in the `dash` block of its course-walk stream (EcoCapture-Web field.py
 * dash_frame). The laps are the logger's own (lap.py): this phone times nothing here.
 */

/** One frame of the logger (field.py's live frame and its `dash` block); times as lap.py sends them, in minutes. */
data class CircuitInput(
    val connected: Boolean,
    val rec: Boolean = false,
    val lat: Double? = null,
    val lon: Double? = null,
    val speedKmh: Double? = null,
    val currentLap: Double? = null,
    val elapsedMin: Double? = null,
    val lastMin: Double? = null,
    val bestMin: Double? = null,
    val raceMin: Double? = null,
    val diffS: Double? = null,
    val lastPit: Boolean = false,
    val startPit: Boolean = false,
    val oil: Double? = null,
    val water: Double? = null,
    val utc: String? = null,
    /** null from an EcoCapture without the video summary. */
    val video: CircuitVideo? = null,
)

data class CircuitVideo(val recording: Boolean, val minutesLeft: Double?)

/** dash_model.DEFAULTS: oil 120 C (ncec-roadster track/thermal-limits.md), water 10 C lower (oil ~ water + 10 C). */
data class CircuitConfig(
    val oilWarn: Double = 120.0,
    val waterWarn: Double = 110.0,
    val holdOnS: Double = 1.0,
    val holdOffS: Double = 5.0,
    val deltaFullScaleS: Double = 2.0,
    val staleS: Double = 2.0,
    /** Fewer minutes of video left than this (a 120-minute race with the grid and the cool-down lap): yellow. */
    val videoWarnMin: Double = 130.0,
)

enum class Kind { FASTER, SLOWER, EVEN, PIT, OK, WARN }

/** Everything the circuit screen shows (dash_model.DashModel.update's state). */
data class CircuitState(
    val stale: Boolean = true,
    val staleS: Double? = null,
    val lapNow: String = "--",
    val notice: String = "",
    val delta: String = "--",
    val deltaKind: Kind? = null,
    val deltaFrac: Double? = null,
    val last: String = "--",
    val lastNote: String = "",
    val lastNoteKind: Kind? = null,
    val best: String = "--",
    val lapNo: String = "--",
    val elapsed: String = WAITING,
    val clock: String = "--:--",
    val rec: Boolean = false,
    val video: String = "",
    val videoKind: Kind? = null,
    val gnss: Boolean = false,
    val oilSensor: Boolean = false,
    val warn: Boolean = false,
    val warnLabel: String? = null,
    val warnValue: String? = null,
) {
    companion object { const val WAITING = "スタート待ち" }
}

object CircuitFormat {
    /** 1:52.34 (or 1:12.3 with digits = 1), cut, never rounded up. */
    fun lap(seconds: Double?, digits: Int = 2): String {
        if (seconds == null || seconds < 0) return "--"
        val scale = if (digits == 1) 10L else 100L
        val total = floor(seconds * scale + 1e-6).toLong()
        val minutes = total / (60 * scale); val rest = total % (60 * scale)
        return "%d:%02d.%0${digits}d".format(Locale.ROOT, minutes, rest / scale, rest % scale)
    }

    fun hms(seconds: Double?): String {
        if (seconds == null || seconds < 0) return "--"
        val t = seconds.toLong()
        return "%d:%02d:%02d".format(Locale.ROOT, t / 3600, t / 60 % 60, t % 60)
    }

    /** +0.41 / −0.84 (U+2212, as wide as +); +38.4 and +123 once the hundredths stop mattering. */
    fun signed(seconds: Double?): String {
        if (seconds == null) return "--"
        if (abs(seconds) < 0.005) return "0.00"
        val size = abs(seconds)
        return (if (seconds > 0) "+" else "−") + "%.${if (size < 10) 2 else if (size < 100) 1 else 0}f".format(Locale.ROOT, size)
    }

    fun utc(text: String?): Instant? {
        if (text.isNullOrEmpty()) return null
        return try { OffsetDateTime.parse(text).toInstant() } catch (_: Exception) {
            try { LocalDateTime.parse(text).toInstant(ZoneOffset.UTC) } catch (_: Exception) { null }
        }
    }

    val JST: ZoneId = ZoneOffset.ofHours(9)
    val CLOCK: DateTimeFormatter = DateTimeFormatter.ofPattern("HH:mm").withZone(JST)
}

/**
 * dash_model.LapRef (lap_ref.h's lr_update): the gap (s) to the best lap at the same place on
 * the track. The best lap's track is kept in [file] (one "lat lon elapsed" line per point after
 * a "lap time" line), so a restart of the app keeps the gap.
 */
open class LapRef(private val file: File? = null) {
    data class Point(val lat: Double, val lon: Double, val el: Double)
    class Ref(val no: Int, val timeS: Double, val pts: List<Point>)

    private var cur = ArrayList<Point>()
    private var curNo = -1
    private var idx = 0
    var ref: Ref? = null
        private set
    var delta: Double? = null
        private set

    init { load() }

    private fun load() {
        val f = file ?: return
        ref = try {
            val lines = f.readLines().filter { it.isNotBlank() }
            val head = lines.first().split(' ')
            val pts = lines.drop(1).map { l -> l.split(' ').let { Point(it[0].toDouble(), it[1].toDouble(), it[2].toDouble()) } }
            if (pts.size in 2..MAX) Ref(head[0].toInt(), head[1].toDouble(), pts) else null
        } catch (_: Exception) { null }
    }

    private fun save() {
        val f = file ?: return
        val r = ref ?: return
        try {
            val temp = File(f.path + ".tmp")
            temp.writeText(buildString {
                append(r.no).append(' ').append(r.timeS).append('\n')
                for (p in r.pts) append(p.lat).append(' ').append(p.lon).append(' ').append(p.el).append('\n')
            })
            if (!temp.renameTo(f)) { f.delete(); temp.renameTo(f) }
        } catch (_: Exception) {}
    }

    /** (distance m, segment i, position u along it) of the best lap's track nearest (lat, lon). */
    private fun nearest(lat: Double, lon: Double, lo: Int, hi: Int): Triple<Double, Int, Double> {
        val pts = ref!!.pts
        val kx = cos(Math.toRadians(lat)) * 111320.0; val ky = 111320.0
        var best = Triple(Double.POSITIVE_INFINITY, 0, 0.0)
        for (i in lo until min(hi, pts.size - 1)) {
            val bx = (pts[i + 1].lon - pts[i].lon) * kx; val by = (pts[i + 1].lat - pts[i].lat) * ky
            val px = (lon - pts[i].lon) * kx; val py = (lat - pts[i].lat) * ky
            val l2 = bx * bx + by * by
            val u = if (l2 > 0) min(max((px * bx + py * by) / l2, if (i == 0) -1.0 else 0.0), if (i + 2 == pts.size) 2.0 else 1.0) else 0.0
            val d = hypot(px - u * bx, py - u * by)
            if (d < best.first) best = Triple(d, i, u)
        }
        return best
    }

    open fun update(lat0: Double?, lon0: Double?, lapNo: Double?, elapsedS: Double?, lastS: Double?, bestS: Double?): Double? {
        val zero = lat0 == 0.0 && lon0 == 0.0 // 0, 0 can come before the first fix
        val lat = if (zero) null else lat0; val lon = if (zero) null else lon0
        val no = lapNo?.toInt() ?: -1
        if (no != curNo) { // a new lap
            val c = cur
            if (curNo > 0 && no == curNo + 1 && lastS != null && c.size in 20 until MAX &&
                c.first().el <= EDGE_S && abs(c.last().el - lastS) <= EDGE_S) { // recorded in full
                if (bestS != null && abs(lastS - bestS) < .01) { // and it is the best lap
                    ref = Ref(curNo, lastS, c.toList()); save()
                }
            }
            cur = ArrayList(); curNo = no; idx = 0
        }
        if (lat != null && lon != null && elapsedS != null && cur.size < MAX && (cur.isEmpty() || elapsedS > cur.last().el)) {
            cur.add(Point(lat, lon, elapsedS))
        }
        delta = null
        val r = ref
        if (r == null || bestS == null || abs(r.timeS - bestS) >= .05 || lat == null || lon == null || elapsedS == null || r.pts.size < 2) return null
        var m = nearest(lat, lon, max(0, idx - 10), idx + 150)
        if (m.first > MATCH_M) m = nearest(lat, lon, 0, r.pts.size) // not near the last match (restart, jump): search the whole lap
        if (m.first > MATCH_M) return null
        idx = m.second
        val p = r.pts; val i = m.second
        delta = elapsedS - (p[i].el + m.third * (p[i + 1].el - p[i].el))
        return delta
    }

    companion object {
        const val MAX = 8192        // points kept per lap (13 min at 10 Hz; a longer lap is never the reference)
        const val MATCH_M = 40.0    // farther than this from the best lap's track: no gap (pit garage, off course)
        const val EDGE_S = 3.0      // a lap recorded to within this of both ends counts as recorded in full
    }
}

/** dash_model.Warning: the oil / water temperature warning with its hold times. */
class TempWarning(private val config: CircuitConfig) {
    var on = false
        private set
    var label: String? = null
        private set
    var value: Double? = null
        private set
    private var since: Double? = null

    /** True at the moment the warning comes on (its one sound). */
    fun update(now: Double, oil: Double?, water: Double?): Boolean {
        val hotOil = oil != null && oil >= config.oilWarn
        val hotWater = water != null && water >= config.waterWarn
        // what the band shows: the one over its limit (oil first), else the oil while it is read
        if (hotOil || (oil != null && !hotWater)) { label = "油温"; value = oil } else { label = "水温"; value = water }
        val hot = hotOil || hotWater
        if (hot == on) { since = null; return false }
        val s = since ?: now.also { since = it }
        if (now - s < if (hot) config.holdOnS else config.holdOffS) return false
        on = hot; since = null
        return hot
    }
}

/** dash_model.DashModel: [update] once per frame (or with null when none came), times in seconds. */
class CircuitModel(val config: CircuitConfig = CircuitConfig(), val lapRef: LapRef = LapRef()) {
    val warning = TempWarning(config)
    var lastGood: Double? = null
        private set

    /** The screen for this frame, and whether the warning sound starts now. */
    fun update(f: CircuitInput?, now: Double, wall: Instant = Instant.now()): Pair<CircuitState, Boolean> {
        val live = f != null && f.connected
        if (live) lastGood = now
        val good = lastGood
        val stale = good == null || now - good > config.staleS
        val minutes = { v: Double? -> v?.times(60) }
        val elapsed = minutes(f?.elapsedMin); val last = minutes(f?.lastMin); val best = minutes(f?.bestMin)
        val race = minutes(f?.raceMin)
        val oil = if (live) f?.oil else null; val water = if (live) f?.water else null
        val sound = warning.update(now, oil, water)
        var delta = if (live) lapRef.update(f?.lat, f?.lon, f?.currentLap, elapsed, last, best) else null
        val stopped = f?.speedKmh?.let { it < STOPPED_KMH } ?: false
        val outLap = f?.startPit == true
        if (outLap || stopped) delta = null // still tracked above, so the reference keeps its place
        // The strip under the running lap is for the pit stop only (the temperature has its own band)
        val notice = if (outLap) (if (stopped) "PIT IN" else "PIT OUT") else ""

        val diff = f?.diffS
        val (note, noteKind) = when {
            f?.lastPit == true -> "PIT" to Kind.PIT
            diff != null -> "前周比 ${CircuitFormat.signed(diff)}s" to kind(diff)
            else -> "" to null
        }
        val clock = CircuitFormat.CLOCK.format(CircuitFormat.utc(f?.utc) ?: wall)
        val current = f?.currentLap
        // How long the burnt-in video can still record. No light from an EcoCapture without the summary.
        val v = f?.video
        val left = v?.minutesLeft
        val (videoText, videoKind) = when {
            v == null -> "" to null
            !v.recording -> "録画なし" to Kind.WARN
            else -> (if (left == null) "録画" else "録画 %d:%02d".format(Locale.ROOT, left.toInt() / 60, left.toInt() % 60)) to
                (if (left == null || left >= config.videoWarnMin) Kind.OK else Kind.WARN)
        }
        val lat = f?.lat; val lon = f?.lon
        return CircuitState(
            stale = stale,
            staleS = good?.let { now - it },
            lapNow = CircuitFormat.lap(elapsed, 1),
            notice = notice,
            delta = CircuitFormat.signed(delta),
            deltaKind = delta?.let { kind(it) },
            deltaFrac = delta?.let { (it / config.deltaFullScaleS).coerceIn(-1.0, 1.0) },
            last = CircuitFormat.lap(last), lastNote = note, lastNoteKind = noteKind,
            best = CircuitFormat.lap(best),
            lapNo = if (current == null || current == 0.0) "--" else current.toInt().toString(),
            elapsed = if (race != null) CircuitFormat.hms(race) else CircuitState.WAITING,
            clock = clock,
            rec = f?.rec == true,
            video = videoText, videoKind = videoKind,
            gnss = lat != null && lon != null && !(lat == 0.0 && lon == 0.0),
            oilSensor = oil != null,
            warn = warning.on,
            warnLabel = warning.label,
            warnValue = warning.value?.let { "%.0f℃".format(Locale.ROOT, it) },
        ) to sound
    }

    private fun kind(s: Double) = if (s > 0.005) Kind.SLOWER else if (s < -0.005) Kind.FASTER else Kind.EVEN

    companion object {
        const val STOPPED_KMH = 10.0 // slower than this the gap to the best lap means nothing (in the pit, on the grid)
    }
}

/** dash_model.tone_wav's warning: a two-tone alarm of two seconds, as 16-bit mono samples. */
object AlarmTone {
    const val RATE = 22050

    fun samples(volume: Double = 0.8): ShortArray {
        val parts = List(4) { listOf(1000 to .25, 750 to .25) }.flatten()
        val amp = volume.coerceIn(0.0, 1.0) * 32000
        val fade = (RATE * .005).toInt()
        val out = ShortArray(parts.sumOf { (RATE * it.second).toInt() })
        var k0 = 0
        for ((freq, length) in parts) {
            val n = (RATE * length).toInt()
            for (k in 0 until n) {
                val gain = min(1.0, min(k.toDouble() / fade, (n - 1 - k).toDouble() / fade))
                out[k0 + k] = (amp * gain * sin(2 * PI * freq * k / RATE)).toInt().toShort()
            }
            k0 += n
        }
        return out
    }
}
