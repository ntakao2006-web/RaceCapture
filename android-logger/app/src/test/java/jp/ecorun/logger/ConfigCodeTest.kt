package jp.ecorun.logger

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class ConfigCodeTest {
    /** A phone as the settings screen hands it over; every value is made up. */
    private val phone: Map<String, String> = mapOf(
        "pf" to "ecorun", "car" to "car2",
        "p" to "wss://main.example.com/ws/audio/car2", "b" to "wss://spare.example.com/ws/audio/car2",
        "ll" to "0", "ls" to "example-logger", "lp" to "example-pass-1234", "lk" to "EXAMPLEKEY0123456789abcdef", "lh" to "",
        "cl" to "CN_MOTORCYCLE", "tl" to "3", "tm" to "987.36", "ds" to "6856.72", "ml" to "10",
        "ow" to "120", "ww" to "110", "av" to "80", "ks" to "1", "fb" to "1",
    ) + RaceClass.entries.associate { ConfigCode.marginKey(it) to "30" }

    private fun code(body: String, head: String = "ELCFG1") = "$head|$body|id=${ConfigCode.id(body)}"

    @Test
    fun comesBackTheSameWithoutTheSecrets() {
        val text = ConfigCode.encode(phone)
        val parsed = ConfigCode.parse(text)
        // Laps, time and distance belong to the class unless it is the hand-entered one.
        assertEquals(phone - setOf("lp", "lk", "tl", "tm", "ds"), parsed.values)
        assertFalse(parsed.hasSecrets)
        assertTrue(parsed.unknown.isEmpty())
        assertFalse(text.contains("example-pass-1234"))
        assertFalse(text.contains("EXAMPLEKEY"))
    }

    @Test
    fun secretsGoOnlyWhenAsked() {
        val parsed = ConfigCode.parse(ConfigCode.encode(phone, secrets = true))
        assertEquals("example-pass-1234", parsed.values["lp"])
        assertEquals("EXAMPLEKEY0123456789abcdef", parsed.values["lk"])
        assertTrue(parsed.hasSecrets)
        assertTrue(ConfigCode.secretsIn(phone))
    }

    /** A phone without the key must not wipe the key of the phone that reads its settings. */
    @Test
    fun anEmptySecretIsNeverWritten() {
        val bare = phone + mapOf("lp" to "", "lk" to "")
        assertFalse(ConfigCode.secretsIn(bare))
        val parsed = ConfigCode.parse(ConfigCode.encode(bare, secrets = true))
        assertFalse("lp" in parsed.values)
        assertFalse("lk" in parsed.values)
    }

    /** A QR code read from another phone's screen is comfortable up to about 500 characters (version 17, level M: 504 bytes). */
    @Test
    fun isShortEnoughForAQrCode() {
        val text = ConfigCode.encode(phone, secrets = true)
        println("ConfigCode: ${ConfigCode.encode(phone).length} characters, ${text.length} with the secrets")
        assertTrue(text.length < 500)
        assertTrue(text.all { it.code in 0x21..0x7e })
    }

    @Test
    fun handEnteredRulesTravelOnlyWithThatClass() {
        val custom = phone + mapOf("cl" to "OTHER", "tl" to "5", "tm" to "1500.5", "ds" to "")
        val parsed = ConfigCode.parse(ConfigCode.encode(custom))
        assertEquals("5", parsed.values["tl"])
        assertEquals("1500.5", parsed.values["tm"])
        assertEquals("", parsed.values["ds"])
        // Written by hand next to a class with its own rules: left out.
        assertFalse("tl" in ConfigCode.parse(code("cl=CNG3|tl=9")).values)
        assertFalse("tl" in ConfigCode.parse(code("car=a|tl=9")).values)
    }

    @Test
    fun otherCharactersSurvive() {
        val odd = phone + mapOf("car" to "2号車 A|B 100%", "ls" to "net=1")
        val text = ConfigCode.encode(odd)
        assertTrue(text.all { it.code in 0x21..0x7e })
        val parsed = ConfigCode.parse(text)
        assertEquals("2号車 A|B 100%", parsed.values["car"])
        assertEquals("net=1", parsed.values["ls"])
    }

    /** Chat apps wrap long lines and add spaces around a pasted text. */
    @Test
    fun lineBreaksAndOuterSpacesAreIgnored() {
        val text = ConfigCode.encode(phone)
        val wrapped = "  " + text.chunked(40).joinToString("\r\n") + "\n"
        assertEquals(ConfigCode.parse(text), ConfigCode.parse(wrapped))
    }

    @Test
    fun unknownKeysAreSkipped() {
        val parsed = ConfigCode.parse(code("car=car3|zz=later|ow=115"))
        assertEquals(mapOf("car" to "car3", "ow" to "115"), parsed.values)
        assertEquals(listOf("zz"), parsed.unknown)
    }

    @Test
    fun aNewerVersionIsRefused() {
        val e = assertThrows(ConfigCode.Invalid::class.java) { ConfigCode.parse(code("car=car3", "ELCFG2")) }
        assertTrue(e.message!!.contains("新しい版"))
    }

    @Test
    fun otherTextsAreRefused() {
        for (text in listOf("", "https://example.com", "ECOLINES1|c=-|s=-|g=-|id=0000", "ELCFG|car=a|id=0000", "ELCFGx|car=a|id=0000",
                            "ELCFG0|car=a|id=0000", "ELCFG1", "ELCFG1|id=DA39", code("zz=1"), code("car")))
            assertThrows(text, ConfigCode.Invalid::class.java) { ConfigCode.parse(text) }
    }

    @Test
    fun aChangedOrCutTextIsRefused() {
        val text = ConfigCode.encode(phone)
        assertThrows(ConfigCode.Invalid::class.java) { ConfigCode.parse(text.replace("car=car2", "car=car3")) }
        assertThrows(ConfigCode.Invalid::class.java) { ConfigCode.parse(text.dropLast(1)) }
        val cut = assertThrows(ConfigCode.Invalid::class.java) { ConfigCode.parse(text.take(text.length / 2)) }
        assertTrue(cut.message!!.contains("途中で切れています"))
    }

    /** The limits of the settings screen's save buttons: 60-200 C, 0-100 %, margin 0-600 s, shortest lap 5-7200 s. */
    @Test
    fun valuesOutOfRangeAreRefused() {
        for (body in listOf("ow=59", "ow=201", "ww=abc", "ow=", "av=101", "av=80.5", "ks=2", "ll=yes", "pf=kart", "cl=F1",
                            "m_CNG3=601", "m_CNG3=-1", "ml=4", "ml=7201", "cl=OTHER|tl=0", "cl=OTHER|tl=2.5", "cl=OTHER|tm=0",
                            "car=" + "x".repeat(65), "car=a%0Ab", "car=a%ZZ", "car=a%4", "car=a b"))
            assertThrows(body, ConfigCode.Invalid::class.java) { ConfigCode.parse(code(body)) }
        for (body in listOf("ow=60", "ow=200", "av=0", "av=100", "m_CNG3=0", "m_CNG3=600", "ml=5", "ml=7200", "cl=OTHER|tl=|tm=|ds=", "car=a%20b"))
            ConfigCode.parse(code(body))
        assertEquals("120", ConfigCode.parse(code("ow=120.0")).values["ow"])
    }

    @Test
    fun aRefusedSecretIsNotPrinted() {
        val long = "s".repeat(70)
        val e = assertThrows(ConfigCode.Invalid::class.java) { ConfigCode.parse(code("lp=$long")) }
        assertFalse(e.message!!.contains("sss"))
        val out = assertThrows(ConfigCode.Invalid::class.java) { ConfigCode.encode(phone + ("lp" to long), secrets = true) }
        assertFalse(out.message!!.contains("sss"))
    }

    @Test
    fun listsWhatWouldChange() {
        val other = phone + mapOf("car" to "car3", "b" to "", "ll" to "1", "cl" to "CNG3", "m_CNG3" to "45", "ow" to "125", "ks" to "0")
        val changes = ConfigCode.changes(phone, ConfigCode.parse(ConfigCode.encode(other)).values)
        assertEquals(listOf(
            ConfigCode.Change("車の名前", "car2", "car3"),
            ConfigCode.Change("予備サーバーのURL", "wss://spare.example.com/ws/audio/car2", "（空）"),
            ConfigCode.Change("ロガーへのつなぎ方", "ロガーのWi-Fi", "このスマホのテザリング・同じWi-Fi"),
            ConfigCode.Change("クラス", "CN二輪", "CNG3"),
            ConfigCode.Change("余裕（CNG3）", "30秒", "45秒"),
            ConfigCode.Change("油温の警告", "120℃", "125℃"),
            ConfigCode.Change("画面を消さない（記録していなくても）", "オン", "オフ"),
        ), changes)
        assertTrue(ConfigCode.changes(phone, ConfigCode.parse(ConfigCode.encode(phone, secrets = true)).values).isEmpty())
    }

    @Test
    fun handEnteredRulesAreListedReadably() {
        val custom = phone + mapOf("cl" to "OTHER", "tl" to "5", "tm" to "1500.5", "ds" to "")
        val changes = ConfigCode.changes(phone, ConfigCode.parse(ConfigCode.encode(custom)).values)
        assertEquals(listOf(
            ConfigCode.Change("クラス", "CN二輪", "その他"),
            ConfigCode.Change("規定周回数", "3周", "5周"),
            ConfigCode.Change("規定時間", "16:27.36", "25:00.50"),
            ConfigCode.Change("規定距離", "6856.72m", "（空）"),
        ), changes)
    }

    @Test
    fun secretsAreNeverShownInTheList() {
        val fresh = phone + mapOf("lp" to "", "lk" to "other-example-key")
        val changes = ConfigCode.changes(fresh, ConfigCode.parse(ConfigCode.encode(phone, secrets = true)).values)
        assertEquals(listOf(
            ConfigCode.Change("ロガーのWi-Fiのパスワード", "（なし）", "（入る）"),
            ConfigCode.Change("コースウォーク画面の合言葉", "（入っている）", "（別の値になる）"),
        ), changes)
    }

    /** With the race settings locked, the class, the margins and the hand-entered rules stay. */
    @Test
    fun theRaceLockHoldsTheClassItems() {
        val custom = phone + mapOf("cl" to "OTHER", "car" to "car3", "ml" to "20")
        val (kept, held) = ConfigCode.withoutRace(ConfigCode.parse(ConfigCode.encode(custom)).values)
        assertEquals(1 + RaceClass.entries.size + 3, held)
        assertTrue(kept.keys.none { it == "cl" || it.startsWith("m_") || it in setOf("tl", "tm", "ds") })
        assertEquals("car3", kept["car"])
        assertEquals("20", kept["ml"])
    }

    @Test
    fun everyKeyIsUsedOnce() {
        assertEquals(ConfigCode.ITEMS.size, ConfigCode.ITEMS.map { it.key }.toSet().size)
        assertEquals(phone.keys, ConfigCode.ITEMS.map { it.key }.toSet())
        assertEquals(listOf("lp", "lk"), ConfigCode.ITEMS.filter { it.secret }.map { it.key })
    }

    @Test
    fun numbersAreWrittenShort() {
        assertEquals("30", ConfigCode.num(30.0))
        assertEquals("12.5", ConfigCode.num(12.5))
        assertEquals("2360.11", ConfigCode.num(39 * 60 + 20.11))
        assertEquals("0.8", ConfigCode.num(0.8f.toDouble()))
        assertEquals("0", ConfigCode.num(0.0))
    }
}
