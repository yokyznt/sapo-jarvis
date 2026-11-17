package io.github.yokyznt.sapo.core

import io.github.yokyznt.sapo.core.Command.Alarm
import io.github.yokyznt.sapo.core.Command.Battery
import io.github.yokyznt.sapo.core.Command.Call
import io.github.yokyznt.sapo.core.Command.OpenApp
import io.github.yokyznt.sapo.core.Command.Pc
import io.github.yokyznt.sapo.core.Command.Settings
import io.github.yokyznt.sapo.core.Command.Sms
import io.github.yokyznt.sapo.core.Command.Time
import io.github.yokyznt.sapo.core.Command.Timer
import io.github.yokyznt.sapo.core.Command.Torch
import io.github.yokyznt.sapo.core.Command.Volume
import io.github.yokyznt.sapo.core.Command.WhatsApp
import java.time.LocalDateTime
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import org.junit.Test

class IntentsTest {
    private val now = LocalDateTime.of(2026, 10, 31, 15, 0)

    private fun p(s: String, at: LocalDateTime = now) = Intents.parse(s, at)

    private fun check(cases: List<kotlin.Pair<String, Command>>) {
        for ((input, expected) in cases) assertEquals(expected, p(input), "frase: \"$input\"")
    }

    @Test
    fun calls() = check(
        listOf(
            "llama a mi mamá" to Call("mi mamá"),
            "Márcale a Juan" to Call("Juan"),
            "llámale a Pedro ahorita" to Call("Pedro"),
            "háblale a mi abuelita" to Call("mi abuelita"),
            "marca al 5512345678" to Call("5512345678"),
            "oye sapo, llama a Ana por favor" to Call("Ana"),
            "hazle una llamada a Luis" to Call("Luis"),
            "¿Puedes llamar a mi papá?" to Call("mi papá"),
            "LLAMA A MAMÁ" to Call("MAMÁ"),
            "llama al doctor Ramírez al celular" to Call("doctor Ramírez"),
            "habla a la oficina" to Call("la oficina")
        )
    )

    @Test
    fun sms() = check(
        listOf(
            "mándale un mensaje a Ana que ya voy" to Sms("Ana", "ya voy"),
            "dile a Juan que llego en 10 minutos" to Sms("Juan", "llego en 10 minutos"),
            "escríbele a mi mamá que ya comí" to Sms("mi mamá", "ya comí"),
            "envíale un mensaje de texto a Pedro diciendo que no voy" to Sms("Pedro", "no voy"),
            "manda un mensaje a Caro: ¿dónde estás?" to Sms("Caro", "¿dónde estás?"),
            "mándale a Ana: ya llegué" to Sms("Ana", "ya llegué"),
            "dile a Ana que me mande un whatsapp" to Sms("Ana", "me mande un whatsapp"),
            "dile a Ana que le diga a Luis que sí" to Sms("Ana", "le diga a Luis que sí"),
            "mándale un mensaje a Ana" to Sms("Ana", "")
        )
    )

    @Test
    fun whatsapp() = check(
        listOf(
            "dile por WhatsApp a Luis que ya salí" to WhatsApp("Luis", "ya salí"),
            "mándale un whats a Caro que la quiero mucho" to WhatsApp("Caro", "la quiero mucho"),
            "manda un wasap a mi hermano que me marque" to WhatsApp("mi hermano", "me marque"),
            "dile a Luis que ya voy por WhatsApp" to WhatsApp("Luis", "ya voy"),
            "escríbele por whatsapp a Mamá diciendo que ya llegué" to WhatsApp("Mamá", "ya llegué"),
            "mándale un WhatsApp a Luis" to WhatsApp("Luis", "")
        )
    )

    @Test
    fun openApp() = check(
        listOf(
            "abre Spotify" to OpenApp("Spotify"),
            "abre la app de YouTube" to OpenApp("YouTube"),
            "ábreme la cámara" to OpenApp("cámara"),
            "inicia Waze" to OpenApp("Waze"),
            "sapo abre google maps" to OpenApp("google maps")
        )
    )

