package jp.ecorun.logger

import org.junit.Assert.assertEquals
import org.junit.Test

class LoggerLightsTest {
    private val ok = Light.Kind.OK; private val warn = Light.Kind.WARN; private val bad = Light.Kind.BAD
    private val off = Light.Kind.OFF; private val unknown = Light.Kind.UNKNOWN

    @Test
    fun allWellIsThreeGreenLights() {
        val l = LoggerLights.of(fresh = true, mcu = true, rec = true, fix = 3, send = "ok")
        assertEquals(LoggerLights(Light("記録中", ok), Light("測位OK", ok), Light("送信中", ok)), l)
        assertEquals(Light("測位OK", ok), LoggerLights.of(true, true, true, 2, "ok").gnss)
    }

    /** Not joined yet, or the frames stopped: nothing is shown as good, whatever came last. */
    @Test
    fun withoutFreshFramesEveryLightIsNotKnown() {
        val l = LoggerLights.of(fresh = false, mcu = true, rec = true, fix = 3, send = "ok")
        assertEquals(LoggerLights(Light("記録 --", unknown), Light("測位 --", unknown), Light("送信 --", unknown)), l)
        assertEquals(l, LoggerLights.of(false, false, false, 0, null))
    }

    /** The words and kinds of EcoCapture DASH's send_light (RaceCapture-UNOQ/dash_model.py). */
    @Test
    fun sendingFollowsTheLoggersWord() {
        fun send(s: String?) = LoggerLights.of(true, true, true, 3, s).send
        assertEquals(Light("送信中", ok), send("ok"))
        assertEquals(Light("未送信", warn), send("warn"))
        assertEquals(Light("送信OFF", off), send("off"))
    }

    /** An EcoCapture older than the item sends none; a word this app does not know is not good either. */
    @Test
    fun sendingFromAnOlderLoggerIsNotKnown() {
        for (s in listOf(null, "", "OK", "streaming", "true", "null")) {
            val l = LoggerLights.of(true, true, true, 3, s)
            assertEquals(s, Light("送信 --", unknown), l.send)
            assertEquals(Light("記録中", ok), l.rec)   // the rest still shows
            assertEquals(Light("測位OK", ok), l.gnss)
        }
    }

    @Test
    fun stoppedRecordingAndNoFixAreBad() {
        val l = LoggerLights.of(fresh = true, mcu = true, rec = false, fix = 0, send = "warn")
        assertEquals(LoggerLights(Light("記録停止", bad), Light("測位なし", bad), Light("未送信", warn)), l)
    }

    /** Without the MCU the logger has no fix to tell: not known, while recording and sending still are. */
    @Test
    fun withoutTheMcuTheFixIsNotKnown() {
        val l = LoggerLights.of(fresh = true, mcu = false, rec = true, fix = 0, send = "ok")
        assertEquals(LoggerLights(Light("記録中", ok), Light("測位 --", unknown), Light("送信中", ok)), l)
        assertEquals(Light("測位 --", unknown), LoggerLights.of(true, false, true, 3, "ok").gnss)
    }
}
