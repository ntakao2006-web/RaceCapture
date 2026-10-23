package jp.ecorun.logger

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.BatteryManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.os.SystemClock
import android.view.Gravity
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.WindowManager
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.Toast

/**
 * The driver screen (landscape). Start is one tap; stop needs a long press so a
 * brush against the phone cannot end the recording. While recording the screen
 * stays on and shows over the lock screen.
 */
class MainActivity : Activity() {
    private lateinit var dashboard: DashboardView
    private lateinit var startStop: Button
    private lateinit var settingsButton: Button
    private val ui = Handler(Looper.getMainLooper())
    private var noFixSince = 0L

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Race.init(this)
        Imu.init(this)
        RaceClass.ensure(this)
        window.statusBarColor = Color.BLACK
        window.navigationBarColor = Color.BLACK
        dashboard = DashboardView(this)
        val dp = resources.displayMetrics.density
        startStop = button("", Color.rgb(35, 134, 54)).apply {
            setOnClickListener { if (Status.running) toast("止めるときは長押しします") else start() }
            setOnLongClickListener { if (Status.running) { LoggerService.stop(this@MainActivity); later() }; true }
        }
        settingsButton = button("設定", Color.rgb(48, 54, 61)).apply {
            // During the race the settings open only on a long press, so a brush cannot change anything.
            setOnClickListener {
                if (Race.racing()) toast("走行中は長押しで開きます")
                else startActivity(Intent(this@MainActivity, SettingsActivity::class.java))
            }
            setOnLongClickListener { startActivity(Intent(this@MainActivity, SettingsActivity::class.java)); true }
        }
        val bar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            val m = (8 * dp).toInt()
            setPadding(m * 2, 0, m * 2, m)
            addView(settingsButton, LinearLayout.LayoutParams(0, MATCH_PARENT, 1f).apply { marginEnd = m })
            addView(startStop, LinearLayout.LayoutParams(0, MATCH_PARENT, 3f))
        }
        val root = FrameLayout(this)
        root.addView(dashboard, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
        root.addView(bar, FrameLayout.LayoutParams(MATCH_PARENT, (64 * dp).toInt(), Gravity.BOTTOM))
        dashboard.bottomReservePx = 64 * dp
        setContentView(root)
        // Full screen: the status bar would cover the top strip. A swipe from the edge brings it back briefly.
        window.insetsController?.let {
            it.hide(android.view.WindowInsets.Type.systemBars())
            it.systemBarsBehavior = android.view.WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        }
    }

    private fun button(text: String, color: Int) = Button(this).apply {
        this.text = text
        textSize = 20f
        setTextColor(Color.WHITE)
        isAllCaps = false
        background = GradientDrawable().apply { setColor(color); cornerRadius = 14 * resources.displayMetrics.density }
    }

    override fun onResume() { super.onResume(); refresh() }
    override fun onPause() { ui.removeCallbacksAndMessages(null); super.onPause() }

    private fun later() = ui.postDelayed({ refresh() }, 300)

    private fun refresh() {
        val running = Status.running
        val settings = Settings(this)
        if (running || settings.keepScreenOn) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        setShowWhenLocked(running)
        val brightness = if (running && settings.fullBrightness) 1f else WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE
        if (window.attributes.screenBrightness != brightness) {
            window.attributes = window.attributes.apply { screenBrightness = brightness }
        }

        startStop.text = if (running) "■ 長押しで停止" else "● 記録を始める"
        (startStop.background as GradientDrawable).setColor(if (running) Color.rgb(48, 54, 61) else Color.rgb(35, 134, 54))

        val battery = registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val level = battery?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val scale = battery?.getIntExtra(BatteryManager.EXTRA_SCALE, 100) ?: 100
        val plugged = (battery?.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0) ?: 0) != 0

        val now = SystemClock.elapsedRealtime()
        if (!running || Status.fix != 0) noFixSince = now
        dashboard.dash = Dash(
            running = running,
            recSeconds = if (running) (now - Status.startedAt) / 1000 else 0,
            recordingOk = Status.fileName != null,
            fix = Status.fix, sats = Status.sats, accuracyM = Status.accuracyM,
            speedKmh = if (running) Status.speedKmh else null,
            relay = Status.relay, relayConnected = Status.relayConnected,
            batteryPct = if (level >= 0) level * 100 / scale else null, charging = plugged,
            lap = Race.values(), config = Race.config(), laps = Race.laps(),
            classCode = settings.raceClass?.code ?: "",
            reference = Race.reference?.id?.let { "基準$it" } ?: "基準なし",
            source = if (!settings.loggerConfigured) null else if (running && Status.fromLogger) "ロガー" else "スマホ",
            warning = warning(running, now),
        )
        ui.removeCallbacksAndMessages(null)
        ui.postDelayed({ refresh() }, 200)
    }

    private fun warning(running: Boolean, now: Long): String? = when {
        running && Status.fileName == null -> "記録できていません：" + Status.logError.take(60)
        running && Settings(this).loggerConfigured && !Status.fromLogger ->
            "ロガー未接続：スマホのGNSSで計測中（" + LoggerFeed.reason() + "）"
        running && now - noFixSince > 5000 -> "GNSSが測位できていません（空が見える所へ）"
        running && LoggerFeed.lineId != null && LoggerFeed.lineId != Race.reference?.id ->
            "ラインがロガー（基準${LoggerFeed.lineId}）と違います：設定でQRを読み直す"
        !running && checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED ->
            "位置情報の許可がまだです（記録を始めると聞かれます）"
        !running && !getSystemService(PowerManager::class.java).isIgnoringBatteryOptimizations(packageName) ->
            "電池の最適化が有効です：設定 → 点検 から外してください"
        !running && Settings(this).urls.isEmpty() ->
            if (Settings(this).podiumKey.isNotEmpty()) "サーバーが未設定です（Podiumへ直接送ります）" else "サーバーが未設定です（記録だけします）"
        else -> null
    }

    private fun start() {
        val missing = PERMISSIONS.filter { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }
        if (missing.isNotEmpty()) { requestPermissions(missing.toTypedArray(), 1); return }
        LoggerService.start(this)
        later()
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<String>, results: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, results)
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED) {
            LoggerService.start(this); later()
        } else toast("正確な位置情報の許可が必要です")
    }

    private fun toast(s: String) = Toast.makeText(this, s, Toast.LENGTH_SHORT).show()

    companion object {
        val PERMISSIONS = buildList {
            add(Manifest.permission.ACCESS_FINE_LOCATION)
            add(Manifest.permission.ACCESS_COARSE_LOCATION)
            if (android.os.Build.VERSION.SDK_INT >= 33) add(Manifest.permission.POST_NOTIFICATIONS)
        }
    }
}