    @Test
    fun alarmHours() = check(
        listOf(
            "pon una alarma a las 7 y media" to Alarm(7, 30, null),
            "pon una alarma a las 7:30" to Alarm(7, 30, null),
            "despiértame a las 6 am" to Alarm(6, 0, null),
            "pon una alarma a las 8 de la noche" to Alarm(20, 0, null),
            "pon una alarma al mediodía" to Alarm(12, 0, null),
            "pon una alarma a las 10 y cuarto" to Alarm(10, 15, null),
            "despiértame a las seis y media de la mañana" to Alarm(6, 30, null),
            "pon una alarma a las 7:30 pm" to Alarm(19, 30, null),
            "pon una alarma a las 6 menos cuarto" to Alarm(5, 45, null),
            "pon una alarma a las 12 de la noche" to Alarm(0, 0, null),
            "pon una alarma a la una y media de la tarde" to Alarm(13, 30, null),
            "pon una alarma para mañana a las 6:15 a.m." to Alarm(6, 15, null),
            "pon una alarma a las 19:45" to Alarm(19, 45, null),
            "pon una alarma a medianoche" to Alarm(0, 0, null),
            "levántame a las 5 de la madrugada" to Alarm(5, 0, null),
            "pon una alarma a las 7.20" to Alarm(7, 20, null),
            "ponme una alarma a las 4 de la tarde" to Alarm(16, 0, null),
            "despiértame a las 12 del mediodía" to Alarm(12, 0, null)
        )
    )

    @Test
    fun alarmLabels() = check(
        listOf(
            "pon una alarma a las 7 para ir al gym" to Alarm(7, 0, "ir al gym"),
            "alarma a las 3 de la tarde para la junta" to Alarm(15, 0, "la junta"),
            "pon una alarma para la pastilla a las 9 de la noche" to Alarm(21, 0, "la pastilla"),
            "pon una alarma a las 8 que diga sacar la basura" to Alarm(8, 0, "sacar la basura"),
            "pon una alarma para las 7" to Alarm(7, 0, null)
        )
    )

    @Test
    fun alarmRelativeUsesNow() {
        assertEquals(Alarm(15, 20, null), p("despiértame en 20 minutos"))
        assertEquals(Alarm(16, 30, null), p("pon una alarma dentro de una hora y media"))
        assertEquals(Alarm(0, 20, null), p("despiértame en media hora", LocalDateTime.of(2026, 10, 31, 23, 50)))
    }

    @Test
    fun alarmWithoutHourIsChat() {
        assertEquals(Command.Chat("pon una alarma"), p("pon una alarma"))
        assertEquals(Command.Chat("quita la alarma de las 7"), p("quita la alarma de las 7"))
        assertEquals(Command.Chat("¿a qué hora es mi alarma?"), p("¿a qué hora es mi alarma?"))
    }

    @Test
    fun timers() = check(
        listOf(
            "pon un temporizador de 5 minutos" to Timer(300),
            "pon un temporizador de media hora" to Timer(1800),
            "temporizador de 90 segundos" to Timer(90),
            "pon un timer de una hora y media" to Timer(5400),
            "pon un temporizador de cinco minutos" to Timer(300),
            "pon un temporizador de 1 minuto y 30 segundos" to Timer(90),
            "avísame en 10 minutos" to Timer(600),
            "pon un temporizador de un minuto y medio" to Timer(90),
            "pon un temporizador de un cuarto de hora" to Timer(900),
            "pon un temporizador de cuarenta y cinco segundos" to Timer(45),
            "temporizador de 2 horas" to Timer(7200),
            "pon un temporizador de 3 min" to Timer(180)
        )
    )

    @Test
    fun timerWithoutTimeIsChat() {
        assertEquals(Command.Chat("pon un temporizador"), p("pon un temporizador"))
    }

    @Test
    fun torch() = check(
        listOf(
            "prende la linterna" to Torch(true),
            "apaga la linterna" to Torch(false),
            "enciende el flash" to Torch(true),
            "¿puedes apagar la lámpara?" to Torch(false),
            "ábreme la linterna" to Torch(true),
            "linterna" to Torch(true)
        )
    )

    @Test
    fun volume() = check(
        listOf(
            "volumen al 50" to Volume(50),
            "pon el volumen al 80 por ciento" to Volume(80),
            "sube el volumen" to Volume(Volume.UP),
            "baja el volumen" to Volume(Volume.DOWN),
            "bájale al volumen" to Volume(Volume.DOWN),
            "súbele" to Volume(Volume.UP),
            "bájale tantito" to Volume(Volume.DOWN),
            "silencia el cel" to Volume(0),
            "pon el cel en silencio" to Volume(0),
            "volumen al máximo" to Volume(100),
            "volumen al 150" to Volume(100),
            "pon el volumen a la mitad" to Volume(50),
            "sube el volumen a 70" to Volume(70),
            "volumen al cincuenta" to Volume(50),
            "volumen" to Volume(null)
        )
    )

