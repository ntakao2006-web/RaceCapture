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
        // WindowInsets.Type is API 30+. Android 10 does not force edge-to-edge, so the system already keeps
        // the content clear of the bars there and no listener is needed.
        if (android.os.Build.VERSION.SDK_INT >= 30) {
            scroll.setOnApplyWindowInsetsListener { v, insets ->
                val bars = insets.getInsets(android.view.WindowInsets.Type.systemBars() or
                    android.view.WindowInsets.Type.displayCutout() or android.view.WindowInsets.Type.ime())
                v.setPadding(bars.left, bars.top, bars.right, bars.bottom); insets
            }
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

        section("使い方")
        for ((circuit, label) in listOf(false to "エコラン（平均速度・規定時間。このスマホで周回を数えてサーバーへ送る）",
                                        true to "サーキット（SUGO：Ver.2の車載画面DASHの予備。Ver.2の値を出すだけ）")) {
            column.addView(button((if (settings.circuit == circuit) "✓ " else "　") + label) {
                when {
                    settings.circuit == circuit -> {}
                    running -> toast("記録を止めてから切り替えてください")
                    else -> { settings.circuit = circuit; toast(if (circuit) "サーキットにしました" else "エコランにしました"); build() }
                }
            }.apply {
                (background as GradientDrawable).setColor(if (settings.circuit == circuit) Color.rgb(35, 134, 54) else Color.rgb(48, 54, 61))
                gravity = android.view.Gravity.START or android.view.Gravity.CENTER_VERTICAL
                textSize = 16f
            }, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = px(6) })
        }
        checks()
        transfer(running)
        if (settings.circuit) { buildCircuit(running); return }

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

        loggerSection(running, false)
        if (settings.loggerConfigured) {
            note("走行前（周回の計測が始まる前）は、ロガーにつながるとロガーのラインを自動で読み込み、このアプリの規定周回数をロガーへ書き込む。規定時間・余裕は大会の設定をロックしている間だけ書き込む（ピットのGrafanaはロガーの値を表示する）。" +
                "「ラップをリセット」はロガーの周回もリセットする。計測が始まったら、どちらも変えない")
            if (LoggerFeed.fresh()) note("ロガーの周回：" + (LoggerFeed.lapCount?.let { "${it}周" } ?: "—") +
                (LoggerFeed.lapsLeft?.let { "　残り${it}周" } ?: "") + (LoggerFeed.totalLaps?.let { "　規定${it}周" } ?: "　規定周回数なし") +
                (if (LoggerFeed.lapFinished) "　ゴール済み" else "") + "　基準${LoggerFeed.lineId ?: "なし"}" +
                (LoggerFeed.timeLimitS?.let { "　規定時間" + DashboardView.clock(it, false) } ?: "　規定時間なし") +
                (LoggerFeed.marginS?.let { "　余裕%.0f秒".format(it) } ?: ""))
            if (LoggerFeed.syncNote.isNotEmpty()) note("最後の同期：" + LoggerFeed.syncNote)
        }

        section("大会")
        val klass = RaceClass.ensure(this)
        val classLocked = Race.classLocked
        note("クラス（2026年 全国大会の競技規則の名前）を選ぶと規定周回数・規定時間・規定距離が入り、1G校正の取り方（二輪は走行中、四輪は停車中）も切り替わる")
        note(if (classLocked) "🔒 クラス・周回数・時間・距離・余裕はロック中（変えるときは下の「ロックを外す」を長押し）"
            else "クラス・周回数・時間・距離・余裕はロックしていません。決めたら下の「ロックする」で固定する（ラップのリセットでも自動でロック）")
        for ((i, c) in RaceClass.entries.withIndex()) {
            if (classLocked && c != klass) continue
            if (i == 3 && !classLocked) note("ほかの公式クラス")
            column.addView(button((if (c == klass) "✓ " else "　") + c.label) {
                if (Race.classLocked) toast("ロック中です") else { c.apply(this); toast("${c.code} にしました"); build() }
            }.apply {
                (background as GradientDrawable).setColor(if (c == klass) Color.rgb(35, 134, 54) else Color.rgb(48, 54, 61))
                gravity = android.view.Gravity.START or android.view.Gravity.CENTER_VERTICAL
                textSize = 16f
            }, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = px(6) })
        }
        val cfg = Race.config()
        val custom = klass == RaceClass.OTHER && !classLocked
        val laps = field("規定周回数", cfg.totalLaps?.toString() ?: "", "例：3", custom, InputType.TYPE_CLASS_NUMBER)
        val limit = field("規定時間（分:秒）", cfg.timeLimitS?.let { DashboardView.clock(it, false) + ".%02d".format(Math.round((it % 1) * 100).toInt().coerceAtMost(99)) } ?: "",
            "例：16:27.36", custom, InputType.TYPE_CLASS_TEXT)
        val distance = field("規定距離（m、目標の平均速度に使う）", cfg.raceDistanceM?.let { "%.2f".format(it) } ?: "",
            "例：6856.72", custom, InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_FLAG_DECIMAL)
        if (!custom && !classLocked) note("規定周回数・規定時間・規定距離を変えるときは「その他（手入力）」を選ぶ")
        val margin = field("余裕（秒）：規定時間よりこれだけ早くゴールする目標で平均速度を出す（${klass.code}用）", "%.0f".format(settings.marginS(klass)),
            "例：30", !classLocked, InputType.TYPE_CLASS_NUMBER)
        val minLap = field("最短ラップ（秒、これより短い周は数えない）", "%.0f".format(cfg.minLapS), "10", true, InputType.TYPE_CLASS_NUMBER)
        column.addView(button("車・サーバー・大会の設定を保存") {
            if (!running) {
                settings.carName = car.text.toString(); settings.primaryUrl = primary.text.toString(); settings.backupUrl = backup.text.toString()
            }
            val total = laps.text.toString().trim().toIntOrNull()
            val lim = parseClock(limit.text.toString())
            val min = minLap.text.toString().trim().toDoubleOrNull()
            if (custom && limit.text.isNotBlank() && lim == null) { toast("規定時間は 16:27.36 の形で入れてください"); return@button }
            var c = Race.config().copy(minLapS = (min ?: 10.0).coerceIn(5.0, 7200.0))
            if (!Race.classLocked) {
                val marginS = (margin.text.toString().trim().toDoubleOrNull() ?: Settings.DEFAULT_MARGIN_S).coerceIn(0.0, 600.0)
                settings.setMarginS(klass, marginS)
                c = c.copy(marginS = marginS)
            }
            Race.configure(if (custom && !Race.classLocked) c.copy(totalLaps = total, timeLimitS = lim,
                raceDistanceM = distance.text.toString().trim().toDoubleOrNull()?.takeIf { it > 0 }) else c)
            toast("保存しました"); build()
        }, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = px(8) })
        column.addView(if (classLocked) button("大会の設定のロックを外す（長押し）") { toast("長押しで外します") }.apply {
            setOnLongClickListener {
                AlertDialog.Builder(this@SettingsActivity).setMessage("クラス・周回数・時間・距離・余裕のロックを外します。外すと変えられるようになります。よいですか？")
                    .setPositiveButton("外す") { _, _ -> Race.setClassLocked(false); build() }
                    .setNegativeButton("やめる", null).show(); true
            }
        } else button("大会の設定をロックする") {
            Race.setClassLocked(true); toast("ロックしました（未保存の入力は捨てました）"); build()
        }, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = px(6) })

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
            AlertDialog.Builder(this).setMessage("周回の記録を消して、スタート前に戻します。ラインと大会の設定（クラス・余裕など）もロックします。よいですか？")
                .setPositiveButton("リセット") { _, _ -> Race.reset(); build(); resetLogger() }
                .setNegativeButton("やめる", null).show()
        }, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = px(8) })
    }

    /** Checks first (they decide whether the run can be trusted), then the screen: both profiles. */
    private fun checks() {
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
    }

    /**
     * The same settings into another phone without typing them again ([ConfigCode]): out through
     * the share sheet or the clipboard, in by paste or QR. Both profiles. The app cannot draw a
     * QR code (it only reads them), so the text is what moves.
     */
    private fun transfer(running: Boolean) {
        section("設定を別のスマホへ写す")
        note("このスマホの設定（使い方・車の名前・サーバー・ロガーへのつなぎ方・クラスと余裕・警告・画面）を1つの文字列にして、" +
            "予備のスマホやほかの人のスマホへ、打ち直さずに入れる。ライン・ロック・周回・1G校正は入らない（ラインはエコランの設定の「ライン」で写す）。" +
            "書き出すのは保存してある値なので、入力の途中なら先にそれぞれの「保存」を押す")
        val buttons = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        buttons.addView(button("設定を書き出す") { exportConfig() })
        buttons.addView(button("設定を読み込む（貼り付け）") { if (Status.running) toast("記録を止めてから読み込んでください") else pasteConfig() })
        buttons.addView(button("QRで読み込む") { if (Status.running) toast("記録を止めてから読み込んでください") else scanQr { previewConfig(it) } })
        column.addView(buttons)
        if (running) note("読み込みは記録中はできません（止めてから）。書き出しはできます")
    }

    /** What [ConfigCode] carries, as this phone has it saved. */
    private fun currentConfig(): Map<String, String> {
        val c = Race.config()
        fun flag(b: Boolean) = if (b) "1" else "0"
        return buildMap {
            put("pf", if (settings.circuit) "circuit" else "ecorun")
            put("car", settings.carName); put("p", settings.primaryUrl); put("b", settings.backupUrl)
            put("ll", flag(settings.loggerLan)); put("ls", settings.loggerSsid); put("lp", settings.loggerPass)
            put("lk", settings.loggerKey); put("lh", settings.loggerHost)
            put(ConfigCode.CLASS, RaceClass.ensure(this@SettingsActivity).name)
            for (k in RaceClass.entries) put(ConfigCode.marginKey(k), ConfigCode.num(settings.marginS(k)))
            put("tl", c.totalLaps?.toString() ?: ""); put("tm", c.timeLimitS?.let { ConfigCode.num(it) } ?: "")
            put("ds", c.raceDistanceM?.let { ConfigCode.num(it) } ?: ""); put("ml", ConfigCode.num(c.minLapS))
            put("ow", ConfigCode.num(settings.oilWarn)); put("ww", ConfigCode.num(settings.waterWarn))
            put("av", Math.round(settings.alarmVolume * 100).toString())
            put("ks", flag(settings.keepScreenOn)); put("fb", flag(settings.fullBrightness))
        }
    }

    /** Writes what was read; only the keys in [m] change. The values have passed [ConfigCode.parse]. */
    private fun applyConfig(m: Map<String, String>) {
        m["pf"]?.let { settings.circuit = it == "circuit" }
        m["car"]?.let { settings.carName = it }; m["p"]?.let { settings.primaryUrl = it }; m["b"]?.let { settings.backupUrl = it }
        m["ll"]?.let { settings.loggerLan = it == "1" }; m["ls"]?.let { settings.loggerSsid = it }; m["lp"]?.let { settings.loggerPass = it }
        m["lk"]?.let { settings.loggerKey = it }; m["lh"]?.let { settings.loggerHost = it }
        m["ow"]?.toDoubleOrNull()?.let { settings.oilWarn = it }; m["ww"]?.toDoubleOrNull()?.let { settings.waterWarn = it }
        m["av"]?.toDoubleOrNull()?.let { settings.alarmVolume = it / 100 }
        m["ks"]?.let { settings.keepScreenOn = it == "1" }; m["fb"]?.let { settings.fullBrightness = it == "1" }
        // The margins before the class: choosing a class takes its margin into the lap timer.
        for (k in RaceClass.entries) m[ConfigCode.marginKey(k)]?.toDoubleOrNull()?.let { settings.setMarginS(k, it) }
        m[ConfigCode.CLASS]?.let { n -> RaceClass.entries.firstOrNull { it.name == n }?.apply(this) }
        val klass = RaceClass.ensure(this) // a changed margin of the class already chosen
        var c = Race.config()
        m["ml"]?.toDoubleOrNull()?.let { c = c.copy(minLapS = it) }
        if (klass == RaceClass.OTHER) {
            m["tl"]?.let { c = c.copy(totalLaps = it.toIntOrNull()) }
            m["tm"]?.let { c = c.copy(timeLimitS = it.toDoubleOrNull()) }
            m["ds"]?.let { c = c.copy(raceDistanceM = it.toDoubleOrNull()) }
        }
        if (c != Race.config()) Race.configure(c)
    }

    private fun exportConfig() {
        val values = currentConfig()
        if (!ConfigCode.secretsIn(values)) { showExport(values, false); return }
        AlertDialog.Builder(this).setMessage("ロガーの合言葉・ロガーのWi-Fiのパスワードも入れますか？\n\n" +
                "入れないときは、読み込んだスマホでその2つだけ手で入れます（ふつうはこちら）。")
            .setPositiveButton("入れない") { _, _ -> showExport(values, false) }
            .setNegativeButton("秘密も入れる") { _, _ -> showExport(values, true) }
            .setNeutralButton("やめる", null).show()
    }

    private fun showExport(values: Map<String, String>, secrets: Boolean) {
        val code = try { ConfigCode.encode(values, secrets) } catch (e: ConfigCode.Invalid) {
            alert("書き出せません：${e.message}\nその設定を直して保存してから、もう一度押してください"); return
        }
        AlertDialog.Builder(this).setMessage(
                (if (secrets) "⚠ この文字列（と、そこから作ったQR）には秘密が入っています。写真に撮って送ったり、画面を共有したりしないでください。送る相手も確かめてください。\n\n"
                else "合言葉・Wi-Fiのパスワードは入っていません。\n\n") +
                "設定を${code.length}文字の文字列にしました。「共有する」でメッセージのアプリなどから別のスマホへ送るか、「コピー」して貼り付けます。\n" +
                "受け取ったスマホでは、文字列をコピーしてから、このアプリの設定の「設定を読み込む（貼り付け）」を押します。")
            .setPositiveButton("共有する") { _, _ ->
                startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, code), "設定を送る"))
            }
            .setNegativeButton("コピー") { _, _ ->
                val clip = android.content.ClipData.newPlainText("EcoLoggerの設定", code)
                // Android 13+: keeps the text out of the clipboard preview.
                if (secrets && android.os.Build.VERSION.SDK_INT >= 33) clip.description.extras =
                    android.os.PersistableBundle().apply { putBoolean(android.content.ClipDescription.EXTRA_IS_SENSITIVE, true) }
                getSystemService(android.content.ClipboardManager::class.java).setPrimaryClip(clip)
                toast("コピーしました")
            }
            .setNeutralButton("閉じる", null).show()
    }

    private fun pasteConfig() {
        val input = EditText(this).apply { hint = "${ConfigCode.PREFIX}${ConfigCode.VERSION}|…"; setTextColor(Color.WHITE) }
        val clip = getSystemService(android.content.ClipboardManager::class.java).primaryClip
        clip?.getItemAt(0)?.text?.toString()?.trim()?.takeIf { it.startsWith(ConfigCode.PREFIX) }?.let { input.setText(it) }
        AlertDialog.Builder(this).setMessage("別のスマホで「設定を書き出す」で出した文字列を貼り付けてください（コピーしてあれば、もう入っています）。次の画面で、変わる所を確かめてから読み込みます")
            .setView(input)
            .setPositiveButton("次へ") { _, _ -> previewConfig(input.text.toString()) }
            .setNegativeButton("やめる", null).show()
    }

    /** Shows what would change and asks; nothing is written before "読み込む". */
    private fun previewConfig(text: String) {
        if (Status.running) { toast("記録を止めてから読み込んでください"); return }
        val parsed = try { ConfigCode.parse(text) } catch (e: ConfigCode.Invalid) { alert("読み込めません：${e.message}"); return }
        val current = currentConfig()
        val incoming = if (Race.classLocked) ConfigCode.withoutRace(parsed.values).first else parsed.values
        val changes = ConfigCode.changes(current, incoming)
        val held = ConfigCode.changes(current, parsed.values).size - changes.size
        val notes = listOfNotNull(
            "大会の設定がロック中なので、クラス・余裕など${held}項目は変えません（変えるなら、ロックを外してから読み込み直す）".takeIf { held > 0 },
            "このアプリの知らない項目を${parsed.unknown.size}個読み飛ばしました（新しい版のアプリで書き出した設定）".takeIf { parsed.unknown.isNotEmpty() },
            "合言葉・Wi-Fiのパスワードは入っていないので、このスマホの今の値のままです（まだなら手で入れる）".takeIf { !parsed.hasSecrets },
        ).joinToString("") { "\n\n※ $it" }
        if (changes.isEmpty()) { alert("変わる所はありません（今の設定と同じです）。$notes"); return }
        AlertDialog.Builder(this).setTitle("次の${changes.size}項目が変わります")
            .setMessage(changes.joinToString("\n") { "・${it.label}：${it.from} → ${it.to}" } + notes)
            .setPositiveButton("読み込む") { _, _ ->
                if (Status.running) toast("記録を止めてから読み込んでください")
                else { applyConfig(incoming); toast("設定を読み込みました"); build() }
            }
            .setNegativeButton("やめる", null).show()
    }

    private fun alert(message: String?) { AlertDialog.Builder(this).setMessage(message).setPositiveButton("OK", null).show() }

    /**
     * The circuit profile (SUGO): the spare of EcoCapture DASH. The phone shows the Ver.2 logger's
     * values only, so there is nothing of the Eco Mileage race here: no class, lines or phone laps.
     */
    private fun buildCircuit(running: Boolean) {
        note("DASH（HD7Hのモニター）と同じ画面を、Ver.2から受け取った値で出す：今の周・ベスト比・前周と前周比・ベスト・周・経過・時刻、" +
            "油圧が回転数に対して低いとき・油温${"%.0f".format(settings.oilWarn)}℃・水温${"%.0f".format(settings.waterWarn)}℃を超えたら赤い帯（重なったら並べる）と警報音。" +
            "周回はVer.2が数える。このスマホはサーバー・Podiumへ送らない（Ver.2が同じキーで送っているため）。スマホのGNSS・IMUの記録は残す")
        loggerSection(running, true)

        section("警告")
        val oil = field("油温の警告（℃）", "%.0f".format(settings.oilWarn), "120", !running, InputType.TYPE_CLASS_NUMBER)
        val water = field("水温の警告（℃、油温センサーが途絶えても警告が出るように）", "%.0f".format(settings.waterWarn), "110", !running, InputType.TYPE_CLASS_NUMBER)
        val volume = field("警報音の大きさ（0〜100%、スマホの「アラーム」の音量でも変わる）", "%.0f".format(settings.alarmVolume * 100), "80", true, InputType.TYPE_CLASS_NUMBER)
        note("DASHと同じく、温度は1秒・油圧は0.5秒続けたら出て、警報音（高い「ピピピ…」を6回、約10秒）を1回鳴らし、帯を1分点滅させる。5秒続けて戻ったら消える。" +
            "油圧は1500rpm未満では見ない（1500rpmで100kPa、3000rpm以上で200kPaを下回ったら）。温度の数値はDASHの設定（oil_warn・water_warn）と同じにしておく")
        val warnButtons = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        warnButtons.addView(button("保存") {
            val o = oil.text.toString().trim().toDoubleOrNull(); val wt = water.text.toString().trim().toDoubleOrNull()
            val v = volume.text.toString().trim().toDoubleOrNull()
            if (!running) {
                if (o == null || o !in 60.0..200.0 || wt == null || wt !in 60.0..200.0) { toast("温度は60〜200℃で入れてください"); return@button }
                settings.oilWarn = o; settings.waterWarn = wt
            }
            if (v != null) settings.alarmVolume = (v / 100).coerceIn(0.0, 1.0)
            toast(if (running) "音の大きさを保存しました（記録を始め直すと効く）" else "保存しました"); build()
        })
        warnButtons.addView(button("警報音を鳴らしてみる（約10秒）") {
            val v = volume.text.toString().trim().toDoubleOrNull()?.let { (it / 100).coerceIn(0.0, 1.0) } ?: settings.alarmVolume
            Alarm.play(v)
        })
        column.addView(warnButtons)
        if (running) note("温度は記録中は変えられません（止めてから変えてください）")

        section("ロガーの周回")
        val st = Circuit.state
        note(if (!running) "記録を始めると、ロガーの周回がここに出る"
            else if (!LoggerFeed.fresh()) "ロガーにつながっていません：" + LoggerFeed.reason()
            else "周 ${st.lapNo}　前周 ${st.last}　ベスト ${st.best}　経過 ${st.elapsed}" +
                (if (st.elapsed != CircuitState.WAITING) "（計測中）" else "（スタート前）"))
        note("予選のあと決勝の前に、ロガーの周回をリセットする（経過はリセット後に最初にコントロールラインを通った時から数える）。" +
            "PCの Reset-Laps.cmd と同じ（ラインはそのまま）")
        column.addView(button("ロガーの周回をリセット（予選のあと・決勝の前）") {
            AlertDialog.Builder(this).setMessage("Ver.2ロガーの周回の記録（前周・ベスト・経過）を消して、スタート前に戻します。ラインはそのまま。よいですか？")
                .setPositiveButton("リセット") { _, _ -> resetLogger(circuit = true) }
                .setNegativeButton("やめる", null).show()
        }, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = px(8) })
    }

    /** The Ver.2 logger: how to reach it, its key and address; the race notes only for the Eco Mileage profile. */
    private fun loggerSection(running: Boolean, circuit: Boolean) {
        section(if (circuit) "Ver.2ロガーにつなぐ" else "Ver.2ロガーの位置を使う（車のダッシュ用）")
        if (!circuit) note("ロガーのWi-Fi（インターネットなし）にこのアプリだけがつなぎ、ロガーの位置で周回・速度を出す。スマホのほかのアプリ（Discord）はLTEのまま。" +
            "ロガーから2秒届かなければスマホのGNSSに切り替え、画面に「ロガー未接続」を出す。合言葉が空なら使わない")
        var lan = settings.loggerLan
        val via = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        column.addView(via)
        val lSsid: EditText; val lPass: EditText
        fun showVia() {
            via.removeAllViews()
            for ((value, label) in listOf(true to "このスマホのテザリング・同じWi-Fi（ロガーが子機。SUGOはこちら）",
                                          false to "ロガーのWi-Fi（ロガーが親機。エコラン大会の形）")) {
                via.addView(button((if (lan == value) "✓ " else "　") + label) { if (!running) { lan = value; showVia() } }.apply {
                    (background as GradientDrawable).setColor(if (lan == value) Color.rgb(35, 134, 54) else Color.rgb(48, 54, 61))
                    gravity = android.view.Gravity.START or android.view.Gravity.CENTER_VERTICAL
                    textSize = 15f
                }, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = px(6) })
            }
        }
        showVia()
        note("テザリング・同じWi-Fi：アドレスが空なら、このスマホのWi-Fi・テザリングの中を自動で探す（数秒）。" +
            "ロガーのWi-Fi：インターネットのないロガーのWi-Fiにこのアプリだけがつなぐ（ほかのアプリはLTEのまま）。Wi-Fi名・パスワードはこちらだけで使う")
        lSsid = field("ロガーのWi-Fi名（ロガーのWi-Fiのときだけ）", settings.loggerSsid, "例：ecologger-dash", !running, InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS)
        lPass = field("ロガーのWi-Fiのパスワード（同上）", settings.loggerPass, "", !running,
            InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS or InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD)
        val lKey = field("コースウォーク画面の合言葉（URLの k= の後ろ。URLごと貼ってもよい）", settings.loggerKey, "空欄ならロガーを使わない", !running,
            InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS or InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD)
        val lHost = field("ロガーのアドレス", settings.loggerHost, "空欄なら、テザリングは自動で探す・ロガーのWi-Fiは ${Settings.DEFAULT_LOGGER_HOST}", !running)
        if (!running) column.addView(button("ロガーの設定を保存") {
            var key = lKey.text.toString().trim(); var host = lHost.text.toString().trim()
            // A pasted course-walk URL (http://<host>:8082/?k=<key>) gives both.
            Regex("""^https?://([^/:?]+)(?::\d+)?/?\?(?:.*&)?k=([^&\s]+)""").find(key)?.let { m ->
                key = m.groupValues[2]; if (host.isEmpty() && !lan) host = m.groupValues[1]
            }
            settings.loggerLan = lan
            settings.loggerSsid = lSsid.text.toString(); settings.loggerPass = lPass.text.toString()
            settings.loggerKey = key; settings.loggerHost = host
            toast(if (settings.loggerConfigured) "保存しました（記録を始めるとロガーへつなぎます）" else "保存しました（ロガーは使いません）"); build()
        }, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = px(6) })
        if (running) note(if (circuit) (if (LoggerFeed.fresh()) "ロガーにつながっています" + LoggerFeed.host.takeIf { it.isNotEmpty() }?.let { "（$it）" }.orEmpty()
                else "ロガーにつながっていません：" + LoggerFeed.reason() + LoggerFeed.error.takeIf { it.isNotEmpty() }?.let { "（$it）" }.orEmpty())
            else if (Status.fromLogger) "いまはロガーの位置を使っています" else "いまはスマホのGNSSです：" +
            (if (settings.loggerConfigured) LoggerFeed.reason() + LoggerFeed.error.takeIf { it.isNotEmpty() }?.let { "（$it）" }.orEmpty() else "ロガー未設定"))
    }

    /** The phone's lap reset also resets the Ver.2 logger's laps (over its Wi-Fi), and says whether it did. */
    private fun resetLogger(circuit: Boolean = false) {
        if (!settings.loggerConfigured) { if (circuit) toast("ロガーの設定がまだです"); return }
        val link = LoggerLink.current
        val result = { ok: Boolean, msg: String ->
            LoggerFeed.syncNote = if (ok) "ロガーの周回もリセットしました" else "ロガーの周回はリセットできていません（$msg）"
            AlertDialog.Builder(this).setMessage(if (circuit) (if (ok) "ロガーの周回をリセットしました。" else "ロガーの周回はリセットできていません（$msg）。" +
                    "\nロガーにつないでからもう一度押すか、PCの Reset-Laps.cmd を使ってください。")
                else "アプリの周回をリセットしました。\n" + LoggerFeed.syncNote +
                if (ok) "" else "\nロガーにつないでからもう一度リセットするか、コースウォーク画面で「周回数をリセット」を押してください。")
                .setPositiveButton("OK", null).show()
            build()
        }
        if (link == null) result(false, "記録を始めていないのでロガーにつないでいません")
        else link.resetLogger { ok, msg -> runOnUiThread { if (!isFinishing) result(ok, msg) } }
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
                if (Race.setHere(target)) { toast("現在地をラインにしました"); build() }
                else toast("測位できていないか、精度が%.0fmより悪いです（空が開けた所で少し待つ）".format(Race.HERE_MAX_ACC_M))
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

    /** Reads one QR code through Google Play services (no camera permission) and hands its text to [onText]. */
    private fun scanQr(onText: (String) -> Unit) {
        com.google.mlkit.vision.codescanner.GmsBarcodeScanning.getClient(this,
            com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions.Builder()
                .setBarcodeFormats(com.google.mlkit.vision.barcode.common.Barcode.FORMAT_QR_CODE).build())
            .startScan()
            .addOnSuccessListener { code -> code.rawValue?.let { onText(it) } ?: toast("読み取れませんでした") }
            .addOnFailureListener { toast("QRの読み取りを使えません（${it.message}）。貼り付けを使ってください") }
    }

    private fun scanReference() {
        val doImport = { scanQr { importText(it) } }
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
