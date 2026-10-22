package jp.ecorun.logger

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.Typeface
import android.view.View
import kotlin.math.abs
import kotlin.math.floor

/** Everything the driver screen shows, built by the activity a few times a second. */
data class Dash(
    val running: Boolean = false,
    val recSeconds: Long = 0,
    val recordingOk: Boolean = true,
    val fix: Int = 0,
    val sats: Int = 0,
    val accuracyM: Double? = null,
    val speedKmh: Double? = null,
    val relay: String? = null,
    val relayConnected: Boolean = false,
    val batteryPct: Int? = null,
    val charging: Boolean = false,
    val lap: LapValues? = null,
    val config: LapConfig = LapConfig(),
    val laps: List<Double> = emptyList(),
    val warning: String? = null,
    val classCode: String = "",
    val reference: String = "",
)

/**
 * Landscape driver screen, drawn directly so the numbers can be as large as the
 * phone allows: speed on the left, laps and race clocks on the right, a status
 * strip on top. The bottom [bottomReservePx] is left for the activity's buttons.
 */
class DashboardView(context: Context) : View(context) {
    var dash = Dash()
        set(v) { field = v; invalidate() }
    var bottomReservePx = 0f

    private val bg = Color.rgb(9, 12, 16)
    private val tile = Color.rgb(22, 28, 36)
    private val label = Color.rgb(139, 148, 158)
    private val white = Color.rgb(240, 246, 252)
    private val green = Color.rgb(63, 185, 80)
    private val yellow = Color.rgb(230, 180, 40)
    private val red = Color.rgb(248, 81, 73)
    private val grey = Color.rgb(110, 118, 129)

    private val bold = Typeface.create("sans-serif-condensed", Typeface.BOLD)
    private val normal = Typeface.create("sans-serif", Typeface.NORMAL)
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply { fontFeatureSettings = "tnum" }
    private val rect = RectF()

    override fun onDraw(c: Canvas) {
        val w = width.toFloat(); val h = height.toFloat()
        c.drawColor(bg)
        val pad = h * 0.025f
        val d = dash

        // Status strip.
        val stripH = h * 0.13f
        val chipW = (w - pad * 5) / 4
        val rec = if (d.running) (if (d.recordingOk) "● " + clock(d.recSeconds.toDouble(), false) else "記録できていません") else "停止中"
        chip(c, pad, pad, chipW, stripH, "記録", rec, if (!d.running) grey else if (d.recordingOk) red else red)
        val gnssColor = when { d.fix == 0 -> red; d.fix == 2 || (d.accuracyM ?: 99.0) > 10 -> yellow; else -> green }
        val gnss = if (d.fix == 0) "測位なし" else "${if (d.fix == 3) "3D" else "2D"} ${d.sats}衛星" + (d.accuracyM?.let { " ±%.0fm".format(it) } ?: "")
        chip(c, pad * 2 + chipW, pad, chipW, stripH, "GNSS", if (d.running) gnss else "—", if (d.running) gnssColor else grey)
        val relayColor = when { d.relay == null -> grey; !d.relayConnected -> red; d.relay == "主" -> green; else -> yellow }
        chip(c, pad * 3 + chipW * 2, pad, chipW, stripH, "送信", if (!d.running) "—" else d.relay ?: "なし", if (d.running) relayColor else grey)
        val bat = d.batteryPct
        val batColor = when { bat == null -> grey; d.charging -> green; bat < 20 -> red; bat < 40 -> yellow; else -> white }
        chip(c, pad * 4 + chipW * 3, pad, chipW, stripH, "電池", (bat?.let { "$it%" } ?: "—") + if (d.charging) " 充電中" else "", batColor)

        var top = pad * 2 + stripH
        d.warning?.let {
            val bh = h * 0.085f
            paint.color = red; rect.set(pad, top, w - pad, top + bh); c.drawRoundRect(rect, bh / 4, bh / 4, paint)
            text(c, it, rect, white, normal, 0.6f)
            top += bh + pad
        }
        val bottom = h - bottomReservePx - pad

        // Speed.
        val leftW = w * 0.40f
        rect.set(pad, top, leftW, bottom)
        val speedText = d.speedKmh?.let { "%.0f".format(it) } ?: "—"
        val speedRect = RectF(rect.left, rect.top, rect.right, rect.top + rect.height() * 0.80f)
        text(c, speedText, speedRect, if (d.running && d.speedKmh != null) white else grey, bold, 0.98f)
        text(c, "km/h", RectF(rect.left, speedRect.bottom, rect.right, rect.bottom), label, normal, 0.7f)

        // Lap tiles 2 x 2.
        val gx = leftW + pad; val gw = (w - pad - gx - pad) / 2; val gh = (bottom - top - pad) / 2
        val cfg = d.config; val v = d.lap
        val total = cfg.totalLaps
        val hasLine = cfg.control != null

        // Lap count.
        val (lapValue, lapSub) = when {
            !hasLine -> "—" to "ラインが未設定"
            v == null -> "—" to ""
            v.finished -> "ゴール" to "${v.count}周 " + (v.raceS?.let { clock(it, true) } ?: "")
            v.current == 0 -> (if (total != null) "0 / $total" else "0") to "スタート前"
            else -> (if (total != null) "${v.current} / $total" else "${v.current}") to (v.lapsLeft?.let { "残り${it}周" } ?: "")
        }
        tileBox(c, gx, top, gw, gh, listOf("周回", d.classCode, d.reference).filter { it.isNotEmpty() }.joinToString("　"), lapValue, lapSub, white, label)

        // Race clock.
        val limit = cfg.timeLimitS
        if (limit != null) {
            val race = v?.raceS
            val rem = if (race == null) limit else limit - race
            val margin = if (cfg.marginS > 0 && cfg.raceDistanceM != null) "　余裕${"%.0f".format(cfg.marginS)}秒" else ""
            val sub = (if (race == null) "スタート前" else "経過 " + clock(race, false)) + margin
            tileBox(c, gx + gw + pad, top, gw, gh, "残り時間", (if (rem < 0) "+" else "") + clock(abs(rem), false), sub,
                if (rem < 0) red else if (rem < 120) yellow else white, label)
        } else {
            tileBox(c, gx + gw + pad, top, gw, gh, "経過", v?.raceS?.let { clock(it, false) } ?: "—", "", white, label)
        }

        if (cfg.raceDistanceM != null && total != null && limit != null) speedTiles(c, gx, top + gh + pad, gw, gh, pad, d)
        else timeTiles(c, gx, top + gh + pad, gw, gh, pad, d)
    }

