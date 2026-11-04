package jp.ecorun.logger

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Rect
import android.graphics.RectF
import android.graphics.Typeface
import android.os.SystemClock
import android.view.View
import kotlin.math.max
import kotlin.math.min

/** What the circuit screen draws: the model's [s], the cover while the logger's values are missing, the phone's battery. */
data class CircuitScreen(
    val s: CircuitState = CircuitState(),
    /** The big and the small lines over the values; null while they are live. */
    val cover: Pair<String, String>? = null,
    val batteryPct: Int? = null,
    val charging: Boolean = false,
)

/**
 * The circuit screen (landscape), laid out as EcoCapture DASH (ecocapture_dash.py, the same
 * shares, sizes and colours, so a driver who knows one reads the other): the running lap and the
 * gap to the best on top, the last lap, best and lap number in the middle (a red band over them
 * while a warning is on: every one that is on side by side, oil pressure first, flashing bright and
 * dark red for a minute after one comes on), the race time, the clock and the lights at the bottom.
 * The bottom [bottomReservePx] is left for the activity's buttons.
 */
class CircuitView(context: Context) : View(context) {
    var screen = CircuitScreen()
        set(v) { field = v; invalidate() }
    var bottomReservePx = 0f

    private val cellBg = Color.rgb(0x15, 0x15, 0x15)
    private val capColor = Color.rgb(0xa8, 0xa8, 0xa8)
    private val num = Color.rgb(0xf4, 0xf4, 0xf4)
    private val faster = Color.rgb(0x38, 0xe0, 0x5a)
    private val slower = Color.rgb(0xff, 0x4a, 0x4a)
    private val pitNote = Color.rgb(0x5a, 0xae, 0xff)
    private val waiting = Color.rgb(0xff, 0xd0, 0x60)
    private val barBg = Color.rgb(0x2c, 0x2c, 0x2c)
    private val barMid = Color.rgb(0x9a, 0x9a, 0x9a)
    private val barFaster = Color.rgb(0x2f, 0xc6, 0x4c)
    private val barSlower = Color.rgb(0xe8, 0x3a, 0x3a)
    private val pitBlue = Color.rgb(0x1f, 0x64, 0xc8)
    private val banner = Color.rgb(0xe0, 0x14, 0x14)
    private val bannerDim = Color.rgb(0x52, 0x08, 0x08) // the dark half of the flash; the white text stays
    private val coverBg = Color.rgb(0x1a, 0x1a, 0x1a)
    private val coverText = Color.rgb(0xd8, 0xd8, 0xd8)
    private val chipColors = mapOf(
        Kind.OK to (Color.rgb(0x38, 0xe0, 0x5a) to Color.rgb(0x0f, 0x2a, 0x14)),
        Kind.WARN to (Color.rgb(0x1c, 0x10, 0x00) to Color.rgb(0xff, 0xb0, 0x20)),
        Kind.SLOWER to (Color.WHITE to Color.rgb(0xd8, 0x1e, 0x1e)), // the bad light
    )

    private val numFace = Typeface.create("sans-serif-condensed", Typeface.BOLD)
    private val textFace = Typeface.create("sans-serif", Typeface.NORMAL)
    private val textBold = Typeface.create("sans-serif", Typeface.BOLD)
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply { fontFeatureSettings = "tnum" }
    private val rect = RectF()
    private val bounds = Rect()

