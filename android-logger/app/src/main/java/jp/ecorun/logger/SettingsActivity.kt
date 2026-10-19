package jp.ecorun.logger

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Bundle
import android.os.PowerManager
import android.text.InputType
import android.view.View
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast

/**
 * Everything the driver does not touch while driving: car and servers, race
 * rules, the three lines, lap reset and the pre-run checks. Opened from the
 * driver screen; can be used while recording (setting lines on the course walk
 * needs a live fix, so it only works then).
 */
class SettingsActivity : Activity() {
    private lateinit var settings: Settings
    private lateinit var column: LinearLayout
    private val dp by lazy { resources.displayMetrics.density }

    private val bg = Color.rgb(9, 12, 16)
    private val card = Color.rgb(22, 28, 36)
    private val muted = Color.rgb(139, 148, 158)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Race.init(this)
        settings = Settings(this)
        window.statusBarColor = Color.BLACK
        window.navigationBarColor = Color.BLACK
        column = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(px(20), px(12), px(20), px(32))
        }
        val scroll = ScrollView(this).apply { setBackgroundColor(bg); addView(column) }
        // Edge-to-edge (target SDK 35+): keep the content clear of the status, navigation and keyboard areas.
        scroll.setOnApplyWindowInsetsListener { v, insets ->
            val bars = insets.getInsets(android.view.WindowInsets.Type.systemBars() or
                android.view.WindowInsets.Type.displayCutout() or android.view.WindowInsets.Type.ime())
            v.setPadding(bars.left, bars.top, bars.right, bars.bottom); insets
        }
        setContentView(scroll)
        build()
    }

    override fun onResume() { super.onResume(); build() }

    private fun px(v: Int) = (v * dp).toInt()

    private fun build() {
        column.removeAllViews()
        val running = Status.running
        val header = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        header.addView(title("設定"), LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f))
        header.addView(button("戻る") { finish() })
        column.addView(header)

        // Checks first: they decide whether the run can be trusted.
        section("点検")
        val pm = getSystemService(PowerManager::class.java)
        val ignoring = pm.isIgnoringBatteryOptimizations(packageName)
        row(if (ignoring) "電池の最適化：外してあります" else "電池の最適化：有効（画面を消すと止められることがあります）",
            if (ignoring) null else "外す" to {
                startActivity(Intent(android.provider.Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                    Uri.parse("package:$packageName")))
            })
        note("記録ファイル：端末の Download/EcoLogger/ に走行ごとに1つ")

        section("車とサーバー")
        val car = field("車の名前（記録ファイル名・サーバーでの表示名）", settings.carName, "例：car2", !running)
        val primary = field("主サーバーのURL", settings.primaryUrl, "wss://…/ws/audio/<room>", !running)
        val backup = field("予備サーバーのURL", settings.backupUrl, "空欄なら予備なし", !running)
        if (running) note("記録中は変えられません（止めてから変えてください）")

        section("大会")
        val cfg = Race.config()
        val laps = field("規定周回数", cfg.totalLaps?.toString() ?: "", "例：7", true, InputType.TYPE_CLASS_NUMBER)
        val limit = field("規定時間（分:秒）", cfg.timeLimitS?.let { DashboardView.clock(it, false) + ".%02d".format(Math.round((it % 1) * 100).toInt().coerceAtMost(99)) } ?: "",
            "例：39:20.11", true, InputType.TYPE_CLASS_TEXT)
        val minLap = field("最短ラップ（秒、これより短い周は数えない）", "%.0f".format(cfg.minLapS), "10", true, InputType.TYPE_CLASS_NUMBER)
        column.addView(button("車・サーバー・大会の設定を保存") {
            if (!running) {
                settings.carName = car.text.toString(); settings.primaryUrl = primary.text.toString(); settings.backupUrl = backup.text.toString()
            }
            val total = laps.text.toString().trim().toIntOrNull()
            val lim = parseClock(limit.text.toString())
            val min = minLap.text.toString().trim().toDoubleOrNull()
            if (limit.text.isNotBlank() && lim == null) { toast("規定時間は 39:20.11 の形で入れてください"); return@button }
            Race.configure(Race.config().copy(totalLaps = total, timeLimitS = lim, minLapS = (min ?: 10.0).coerceIn(5.0, 7200.0)))
            toast("保存しました"); build()
        }, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = px(8) })

        section("ライン")
        note("コースウォークで記録を始めてからライン上に立ち「現在地にする」。地図で調べた「緯度, 経度」を入れてもよい。向きは最初の通過で自動に決まる")
        for ((target, name) in listOf("control" to "コントロールライン（毎周通る）", "start" to "スタートライン（任意）", "goal" to "ゴールライン（任意）")) {
            line(target, name)
        }

        section("ラップ")
        val v = Race.values()
        val list = Race.laps()
        note(if (list.isEmpty()) "まだ周回はありません" else list.mapIndexed { i, s -> "${i + 1}周目 ${DashboardView.clock(s, true)}" }.joinToString("　"))
        if (v?.finished == true) note("ゴール済み")
        column.addView(button("ラップをリセット（本番の前に必ず）") {
            AlertDialog.Builder(this).setMessage("周回の記録を消して、スタート前に戻します。よいですか？")
                .setPositiveButton("リセット") { _, _ -> Race.reset(); build() }
                .setNegativeButton("やめる", null).show()
        }, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = px(8) })
    }

    private fun line(target: String, name: String) {
        val g = Race.config().gate(target)
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(px(14), px(10), px(14), px(10))
            background = GradientDrawable().apply { setColor(card); cornerRadius = 12 * dp }
        }
        box.addView(text(name, 17f, Color.WHITE, true))
        box.addView(text(g?.let { "%.6f, %.6f　幅 %.0fm　向き %s".format(it.lat, it.lon, it.widthM, it.bearing?.let { b -> "%.0f°".format(b) } ?: "未定（最初の通過で決まる）") }
            ?: "未設定", 15f, muted, false))
        val coords = EditText(this).apply {
            hint = "緯度, 経度（Googleマップの右クリックで出る形）"; setHintTextColor(muted); setTextColor(Color.WHITE)
            isSingleLine = true; inputType = InputType.TYPE_CLASS_TEXT
        }
        box.addView(coords, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
        val buttons = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        buttons.addView(button("現在地にする") {
            if (!Status.running) toast("記録を始めてから押してください")
            else if (Race.setHere(target)) { toast("現在地をラインにしました"); build() }
            else toast("測位できていません")
        })
        buttons.addView(button("入れた座標にする") {
            val p = coords.text.split(",").map { it.trim().toDoubleOrNull() }
            if (p.size != 2 || p[0] == null || p[1] == null || p[0]!! !in -90.0..90.0 || p[1]!! !in -180.0..180.0) {
                toast("「36.531234, 140.226543」の形で入れてください")
            } else {
                Race.configure(Race.config().withGate(target, Gate(p[0]!!, p[1]!!, null, g?.widthM ?: 30.0))); build()
            }
        })
        if (g != null) buttons.addView(button("消す") { Race.configure(Race.config().withGate(target, null)); build() })
        box.addView(buttons)
        column.addView(box, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = px(8) })
    }

    private fun parseClock(s: String): Double? {
        val t = s.trim()
        if (t.isEmpty()) return null
        val parts = t.split(":")
        return when (parts.size) {
            1 -> parts[0].toDoubleOrNull()?.times(60)
            2 -> { val m = parts[0].toIntOrNull(); val sec = parts[1].toDoubleOrNull(); if (m == null || sec == null) null else m * 60 + sec }
            else -> null
        }
    }

    private fun title(s: String) = text(s, 26f, Color.WHITE, true)

    private fun section(s: String) {
        column.addView(text(s, 20f, Color.WHITE, true).apply { setPadding(0, px(20), 0, px(4)) })
    }

    private fun note(s: String) = column.addView(text(s, 15f, muted, false).apply { setPadding(0, px(4), 0, px(4)) })

    private fun row(s: String, action: Pair<String, () -> Unit>?) {
        val r = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        r.addView(text(s, 16f, Color.WHITE, false), LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f))
        action?.let { (label, run) -> r.addView(button(label) { run() }) }
        column.addView(r)
    }

    private fun field(label: String, value: String, hint: String, enabled: Boolean, type: Int = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI): EditText {
        column.addView(text(label, 14f, muted, false).apply { setPadding(0, px(8), 0, 0) })
        return EditText(this).apply {
            setText(value); this.hint = hint; isSingleLine = true; inputType = type; isEnabled = enabled
            setTextColor(if (enabled) Color.WHITE else muted); setHintTextColor(Color.rgb(80, 88, 98))
            column.addView(this, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
        }
    }

    private fun text(s: String, size: Float, color: Int, bold: Boolean) = TextView(this).apply {
        text = s; textSize = size; setTextColor(color); if (bold) typeface = Typeface.DEFAULT_BOLD
    }

    private fun button(label: String, onClick: (View) -> Unit) = Button(this).apply {
        text = label; isAllCaps = false; setTextColor(Color.WHITE); textSize = 15f
        background = GradientDrawable().apply { setColor(Color.rgb(48, 54, 61)); cornerRadius = 10 * dp }
        setPadding(px(14), 0, px(14), 0)
        setOnClickListener(onClick)
    }

    private fun toast(s: String) = Toast.makeText(this, s, Toast.LENGTH_SHORT).show()
}