    /**
     * Eco-run pacing ([Pace]): the average speed this lap needs to finish on
     * time (set when the lap starts, so it holds still while the driver works
     * to it), and beside it this lap's running average, which moves as the
     * lap goes on, green at or above the target and yellow below.
     */
    private fun speedTiles(c: Canvas, x: Float, y: Float, w: Float, h: Float, pad: Float, d: Dash) {
        val cfg = d.config; val v = d.lap
        val index = v?.count ?: 0
        val running = v != null && !v.finished && v.current > 0
        val target = if (v?.finished == true) null else Pace.targetKmh(cfg, d.laps, index)
        val banked = if (v != null && v.count > 0) Pace.bankedS(cfg, d.laps, v.count) else null
        val (targetSub, targetSubColor) = when {
            v?.finished == true -> "ゴール" to label
            target == null -> (v?.raceS?.let { if (it < (cfg.timeLimitS ?: 0.0)) "余裕を使い切りました" else "規定時間を過ぎました" } ?: "") to red
            banked != null -> "貯金 " + (if (banked >= 0) "+" else "−") + clock(abs(banked), false) to (if (banked >= 0) green else red)
            running -> "" to label
            else -> "スタート前" to label
        }
        tileBox(c, x, y, w, h, "この周の目標 平均km/h", target?.let { "%.1f".format(it) } ?: "—", targetSub, white, targetSubColor)

        val elapsed = v?.elapsedS
        val avg = if (running && elapsed != null && elapsed >= 5) v!!.lapDistM / elapsed * 3.6 else null
        val (avgSub, avgColor) = when {
            avg == null -> (if (running) "計測中" else if (v?.finished == true) "ゴール" else "スタート前") to white
            target == null -> "" to white
            else -> "目標比 " + signed(avg - target) to (if (avg >= target) green else yellow)
        }
        tileBox(c, x + w + pad, y, w, h, "この周の平均 km/h", avg?.let { "%.1f".format(it) } ?: "—", avgSub,
            if (avg == null) white else avgColor, if (avg == null) label else avgColor)
    }

