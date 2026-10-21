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
        Imu.init(this)
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

        section("画面")
        toggle("この画面を開いている間は画面を消さない（記録していなくても）", settings.keepScreenOn) { settings.keepScreenOn = it }
        toggle("記録中は画面を最大の明るさにする（日なたで読めるように。電池は減りやすい）", settings.fullBrightness) { settings.fullBrightness = it }
        note("記録中は設定に関係なく画面を消さない。ほかのアプリ（Discordなど）を前に出していると、そのアプリの設定で暗くなるので、走行中はこのアプリを前に出しておく")

        section("取付けの向き（前後・左右・上下のG）")
        note(Imu.describe())
        note(if (RaceClass.ensure(this).twoWheel)
            "二輪：ホルダーに付けたら、車体をまっすぐ立てて（センタースタンドか支えて）揺らさずに「1G校正」。" +
            "しなくても、まっすぐ一定の速さで走っている間に自動で取る（サイドスタンドで傾いた停車中は使わない）。" +
            "前方は画面がライダーを向いている前提で始まり、走ると加速・減速からGNSSで校正される"
        else "四輪：ホルダーに付けたら、車を平らな所に止めて揺らさずに「1G校正」。しなくても、記録中に停車すると自動で取る。" +
            "前方は画面がドライバーを向いている前提で始まり、走ると加速・減速からGNSSで校正される")
        val imuButtons = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        imuButtons.addView(button("今の向きで1G校正") {
            when {
                !Status.running -> toast("記録を始めてから押してください")
                Imu.calibrateNow() -> { toast("校正しました"); build() }
                else -> toast("揺れています。車を止めて、2秒ほど触らずに押してください")
            }
        })
        imuButtons.addView(button("校正をやり直す（自動に戻す）") {
            AlertDialog.Builder(this).setMessage("1G・前方の校正を消して、自動で取り直します。よいですか？")
                .setPositiveButton("やり直す") { _, _ -> Imu.clear(); build() }
                .setNegativeButton("やめる", null).show()
        })
        column.addView(imuButtons)

        section("車とサーバー")
        val car = field("車の名前（記録ファイル名・サーバーでの表示名）", settings.carName, "例：car2", !running)
        val primary = field("主サーバーのURL", settings.primaryUrl, "wss://…/ws/audio/<room>", !running)
        val backup = field("予備サーバーのURL", settings.backupUrl, "空欄なら予備なし", !running)
        if (running) note("記録中は変えられません（止めてから変えてください）")

        section("大会")
        val klass = RaceClass.ensure(this)
        note("クラス（2026年 全国大会の競技規則の名前）を選ぶと規定周回数・規定時間が入り、1G校正の取り方（二輪は走行中、四輪は停車中）も切り替わる")
        for ((i, c) in RaceClass.entries.withIndex()) {
            if (i == 3) note("ほかの公式クラス")
            column.addView(button((if (c == klass) "✓ " else "　") + c.label) { c.apply(this); toast("${c.code} にしました"); build() }.apply {
                (background as GradientDrawable).setColor(if (c == klass) Color.rgb(35, 134, 54) else Color.rgb(48, 54, 61))
                gravity = android.view.Gravity.START or android.view.Gravity.CENTER_VERTICAL
                textSize = 16f
            }, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = px(6) })
        }
        val cfg = Race.config()
        val custom = klass == RaceClass.OTHER
        val laps = field("規定周回数", cfg.totalLaps?.toString() ?: "", "例：3", custom, InputType.TYPE_CLASS_NUMBER)
        val limit = field("規定時間（分:秒）", cfg.timeLimitS?.let { DashboardView.clock(it, false) + ".%02d".format(Math.round((it % 1) * 100).toInt().coerceAtMost(99)) } ?: "",
            "例：16:27.36", custom, InputType.TYPE_CLASS_TEXT)
        val distance = field("規定距離（m、目標の平均速度に使う）", cfg.raceDistanceM?.let { "%.2f".format(it) } ?: "",
            "例：6856.72", custom, InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_FLAG_DECIMAL)
        if (!custom) note("規定周回数・規定時間・規定距離を変えるときは「その他（手入力）」を選ぶ")
        val margin = field("余裕（秒）：規定時間よりこれだけ早くゴールする目標で平均速度を出す（${klass.code}用）", "%.0f".format(settings.marginS(klass)),
            "例：30", true, InputType.TYPE_CLASS_NUMBER)
        val minLap = field("最短ラップ（秒、これより短い周は数えない）", "%.0f".format(cfg.minLapS), "10", true, InputType.TYPE_CLASS_NUMBER)
        column.addView(button("車・サーバー・大会の設定を保存") {
            if (!running) {
                settings.carName = car.text.toString(); settings.primaryUrl = primary.text.toString(); settings.backupUrl = backup.text.toString()
            }
            val total = laps.text.toString().trim().toIntOrNull()
            val lim = parseClock(limit.text.toString())
            val min = minLap.text.toString().trim().toDoubleOrNull()
            if (custom && limit.text.isNotBlank() && lim == null) { toast("規定時間は 16:27.36 の形で入れてください"); return@button }
            val marginS = (margin.text.toString().trim().toDoubleOrNull() ?: Settings.DEFAULT_MARGIN_S).coerceIn(0.0, 600.0)
            settings.setMarginS(klass, marginS)
            val c = Race.config().copy(minLapS = (min ?: 10.0).coerceIn(5.0, 7200.0), marginS = marginS)
            Race.configure(if (custom) c.copy(totalLaps = total, timeLimitS = lim,
                raceDistanceM = distance.text.toString().trim().toDoubleOrNull()?.takeIf { it > 0 }) else c)
            toast("保存しました"); build()
        }, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = px(8) })

        section("ライン")
        val ref = Race.reference
        val locked = Race.locked
        note(when {
            ref != null -> "基準：${ref.id}（${ref.source} ${ref.at}）から読み込んだライン" + if (locked) "。ロック中" else "。ロックを外しています"
            locked -> "この端末で決めたライン。ロック中"
            else -> "この端末で決めたライン（Ver.2の基準ではありません）"
        })
        spacing()?.let { note(it) }
        note("基準はVer.2で取る（アクティブアンテナのGNSSの方が10倍ほど正確なため）。Ver.2のWeb画面の「ラインをスマホへ」に出るQRを、下のボタンで読み込む。読み込むとロックがかかる")
        val refButtons = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        refButtons.addView(button("Ver.2の基準をQRで読み込む") { scanReference() })
        refButtons.addView(button("文字で貼り付け") { pasteReference() })
        refButtons.addView(if (locked) button("ロックを外す（長押し）") { toast("長押しで外します") }.apply {
            setOnLongClickListener {
                AlertDialog.Builder(this@SettingsActivity).setMessage("ラインのロックを外します。外すとラインを変えられるようになります。よいですか？")
                    .setPositiveButton("外す") { _, _ -> Race.setLocked(false); build() }
                    .setNegativeButton("やめる", null).show(); true
            }
        } else button("ロックする") { Race.setLocked(true); toast("ロックしました"); build() })
        column.addView(refButtons)
        if (!locked) {
            column.addView(button("もてぎ（全国大会）のおおよその位置に戻す") {
                confirm("3本のラインを、地図から拾ったもてぎの位置（おおよそ）に戻します。よいですか？") { Race.useMotegiLines(); build() }
            }, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = px(6) })
        }
        for ((target, name) in listOf("control" to "コントロールライン（毎周通る）", "start" to "スタートライン", "goal" to "ゴールライン")) {
            line(target, name, locked)
        }

        section("ラップ")
        val v = Race.values()
        val list = Race.laps()
        note(if (list.isEmpty()) "まだ周回はありません" else list.mapIndexed { i, s -> "${i + 1}周目 ${DashboardView.clock(s, true)}" }.joinToString("　"))
        if (v?.finished == true) note("ゴール済み")
        column.addView(button("ラップをリセット（本番の前に必ず）") {
            AlertDialog.Builder(this).setMessage("周回の記録を消して、スタート前に戻します。ラインもロックします。よいですか？")
                .setPositiveButton("リセット") { _, _ -> Race.reset(); build() }
                .setNegativeButton("やめる", null).show()
        }, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = px(8) })
    }

    private fun line(target: String, name: String, locked: Boolean) {
        val g = Race.config().gate(target)
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(px(14), px(10), px(14), px(10))
            background = GradientDrawable().apply { setColor(card); cornerRadius = 12 * dp }
        }
        box.addView(text(name + if (locked) "　🔒" else "", 17f, Color.WHITE, true))
        box.addView(text(g?.let { "%.7f, %.7f　幅 %.0fm　向き %s".format(it.lat, it.lon, it.widthM, it.bearing?.let { b -> "%.0f°".format(b) } ?: "未定（最初の通過で決まる）") }
            ?: "未設定", 15f, muted, false))
        column.addView(box, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = px(8) })
        if (locked) return
        val coords = EditText(this).apply {
            hint = "緯度, 経度（Googleマップの右クリックで出る形）"; setHintTextColor(muted); setTextColor(Color.WHITE)
            isSingleLine = true; inputType = InputType.TYPE_CLASS_TEXT
        }
        box.addView(coords, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
        val buttons = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        buttons.addView(button("現在地にする") {
            if (!Status.running) { toast("記録を始めてから押してください"); return@button }
            confirm("${name}を今いる位置に変えます。よいですか？") {
                if (Race.setHere(target)) { toast("現在地をラインにしました"); build() } else toast("測位できていません")
            }
        })
        buttons.addView(button("入れた座標にする") {
            val p = coords.text.split(",").map { it.trim().toDoubleOrNull() }
            if (p.size != 2 || p[0] == null || p[1] == null || p[0]!! !in -90.0..90.0 || p[1]!! !in -180.0..180.0) {
                toast("「36.531234, 140.226543」の形で入れてください")
            } else confirm("${name}を入れた座標に変えます。よいですか？") {
                Race.setGate(target, Gate(p[0]!!, p[1]!!, null, g?.widthM ?: 30.0)); build()
            }
        })
        if (g != null) buttons.addView(button("消す") { confirm("${name}を消します。よいですか？") { Race.setGate(target, null); build() } })
        box.addView(buttons)
    }

    /** Distances between the lines, so a line taken at the wrong place stands out. */
    private fun spacing(): String? {
        val c = Race.config()
        fun d(a: Gate?, b: Gate?): String? {
            if (a == null || b == null) return null
            val x = (b.lon - a.lon) * 111320.0 * Math.cos(Math.toRadians(a.lat)); val y = (b.lat - a.lat) * 111320.0
            return "%.0fm".format(Math.hypot(x, y))
        }
        val parts = listOfNotNull(d(c.goal, c.control)?.let { "ゴール→コントロール $it" }, d(c.control, c.start)?.let { "コントロール→スタート $it" })
        return if (parts.isEmpty()) null else "ライン間の距離：" + parts.joinToString("、") + "（もてぎの目安：約90m、約280m）"
    }

    private fun confirm(message: String, ok: () -> Unit) {
        AlertDialog.Builder(this).setMessage(message).setPositiveButton("はい") { _, _ -> ok() }.setNegativeButton("やめる", null).show()
    }

    private fun importText(text: String) {
        try {
            val r = Race.importReference(text)
            AlertDialog.Builder(this).setMessage("基準 ${r.id}（${r.source} ${r.at}）のラインを読み込み、ロックしました。\n" + (spacing() ?: ""))
                .setPositiveButton("OK", null).show()
        } catch (e: LineCode.Invalid) {
            AlertDialog.Builder(this).setMessage(e.message).setPositiveButton("OK", null).show()
        }
        build()
    }

    private fun scanReference() {
        val doImport = {
            com.google.mlkit.vision.codescanner.GmsBarcodeScanning.getClient(this,
                com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions.Builder()
                    .setBarcodeFormats(com.google.mlkit.vision.barcode.common.Barcode.FORMAT_QR_CODE).build())
                .startScan()
                .addOnSuccessListener { code -> code.rawValue?.let { importText(it) } ?: toast("読み取れませんでした") }
                .addOnFailureListener { toast("QRの読み取りを使えません（${it.message}）。「文字で貼り付け」を使ってください") }
        }
        if (Race.locked) confirm("今のロックされたラインを、読み込んだ基準で置き換えます。よいですか？") { doImport() } else doImport()
    }

    private fun pasteReference() {
        val input = EditText(this).apply { hint = "ECOLINES1|c=…"; setTextColor(Color.WHITE) }
        val clip = getSystemService(android.content.ClipboardManager::class.java).primaryClip
        clip?.getItemAt(0)?.text?.toString()?.takeIf { it.startsWith(LineCode.PREFIX) }?.let { input.setText(it) }
        AlertDialog.Builder(this).setMessage("Ver.2の画面の「文字で写す」の内容を貼り付けてください").setView(input)
            .setPositiveButton("読み込む") { _, _ -> importText(input.text.toString()) }
            .setNegativeButton("やめる", null).show()
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

    private fun toggle(label: String, value: Boolean, onChange: (Boolean) -> Unit) {
        column.addView(android.widget.Switch(this).apply {
            text = label; textSize = 16f; setTextColor(Color.WHITE); isChecked = value
            setPadding(0, px(6), 0, px(6))
            setOnCheckedChangeListener { _, on -> onChange(on) }
        }, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
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