    override fun onDraw(c: Canvas) {
        val w = width.toFloat(); val h = height - bottomReservePx
        c.drawColor(Color.BLACK)
        val d = screen; val s = d.s
        val pad = 0.015f * h; val gap = 0.011f * h
        val innerW = w - 2 * pad; val innerH = h - 2 * pad - 2 * gap
        val r1 = innerH * 0.45f; val r2 = innerH * 0.33f; val r3 = innerH - r1 - r2
        val big = min(0.195f * h, 0.11f * w); val mid = big * 0.6f; val small = big * 0.44f
        val cap = max(16f, 0.042f * h); val chip = max(16f, 0.036f * h)
        val rad = 0.012f * h; val cpV = 0.012f * h; val cpH = cpV * 1.6f
        val stripH = 0.105f * h

        // Top: the running lap with the pit strip under it, the gap to the best lap with its bar.
        val half = (innerW - gap) / 2
        var x = pad; val y1 = pad
        cell(c, x, y1, half, r1, rad)
        caption(c, "今の周", x + cpH, y1 + cpV, cap)
        val top1 = y1 + cpV + cap * 1.3f; val stripTop = y1 + r1 - cpV - stripH
        number(c, s.lapNow, x + cpH, (top1 + stripTop) / 2, big, half - 2 * cpH, num)
        if (s.notice.isNotEmpty()) {
            fill(c, x + cpH, stripTop, half - 2 * cpH, stripH, rad, pitBlue)
            label(c, s.notice, x + half / 2, stripTop + stripH / 2, mid * 0.55f, half - 4 * cpH, Color.WHITE, textBold, Paint.Align.CENTER)
        }
        x += half + gap
        cell(c, x, y1, half, r1, rad)
        caption(c, "ベスト比", x + cpH, y1 + cpV, cap)
        val deltaColor = when (s.deltaKind) { Kind.FASTER -> faster; Kind.SLOWER -> slower; else -> num }
        // a number: say it is seconds, smaller, so the number stays the thing to read
        number(c, s.delta, x + cpH, (top1 + stripTop) / 2, big, half - 2 * cpH, deltaColor, if (s.deltaKind != null) "s" else null)
        val barW = half - 2 * cpH; val barH = max(10f, 0.028f * h); val barY = stripTop + (stripH - barH) / 2
        c.drawRect(x + cpH, barY, x + cpH + barW, barY + barH, paint.apply { color = barBg })
        val frac = s.deltaFrac
        val centre = x + cpH + barW / 2
        if (frac != null && kotlin.math.abs(frac) >= 1e-3) {
            val len = max(2f, (barW / 2) * kotlin.math.abs(frac.toFloat()))
            paint.color = if (frac < 0) barFaster else barSlower
            if (frac < 0) c.drawRect(centre - len, barY, centre, barY + barH, paint) else c.drawRect(centre, barY, centre + len, barY + barH, paint)
        }
        val markW = max(2f, 0.003f * w)
        c.drawRect(centre - markW / 2, barY, centre + markW / 2, barY + barH, paint.apply { color = barMid })

        // Middle: last lap (and its note), best, lap number; or the warning band over them.
        val y2 = y1 + r1 + gap
        if (s.warns.isNotEmpty()) {
            // flashing just after a warning comes on: dark red half the time (twice a second), the white text stays
            val dim = s.warnFlash && SystemClock.uptimeMillis() % FLASH_PERIOD_MS >= FLASH_PERIOD_MS / 2
            fill(c, pad, y2, innerW, r2, rad, if (dim) bannerDim else banner)
            val items = s.warns.take(WARN_SCALE.size)
            var k = WARN_SCALE[items.size - 1]
            val between = 0.04f * w
            // side by side in equal slots (as the DASH's homogeneous row), all smaller if they would not fit
            fun widths(k: Float) = items.map {
                paint.typeface = textBold; paint.textSize = mid * 0.9f * k
                paint.measureText(it.label) + 0.025f * w * k + numberWidth(it.value, big * k, it.unit, UNIT_SCALE)
            }
            fun total(v: List<Float>) = v.max() * v.size + between * (v.size - 1)
            var ws = widths(k)
            if (total(ws) > innerW * 0.96f) { k *= innerW * 0.96f / total(ws); ws = widths(k) }
            val slot = ws.max()
            var sx = pad + (innerW - total(ws)) / 2
            for ((i, it) in items.withIndex()) {
                val x0 = sx + (slot - ws[i]) / 2
                val nameW = label(c, it.label, x0, y2 + r2 / 2, mid * 0.9f * k, w, Color.WHITE, textBold)
                number(c, it.value, x0 + nameW + 0.025f * w * k, y2 + r2 / 2, big * k, w, Color.WHITE, it.unit, UNIT_SCALE)
                sx += slot + between
            }
        } else {
            val avail = innerW - 2 * gap
            val cells = listOf(Triple("前周", s.last, .42f), Triple("ベスト", s.best, .34f), Triple("周", s.lapNo, .24f))
            x = pad
            for ((i, t) in cells.withIndex()) {
                val cw = avail * t.third
                cell(c, x, y2, cw, r2, rad)
                val capW = caption(c, t.first, x + cpH, y2 + cpV, cap)
                if (i == 0 && s.lastNote.isNotEmpty()) {
                    val noteColor = when (s.lastNoteKind) { Kind.PIT -> pitNote; Kind.SLOWER -> slower; Kind.FASTER -> faster; else -> num }
                    // on the caption's line, as the DASH does
                    label(c, s.lastNote, x + cpH + capW + cap, y2 + cpV + cap * 0.6f, cap * 1.25f,
                        cw - 2 * cpH - capW - cap, noteColor, numFace)
                }
                val top2 = y2 + cpV + cap * 1.3f
                number(c, t.second, x + cpH, (top2 + y2 + r2 - cpV) / 2, mid, cw - 2 * cpH, num)
                x += cw + gap
            }
        }

        // Bottom: the race time and the clock on the left, the lights on the right.
        val y3 = y2 + r2 + gap
        cell(c, pad, y3, innerW, r3, rad)
        val cy = y3 + r3 / 2
        x = pad + cpH
        x += label(c, "経過", x, cy, cap, w, capColor, textFace) + 0.012f * w
        x += if (s.elapsed == CircuitState.WAITING) label(c, s.elapsed, x, cy, small * 0.8f, w, waiting, textBold)
             else number(c, s.elapsed, x, cy, small, w, num)
        x += 0.03f * w
        x += label(c, "時刻", x, cy, cap, w, capColor, textFace) + 0.012f * w
        val leftEnd = x + number(c, s.clock, x, cy, small, w, num)
        // The lights, right to left: this phone's battery, the oil sensor, GNSS, the logger's recording
        val lights = listOf(
            (if (d.charging) "充電 " else "電池 ") + (d.batteryPct?.let { "$it%" } ?: "--") to
                (if (d.charging) Kind.OK else Kind.WARN),
            // the oil sensors (the oil pressure only once it has come); the water temperature still warns for a lost oil one
            s.sensor.first to (if (s.sensor.second) Kind.OK else Kind.WARN),
            (if (s.gnss) "GNSS" else "GNSS未測位") to (if (s.gnss) Kind.OK else Kind.WARN),
            // the log stopped, else the burnt-in video short of time or not recording, else all well
            when { !s.rec -> "記録停止" to Kind.SLOWER; s.videoKind == Kind.WARN -> s.video to Kind.WARN; else -> "記録中" to Kind.OK },
        )
        var right = pad + innerW - cpH
        paint.typeface = textBold; paint.textSize = chip
        val chipH = chip * 1.45f
        for ((text, kind) in lights) {
            val tw = paint.apply { typeface = textBold; textSize = chip }.measureText(text)
            val cw = tw + chip
            if (right - cw < leftEnd + chip) break // the lights give way, never the numbers
            val (fg, bg) = chipColors.getValue(kind)
            fill(c, right - cw, cy - chipH / 2, cw, chipH, rad, bg)
            label(c, text, right - cw / 2, cy, chip, tw + 1, fg, textBold, Paint.Align.CENTER)
            right -= cw + 0.006f * w
        }

        // Over everything while the logger's values are missing (the old numbers must not be read).
        d.cover?.let { (title, sub) ->
            c.drawRect(0f, 0f, w, h, paint.apply { color = coverBg })
            val lines = sub.split('\n').filter { it.isNotEmpty() }
            val total = mid * 0.6f * 1.4f + lines.size * cap * 1.35f
            var ty = h / 2 - total / 2 + mid * 0.6f * 0.7f
            label(c, title, w / 2, ty, mid * 0.6f, w - 4 * pad, coverText, textBold, Paint.Align.CENTER)
            ty += mid * 0.6f * 0.7f + cap * 0.9f
            for (line in lines) { label(c, line, w / 2, ty, cap, w - 4 * pad, coverText, textFace, Paint.Align.CENTER); ty += cap * 1.35f }
        }
    }