    @Test
    fun settings() = check(
        listOf(
            "abre el wifi" to Settings("wifi"),
            "prende el bluetooth" to Settings("bluetooth"),
            "activa los datos" to Settings("internet"),
            "pon el modo avión" to Settings("airplane"),
            "abre los ajustes" to Settings("settings"),
            "abre configuración de Wi-Fi" to Settings("wifi"),
            "Wi-Fi" to Settings("wifi"),
            "abre ajustes de sonido" to Settings("volume"),
            "sube el brillo" to Settings("display"),
            "abre la ubicación" to Settings("location"),
            "apaga el bluetooth" to Settings("bluetooth"),
            "ajustes" to Settings("settings")
        )
    )

    @Test
    fun timeAndBattery() = check(
        listOf(
            "qué hora es" to Time,
            "¿Qué horas son?" to Time,
            "dime la hora" to Time,
            "oye sapo, ¿qué hora es?" to Time,
            "cuánta pila tengo" to Battery,
            "¿cuánta batería me queda?" to Battery,
            "cómo ando de pila" to Battery,
            "batería" to Battery,
            "¿qué porcentaje de batería tengo?" to Battery
        )
    )

    @Test
    fun pc() = check(
        listOf(
            "en la compu abre spotify" to Pc("abre spotify"),
            "En la PC, pon música" to Pc("pon música"),
            "dile a la compu que apague la pantalla" to Pc("apague la pantalla"),
            "abre spotify en la compu" to Pc("abre spotify"),
            "oye sapo en mi computadora busca vuelos a Cancún" to Pc("busca vuelos a Cancún"),
            "en la compu dile a Ana que ya voy" to Pc("dile a Ana que ya voy")
        )
    )

    @Test
    fun everythingElseIsChat() {
        val chats = listOf(
            "qué onda",
            "¿qué onda?",
            "cuéntame un chiste",
            "a qué hora sale el sol",
            "estoy en la compu",
            "la llama es un animal",
            "¿cómo se llama la canción de la película?",
            "por favor",
            "dile que ya voy",
            "no tengo wifi en la casa",
            "  ",
            ""
        )
        for (c in chats) assertEquals(Command.Chat(c.trim()), p(c), "frase: \"$c\"")
    }

    @Test
    fun needsConfirmOnlyForPeople() {
        assertTrue(Intents.needsConfirm(Call("Mamá")))
        assertTrue(Intents.needsConfirm(Sms("Ana", "ya voy")))
        assertTrue(Intents.needsConfirm(WhatsApp("Luis", "")))
        val free = listOf(
            OpenApp("Spotify"), Alarm(7, 0, null), Timer(60), Torch(true), Volume(50), Volume(null),
            Settings("wifi"), Time, Battery, Pc("abre spotify"), Command.Chat("qué onda")
        )
        for (c in free) assertFalse(Intents.needsConfirm(c), c.toString())
    }

    @Test
    fun confirmTextReadable() {
        assertEquals("¿Le marco a Mamá?", Intents.confirmText(Call("Mamá")))
        assertEquals("¿Le mando un mensaje a Ana que diga “ya voy”?", Intents.confirmText(Sms("Ana", "ya voy")))
        assertEquals("¿Le mando un mensaje a Ana?", Intents.confirmText(Sms("Ana", "")))
        assertEquals("¿Le escribo por WhatsApp a Luis: “ya salí”?", Intents.confirmText(WhatsApp("Luis", "ya salí")))
        assertEquals("¿Le abro WhatsApp a Luis?", Intents.confirmText(WhatsApp("Luis", "")))
        assertEquals("¿Abro Spotify?", Intents.confirmText(OpenApp("Spotify")))
        assertEquals("¿Pongo una alarma a las 7:30 de la mañana?", Intents.confirmText(Alarm(7, 30, null)))
        assertEquals("¿Pongo una alarma a las 8:00 de la noche para el gym?", Intents.confirmText(Alarm(20, 0, "el gym")))
        assertEquals("¿Pongo una alarma a la 1:05 de la tarde?", Intents.confirmText(Alarm(13, 5, null)))
        assertEquals("¿Pongo una alarma a las 12:00 del mediodía?", Intents.confirmText(Alarm(12, 0, null)))
        assertEquals("¿Pongo una alarma a las 12:00 de la noche?", Intents.confirmText(Alarm(0, 0, null)))
        assertEquals("¿Pongo un temporizador de 5 minutos?", Intents.confirmText(Timer(300)))
        assertEquals("¿Pongo un temporizador de 1 minuto y 30 segundos?", Intents.confirmText(Timer(90)))
        assertEquals("¿Pongo un temporizador de 1 hora, 1 minuto y 1 segundo?", Intents.confirmText(Timer(3661)))
        assertEquals("¿Prendo la linterna?", Intents.confirmText(Torch(true)))
        assertEquals("¿Apago la linterna?", Intents.confirmText(Torch(false)))
        assertEquals("¿Pongo el volumen al 50%?", Intents.confirmText(Volume(50)))
        assertEquals("¿Subo el volumen?", Intents.confirmText(Volume(Volume.UP)))
        assertEquals("¿Bajo el volumen?", Intents.confirmText(Volume(Volume.DOWN)))
        assertEquals("¿Silencio el cel?", Intents.confirmText(Volume(0)))
        assertEquals("¿Abro los ajustes de Wi-Fi?", Intents.confirmText(Settings("wifi")))
        assertEquals("¿Abro los ajustes?", Intents.confirmText(Settings("settings")))
        assertEquals("¿Le paso a la PC “abre spotify”?", Intents.confirmText(Pc("abre spotify")))
    }