    private fun signed(kmh: Double) = (if (kmh >= 0) "+" else "−") + "%.1f".format(abs(kmh))

    /** Without a regulation distance: lap times against an even share of the time limit. */
    private fun timeTiles(c: Canvas, x: Float, y: Float, w: Float, h: Float, pad: Float, d: Dash) {
        val cfg = d.config; val v = d.lap
        val limit = cfg.timeLimitS; val total = cfg.totalLaps
        // Current lap against the pace that still makes the time limit.
        val elapsed = v?.elapsedS
        val target = if (v != null && !v.finished && limit != null && total != null && v.raceS != null && elapsed != null) {
            val lapsToGo = total - v.count
            if (lapsToGo > 0) (limit - (v.raceS - elapsed)) / lapsToGo else null
        } else null
        tileBox(c, x, y, w, h, "今の周", elapsed?.let { clock(it, true) } ?: "—",
            target?.let { "目標 " + clock(it, false) } ?: "",
            if (target != null && elapsed != null && elapsed > target) yellow else white, label)

        // Previous lap and the time banked against an even pace.
        val savings = if (v != null && limit != null && total != null && v.count > 0) v.count * (limit / total) - d.laps.sum() else null
        val savingsText = savings?.let { "貯金 " + (if (it >= 0) "+" else "−") + clock(abs(it), false) } ?: (v?.bestS?.let { "ベスト " + clock(it, true) } ?: "")
        tileBox(c, x + w + pad, y, w, h, "前回", v?.lastS?.let { clock(it, true) } ?: "—",
            savingsText, white, if (savings == null) label else if (savings >= 0) green else red)
    }

    private fun chip(c: Canvas, x: Float, y: Float, w: Float, h: Float, name: String, value: String, color: Int) {
        paint.color = tile; rect.set(x, y, x + w, y + h); c.drawRoundRect(rect, h / 5, h / 5, paint)
        val lw = w * 0.28f
        text(c, name, RectF(x, y, x + lw, y + h), label, normal, 0.42f)
        text(c, value, RectF(x + lw, y, x + w - h * 0.15f, y + h), color, bold, 0.6f)
    }

    private fun tileBox(c: Canvas, x: Float, y: Float, w: Float, h: Float, name: String, value: String, sub: String,
                        valueColor: Int, subColor: Int) {
        paint.color = tile; rect.set(x, y, x + w, y + h); c.drawRoundRect(rect, h / 12, h / 12, paint)
        val inset = h * 0.06f
        paint.typeface = normal; paint.color = label; paint.textAlign = Paint.Align.LEFT
        paint.textSize = h * 0.13f
        val room = w - inset * 3
        val wide = paint.measureText(name)
        if (wide > room) paint.textSize *= room / wide
        c.drawText(name, x + inset * 1.5f, y + inset + paint.textSize, paint)
        text(c, value, RectF(x + inset, y + h * 0.22f, x + w - inset, y + h * 0.78f), valueColor, bold, 0.95f)
        if (sub.isNotEmpty()) text(c, sub, RectF(x + inset, y + h * 0.76f, x + w - inset, y + h - inset), subColor, normal, 0.85f)
    }

    /** Centred text as large as fits [r]; [fill] is the share of the box height to use. */
    private fun text(c: Canvas, s: String, r: RectF, color: Int, face: Typeface, fill: Float) {
        paint.typeface = face; paint.color = color; paint.textAlign = Paint.Align.CENTER
        paint.textSize = r.height() * fill
        val wide = paint.measureText(s)
        if (wide > r.width() * 0.96f) paint.textSize *= r.width() * 0.96f / wide
        val fm = paint.fontMetrics
        c.drawText(s, r.centerX(), r.centerY() - (fm.ascent + fm.descent) / 2, paint)
    }

    companion object {
        /** m:ss (or h:mm:ss), with tenths when [tenths]. */
        fun clock(seconds: Double, tenths: Boolean): String {
            val t = if (tenths) floor(seconds * 10) / 10 else floor(seconds)
            val h = (t / 3600).toInt(); val m = ((t % 3600) / 60).toInt(); val s = t % 60
            val sec = if (tenths) "%04.1f".format(s) else "%02d".format(s.toInt())
            return if (h > 0) "%d:%02d:%s".format(h, m, sec) else "%d:%s".format(m, sec)
        }
    }
}