    private fun cell(c: Canvas, x: Float, y: Float, w: Float, h: Float, r: Float) = fill(c, x, y, w, h, r, cellBg)

    private fun fill(c: Canvas, x: Float, y: Float, w: Float, h: Float, r: Float, color: Int) {
        rect.set(x, y, x + w, y + h)
        c.drawRoundRect(rect, r, r, paint.apply { this.color = color })
    }

    /** A caption at the top left of a cell; returns its width. */
    private fun caption(c: Canvas, s: String, x: Float, top: Float, size: Float): Float {
        paint.typeface = textFace; paint.textSize = size; paint.color = capColor; paint.textAlign = Paint.Align.LEFT
        c.drawText(s, x, top - paint.fontMetrics.ascent, paint)
        return paint.measureText(s)
    }

    /** Text centred on [cy], shrunk to [maxW]; returns its width. */
    private fun label(c: Canvas, s: String, x: Float, cy: Float, size: Float, maxW: Float, color: Int, face: Typeface,
                      align: Paint.Align = Paint.Align.LEFT): Float {
        paint.typeface = face; paint.textSize = size; paint.color = color; paint.textAlign = align
        val m = paint.measureText(s)
        if (m > maxW && m > 0) paint.textSize = size * maxW / m
        val fm = paint.fontMetrics
        c.drawText(s, x, cy - (fm.ascent + fm.descent) / 2, paint)
        return paint.measureText(s).also { paint.textAlign = Paint.Align.LEFT }
    }

