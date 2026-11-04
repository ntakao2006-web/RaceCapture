package jp.ecorun.logger

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import android.os.SystemClock
import org.json.JSONObject
import java.io.File

/**
 * The circuit screen's [CircuitModel] while the service runs: [LoggerLink] hands it each frame
 * and the service's 100 ms tick hands it null when none came (so a lost link ends the warning
 * the way the DASH's failed fetch does). All calls are on the service's handler thread; the
 * screen reads [state] and [lastGoodAt].
 */
object Circuit {
    @Volatile var state = CircuitState()
    /** elapsedRealtime of the last frame from a logger that receives its MCU, 0 before any. */
    @Volatile var lastGoodAt = 0L
    /** Frames come without the `dash` block: the logger's EcoCapture predates the circuit screen. */
    @Volatile var oldLogger = false
    @Volatile var active = false
    private var model: CircuitModel? = null
    private var lastFrameAt = 0L
    private var volume = 0.8

    fun start(context: Context) {
        val s = Settings(context)
        volume = s.alarmVolume
        model = CircuitModel(CircuitConfig(oilWarn = s.oilWarn, waterWarn = s.waterWarn), LapRef(File(context.filesDir, LAPREF)))
        state = CircuitState(); lastGoodAt = 0; oldLogger = false; lastFrameAt = 0
        active = true
    }

    fun stop() { active = false; model = null }

    /** One of field.py's live frames (with its `dash` block). */
    fun onFrame(j: JSONObject) {
        val m = model ?: return
        val now = SystemClock.elapsedRealtime()
        lastFrameAt = now
        val d = j.optJSONObject("dash")
        oldLogger = !j.has("dash")
        val f = parse(j, d)
        if (f.connected) lastGoodAt = now
        val (s, sound) = m.update(f, now / 1000.0)
        state = s
        if (sound) Alarm.play(volume)
    }

    /** Every 100 ms: with no frame for a while, the model hears that nothing came. */
    fun tick() {
        val m = model ?: return
        val now = SystemClock.elapsedRealtime()
        if (now - lastFrameAt < 300) return
        state = m.update(null, now / 1000.0).first
    }

    private fun parse(j: JSONObject, d: JSONObject?): CircuitInput {
        fun JSONObject.num(k: String): Double? = if (!has(k) || isNull(k)) null else optDouble(k).takeIf { !it.isNaN() }
        val lap = d?.optJSONObject("lap") ?: JSONObject()
        val video = d?.optJSONObject("video")
        return CircuitInput(
            connected = j.optBoolean("connected") && d != null,
            rec = j.optBoolean("rec"),
            lat = j.num("lat"), lon = j.num("lon"),
            speedKmh = d?.num("speed"),
            currentLap = lap.num("CurrentLap"), elapsedMin = lap.num("ElapsedTime"), lastMin = lap.num("LapTime"),
            bestMin = lap.num("BestLap"), raceMin = lap.num("RaceTime"), diffS = lap.num("LapDiffS"),
            lastPit = lap.optBoolean("LastLapPit", false), startPit = lap.optBoolean("LapStartPit", false),
            oil = d?.num("oil"), water = d?.num("water"),
            press = d?.num("press"), rpm = d?.num("rpm"), // from an EcoCapture without them: null, no oil pressure warning
            utc = d?.optString("utc")?.takeIf { d.has("utc") && !d.isNull("utc") },
            video = video?.let { CircuitVideo(it.optBoolean("recording"), it.num("minutes_left")) },
        )
    }

    private const val LAPREF = "circuit_lapref.txt"
}

/** Plays [AlarmTone] on the alarm stream, so it sounds with the media volume down. */
object Alarm {
    private var track: AudioTrack? = null

    @Synchronized fun play(volume: Double) {
        try {
            track?.release()
            val pcm = AlarmTone.samples(volume)
            track = AudioTrack.Builder()
                .setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build())
                .setAudioFormat(AudioFormat.Builder().setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .setSampleRate(AlarmTone.RATE).setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build())
                .setTransferMode(AudioTrack.MODE_STATIC)
                .setBufferSizeInBytes(pcm.size * 2)
                .build().apply { write(pcm, 0, pcm.size); play() }
        } catch (_: Exception) { track = null }
    }
}
