package jp.ecorun.logger

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast

/** One screen: settings, start/stop, and the live status. */
class MainActivity : Activity() {
    private lateinit var settings: Settings
    private lateinit var car: EditText
    private lateinit var primary: EditText
    private lateinit var backup: EditText
    private lateinit var button: Button
    private lateinit var status: TextView
    private val ui = Handler(Looper.getMainLooper())

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        settings = Settings(this)
        val pad = (16 * resources.displayMetrics.density).toInt()
        val column = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad, pad, pad)
        }
        fun label(text: String) = TextView(this).apply { this.text = text; setPadding(0, pad / 2, 0, 0) }
        fun field(value: String, hint: String) = EditText(this).apply {
            setText(value); this.hint = hint; isSingleLine = true
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
        }
        car = field(settings.carName, "例：car2")
        primary = field(settings.primaryUrl, "wss://…/ws/audio/<room>")
        backup = field(settings.backupUrl, "空欄なら予備なし")
        button = Button(this).apply { setOnClickListener { toggle() } }
        status = TextView(this).apply { textSize = 16f; setPadding(0, pad, 0, 0) }
        column.addView(label("車の名前（記録ファイル名と、サーバーでの表示名）"))
        column.addView(car, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
        column.addView(label("主サーバーのURL"))
        column.addView(primary, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
        column.addView(label("予備サーバーのURL"))
        column.addView(backup, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
        column.addView(button, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = pad })
        column.addView(status)
        setContentView(ScrollView(this).apply { addView(column) })
        refresh()
    }

    override fun onResume() { super.onResume(); refresh() }
    override fun onPause() { ui.removeCallbacksAndMessages(null); super.onPause() }

    private fun refresh() {
        val running = Status.running
        button.text = if (running) "記録を止める" else "記録を始める"
        listOf(car, primary, backup).forEach { it.isEnabled = !running }
        status.text = Status.text
        ui.removeCallbacksAndMessages(null)
        ui.postDelayed({ refresh() }, 500)
    }

    private fun toggle() {
        if (Status.running) { LoggerService.stop(this); ui.postDelayed({ refresh() }, 300); return }
        settings.carName = car.text.toString()
        settings.primaryUrl = primary.text.toString()
        settings.backupUrl = backup.text.toString()
        val missing = PERMISSIONS.filter { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }
        if (missing.isNotEmpty()) { requestPermissions(missing.toTypedArray(), 1); return }
        LoggerService.start(this)
        ui.postDelayed({ refresh() }, 300)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<String>, results: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, results)
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED) {
            LoggerService.start(this)
            ui.postDelayed({ refresh() }, 300)
        } else {
            Toast.makeText(this, "正確な位置情報の許可が必要です", Toast.LENGTH_LONG).show()
        }
    }

    companion object {
        private val PERMISSIONS = buildList {
            add(Manifest.permission.ACCESS_FINE_LOCATION)
            add(Manifest.permission.ACCESS_COARSE_LOCATION)
            if (android.os.Build.VERSION.SDK_INT >= 33) add(Manifest.permission.POST_NOTIFICATIONS)
        }
    }
}