    /** The width [number] would draw [s] with its [unit] at [size]. */
    private fun numberWidth(s: String, size: Float, unit: String?, unitScale: Float = 0.55f): Float {
        paint.typeface = numFace
        paint.textSize = size * unitScale
        val unitW = unit?.let { paint.measureText(it) } ?: 0f
        paint.textSize = size
        return paint.measureText(s) + unitW
    }

    /** Digits centred on [cy] by their own height (no descenders), with an optional smaller [unit]; returns the width. */
    private fun number(c: Canvas, s: String, x: Float, cy: Float, size: Float, maxW: Float, color: Int, unit: String? = null,
                       unitScale: Float = 0.55f): Float {
        paint.typeface = numFace; paint.textAlign = Paint.Align.LEFT; paint.color = color
        paint.textSize = size
        var unitW = unit?.let { paint.textSize = size * unitScale; paint.measureText(it) } ?: 0f
        paint.textSize = size
        var numW = paint.measureText(s)
        var scale = 1f
        if (numW + unitW > maxW && numW + unitW > 0) { scale = maxW / (numW + unitW); numW *= scale; unitW *= scale }
        paint.textSize = size * scale
        paint.getTextBounds("0", 0, 1, bounds)
        val base = cy + bounds.height() / 2f
        c.drawText(s, x, base, paint)
        if (unit != null) { paint.textSize = size * unitScale * scale; c.drawText(unit, x + numW, base, paint) }
        return numW + unitW
    }

    companion object {
        /** The warnings in the band, by how many are on (ecocapture_dash.WARN_SCALE). */
        val WARN_SCALE = floatArrayOf(1.0f, 0.75f, 0.55f)
        const val UNIT_SCALE = 0.6f // kPa / ℃ after the value, as the DASH
        const val FLASH_PERIOD_MS = 500L // bright and dark red twice a second (under 3 a second: photosensitivity)
    }
}
