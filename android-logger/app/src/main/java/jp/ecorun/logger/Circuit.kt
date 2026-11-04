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
 *
 * The warnings as the DASH: oil pressure low for the engine speed, oil 120 C, water 110 C, each on
 * or off by itself and shown side by side in one red band (oil pressure first); a new one sounds
 * about ten seconds of alarm and flashes the band for a minute (a straight comes in that time).
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
    /** Oil pressure (kPa, OilPress) and the engine speed it is judged against; null until wired. */
    val press: Double? = null,
    val rpm: Double? = null,
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
    /**
     * Oil pressure (kPa) too low for the engine speed (dash_model oil_press_warn): (rpm, kPa) points,
     * straight between them and flat outside; not judged below [oilPressMinRpm] (a hot idle is 80-100 kPa).
     */
    val oilPressWarn: List<Pair<Double, Double>> = listOf(1500.0 to 100.0, 3000.0 to 200.0),
    val oilPressMinRpm: Double = 1500.0,
    val pressHoldOnS: Double = 0.5,
    /** The band flashes this long after a warning comes on (0: never); a minute takes in a straight. */
    val flashS: Double = 60.0,
    val deltaFullScaleS: Double = 2.0,
    val staleS: Double = 2.0,
    /** Fewer minutes of video left than this (a 120-minute race with the grid and the cool-down lap): yellow. */
    val videoWarnMin: Double = 130.0,
)

enum class Kind { FASTER, SLOWER, EVEN, PIT, OK, WARN }

/** One warning in the band: 油圧 85 kPa, 油温 122 ℃. */
data class WarnItem(val label: String, val value: String, val unit: String)

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
    /** Null until the oil pressure has come once (not wired): its light then says nothing of it. */
    val pressSensor: Boolean? = null,
    /** The oil sensors' light: its text and whether all is well. */
    val sensor: Pair<String, Boolean> = "油温センサー途絶" to false,
    val warn: Boolean = false,
    /** A warning came on less than flashS ago: the band flashes. */
    val warnFlash: Boolean = false,
    /** Every warning that is on, oil pressure first. */
    val warns: List<WarnItem> = emptyList(),
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

/** dash_model.press_limit: the lowest oil pressure (kPa) taken as healthy at this engine speed; null where it is not judged. */
fun pressLimit(config: CircuitConfig, rpm: Double?): Double? {
    if (rpm == null || rpm < config.oilPressMinRpm) return null
    val pts = config.oilPressWarn.sortedBy { it.first }
    if (pts.isEmpty()) return null
    if (rpm <= pts[0].first) return pts[0].second
    for (i in 0 until pts.size - 1) {
        val (r0, p0) = pts[i]; val (r1, p1) = pts[i + 1]
        if (rpm <= r1) return if (r1 <= r0) p1 else p0 + (p1 - p0) * (rpm - r0) / (r1 - r0)
    }
    return pts.last().second
}

/** dash_model.Alarm: one warning, on or off with its hold times; [value] the latest reading (kept while the sensor is lost). */
class WarnAlarm(val label: String, val unit: String, private val holdOnS: Double, private val holdOffS: Double) {
    var on = false
        private set
    var value: Double? = null
        private set
    /** When it last came on. */
    var onAt: Double? = null
        private set
    private var since: Double? = null

    /** True at the moment it comes on. */
    fun update(now: Double, bad: Boolean, reading: Double?): Boolean {
        if (reading != null) value = reading
        if (bad == on) { since = null; return false }
        val s = since ?: now.also { since = it }
        if (now - s < if (bad) holdOnS else holdOffS) return false
        on = bad; since = null
        if (bad) onAt = now
        return bad
    }
}

/** dash_model.Warning: the oil pressure, oil temperature and water temperature warnings. */
class Warnings(private val config: CircuitConfig) {
    val press = WarnAlarm("油圧", "kPa", config.pressHoldOnS, config.holdOffS)
    val oil = WarnAlarm("油温", "℃", config.holdOnS, config.holdOffS)
    val water = WarnAlarm("水温", "℃", config.holdOnS, config.holdOffS)
    private val all = listOf(press, oil, water) // the order of the band

    /** True at the moment any warning comes on (one sound each). */
    fun update(now: Double, oil: Double?, water: Double?, press: Double? = null, rpm: Double? = null): Boolean {
        val limit = pressLimit(config, rpm)
        val new = listOf( // all three updated, never cut short
            this.press.update(now, press != null && limit != null && press < limit, press),
            this.oil.update(now, oil != null && oil >= config.oilWarn, oil),
            this.water.update(now, water != null && water >= config.waterWarn, water))
        return new.any { it }
    }

    val on: Boolean get() = all.any { it.on }

    fun active(): List<WarnAlarm> = all.filter { it.on }

    /** A warning came on less than flashS ago (a new one flashes the band again). */
    fun flashing(now: Double): Boolean = all.any { a -> a.on && a.onAt.let { it != null && now - it < config.flashS } }
}

/** The oil sensors' light (dash_model.sensor_light); [press] null: no oil pressure yet (not wired), so not mentioned. */
fun sensorLight(oil: Boolean, press: Boolean?): Pair<String, Boolean> = when {
    press == null -> if (oil) "油温センサー" to true else "油温センサー途絶" to false
    oil && press -> "油温・油圧" to true
    oil -> "油圧センサー途絶" to false
    press -> "油温センサー途絶" to false
    else -> "油温・油圧途絶" to false
}

/** dash_model.DashModel: [update] once per frame (or with null when none came), times in seconds. */
class CircuitModel(val config: CircuitConfig = CircuitConfig(), val lapRef: LapRef = LapRef()) {
    val warning = Warnings(config)
    var lastGood: Double? = null
        private set
    /** The oil pressure has come at least once (until then its light says nothing). */
    var pressSeen = false
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
        val press = if (live) f?.press else null; val rpm = if (live) f?.rpm else null
        if (press != null) pressSeen = true
        val pressSensor = if (pressSeen) press != null else null
        val sound = warning.update(now, oil, water, press, rpm)
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
            pressSensor = pressSensor,
            sensor = sensorLight(oil != null, pressSensor),
            warn = warning.on,
            warnFlash = warning.flashing(now),
            warns = warning.active().map { a -> WarnItem(a.label, a.value?.let { "%.0f".format(Locale.ROOT, it) } ?: "--", a.unit) },
        ) to sound
    }

    private fun kind(s: Double) = if (s > 0.005) Kind.SLOWER else if (s < -0.005) Kind.FASTER else Kind.EVEN

    companion object {
        const val STOPPED_KMH = 10.0 // slower than this the gap to the best lap means nothing (in the pit, on the grid)
    }
}

/**
 * dash_model.tone_wav's warning, as 16-bit mono samples: [repeat] bursts of a two-tone alarm, 1.5 s
 * each and 0.25 s apart (six: about ten seconds; a break between bursts is heard better than one long tone).
 */
object AlarmTone {
    const val RATE = 22050

    fun samples(volume: Double = 0.8, repeat: Int = 6): ShortArray {
        val burst = List(3) { listOf(1000 to .25, 750 to .25) }.flatten()
        val parts = (0 until max(1, repeat)).flatMap { if (it == 0) burst else listOf(0 to .25) + burst }
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