    @Test
    fun confirmFlowWithContacts() {
        val c = p("llama a mi mamá") as Call
        val who = Contacts.best(c.who, listOf("Juan Pérez", "Mamá", "Papá"))
        assertEquals("¿Le marco a Mamá?", Intents.confirmText(Call(who!!)))
    }

    @Test
    fun everyConfirmTextIsAQuestion() {
        val all = listOf(
            Call("Ana"), Sms("Ana", "x"), WhatsApp("Ana", "x"), OpenApp("Spotify"), Alarm(6, 0, null), Timer(5),
            Torch(true), Volume(null), Settings("nfc"), Settings("raro"), Time, Battery, Pc("x"), Command.Chat("hola")
        )
        for (c in all) {
            val t = Intents.confirmText(c)
            assertTrue(t.startsWith("¿") && t.endsWith("?"), t)
        }
    }

    @Test
    fun phoneControl() {
        check(
            listOf(
                "regresa" to Command.Screen(Command.Screen.BACK),
                "atrás" to Command.Screen(Command.Screen.BACK),
                "ve al inicio" to Command.Screen(Command.Screen.HOME),
                "sal de la app" to Command.Screen(Command.Screen.HOME),
                "apps recientes" to Command.Screen(Command.Screen.RECENTS),
                "abre las notificaciones" to Command.Screen(Command.Screen.NOTIFICATIONS),
                "ajustes rápidos" to Command.Screen(Command.Screen.QUICK),
                "toma captura de pantalla" to Command.Screen(Command.Screen.SCREENSHOT),
                "bloquea el cel" to Command.Screen(Command.Screen.LOCK),
                "desliza hacia abajo" to Command.Scroll(true),
                "más arriba" to Command.Scroll(false),
                "toca aceptar" to Command.Tap("aceptar"),
                "dale click a Siguiente" to Command.Tap("Siguiente"),
                "escribe hola qué onda" to Command.Type("hola qué onda"),
                "¿qué hay en la pantalla?" to Command.ReadScreen,
                "busca tacos al pastor en youtube" to Command.Agent("busca tacos al pastor en youtube"),
                "pon música de Bad Bunny en Spotify" to Command.Agent("pon música de Bad Bunny en Spotify"),
                "en el cel activa el modo oscuro" to Command.Agent("activa el modo oscuro"),
                "abre spotify" to OpenApp("spotify"),
                "baja el volumen" to Volume(Volume.DOWN),
                "escríbele a Ana que ya voy" to Sms("Ana", "ya voy")
            )
        )
    }

    @Test
    fun groupsAndMentions() {
        assertEquals("Primos", Guard.groupName("Primos: Luis", null))
        assertEquals("Primos", Guard.groupName("Luis", "Primos (3 mensajes)"))
        assertEquals("Luis", Guard.sender("Primos: Luis", null))
        assertEquals("Luis", Guard.sender("Luis", "Primos"))
        assertTrue(Guard.mentions("@Yokis ya llegaste?", listOf("Yokis Pérez")))
        assertTrue(Guard.mentions("oye yokis pásame la tarea", listOf("Yokis")))
        assertFalse(Guard.mentions("ya llegó el pastel", listOf("Yokis")))
        val p = Prompt.reply("¿vienes?", "Primos", emptyList(), StyleProfile(0.0, 0.0, emptyList(), 0.0, null, emptyList(), 0.0, 0), emptyList(), auto = false, group = "Primos", sender = "Luis")
        assertTrue(p.contains("grupo de WhatsApp «Primos»") && p.contains("MENSAJE NUEVO DE Luis EN EL GRUPO"))
    }
}
