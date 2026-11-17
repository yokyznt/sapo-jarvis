package io.github.yokyznt.sapo.core

import java.text.Normalizer
import java.time.LocalDateTime

object Intents {
    private const val EDGE = "¿¡?!.,;:…\"'“”«» "
    private const val QUOTES = "\"'“”«»,;:"
    private const val WA = "(?:whatsapp|whatsap|watsap|watsapp|wasap|wassap|guasap|guatsap|wats|whats|wasa|wa)"
    private const val CHAN = "(?:$WA|sms|mensaje|mensajito|msj|texto|recado)"
    private const val MSG_VERB =
        "(?:mandale|mandales|mandarle|manda|mandar|enviale|enviales|enviarle|envia|enviar|escribele|escribeles|escribirle|escribe|escribir|dile|diles|decirle|avisale|avisales|avisarle)"
    private const val NOUN = "(?:una? )?(?:mensaje(?: de texto)?|mensajito|msj|sms|texto|recado|$WA)"
    private const val VIA = "(?:por|en|via|de|al) $CHAN"
    private const val PC = "(?:pc|compu|computadora|ordenador|laptop|lap|maquina)"
    private const val H = "(\\d{1,2}|una|uno)"
    private const val TAIL =
        """(?::(\d{2})|\s+y\s+(media|cuarto|\d{1,2})|\s+menos\s+(cuarto|\d{1,2}))?(?:\s+en punto)?(?:\s+(am|pm|de la manana|de la tarde|de la noche|de la madrugada|en la manana|en la tarde|en la noche|en la madrugada|por la manana|por la tarde|por la noche|del mediodia|de mediodia|hrs|horas|hr)\b)?"""
    private const val TORCH = "(?:linterna|lampara|lamparita|flash)"
    private const val VOL = "(?:volumen|sonido|volume)"
    private const val LITTLE = "(?: (?:mas|un poco|tantito|poquito|un poquito|un tantito|otro poco))?"

    private val spaces = Regex("\\s+")
    private val lead = Regex(
        "^(?:(?:oye|oiga|oigan|hey|ey|okay|ok|sapo|sapito|porfa|porfis|por favor|plis|please|me puedes|me podrias|puedes|podrias|pudieras)(?:[ ,]+|$))+"
    )
    private val trail = Regex("(?:[ ,]+(?:porfa|porfis|por favor|plis|please|gracias|sapo|sapito))+$")

    private val pcHead = Regex(
        "^(?:(?:en|desde|con|por) (?:la|mi|el) $PC|(?:dile|pidele) a (?:la|mi) $PC(?: que)?|(?:pc|compu))[ ,:]+(.+)$"
    )
    private val pcTail = Regex(
        "^((?:abre|abreme|cierra|cierrame|pon|ponme|busca|buscame|reproduce|apaga|prende|sube|subele|baja|bajale|inicia|lanza|ejecuta|escribe|toca|quita|minimiza|maximiza|cambia|silencia|bloquea|suspende|reinicia|haz|hazme|muestrame|manda|descarga|guarda|cerrar|abrir|poner)\\b.*?)[ ,]+(?:en|desde) (?:la|mi|el) $PC$"
    )

    private val msgFull = Regex(
        "^$MSG_VERB(?: $NOUN)?(?: $VIA)?(?: (?:a|al|para|pa))? (.+?)(?: $VIA)?(?:[,:]? (?:que|diciendole que|diciendo que|diciendole|diciendo)|\\s*[:,]) (.+)$"
    )
    private val msgBare = Regex("^$MSG_VERB $NOUN(?: $VIA)? (?:a|al|para|pa) (.+?)(?: $VIA)?$")
    private val waWord = Regex("\\b$WA\\b")
    private val viaTail = Regex("[ ,]+(?:por|en|via) $WA$")
    private val nounWho = Regex("^(?:una? )?$CHAN\\b")

    private val callRe = Regex(
        "^(?:llamale|llamarle|llama|llamar|marcale|marcarle|marca|marcar|hablale|hablarle|habla(?= a )|hablar(?= a )|telefoneale|telefonea|comunicame con|conectame con|hazle una llamada|haz una llamada|hacer una llamada|echale un fon|echale una llamada|dale un toque)(?: por (?:telefono|cel|celular))?(?: (?:a|al|con|para))? (.+?)(?: (?:por telefono|al cel|al celular|a su cel|a su celular|ahorita|ahora|ya|rapido|de volada))*$"
    )

    private val timerWord = Regex(
        "\\b(?:temporizador|timer|cronometro|cuenta regresiva|cuenta atras)\\b|^(?:avisame|recuerdame|recuerdamelo) (?:en|dentro de)\\b"
    )
    private val durRe = Regex(
        """\b(\d{1,5}|una?|uno|medio|media)\s+(horas?|hrs?|minutos?|mins?|segundos?|segs?)\b(?:\s+y\s+(medio|media|cuarto))?"""
    )
    private val quarterRe = Regex("""\b(\d{1,3}|una?)\s+cuartos?\s+de\s+hora\b""")

    private val alarmWord = Regex("\\b(?:alarma|alarmita|despiertame|despiertenme|despertame|levantame|despertador)\\b")
    private val alarmNo = Regex(
        "^(?:quita|quitame|apaga|apagame|cancela|cancelame|borra|borrame|elimina|desactiva|deten|cuando|a que hora|que hora|cual|cuales|tengo)\\b"
    )
    private val relRe = Regex("""\b(?:en|dentro de)\s+(?:\d|una?\b|uno\b|medio\b|media\b)""")
    private val timeAt = Regex("""\b(?:a|para|como a|tipo|desde)\s+las?\s+$H\b$TAIL""")
    private val timeBare = Regex("""\b(\d{1,2})\b$TAIL""")
    private val noon = Regex("\\bmediodia\\b")
    private val midnight = Regex("\\bmedianoche\\b")
    private const val NUMW = "(?:\\d|una\\b|uno\\b|dos\\b|tres\\b|cuatro\\b|cinco\\b|seis\\b|siete\\b|ocho\\b|nueve\\b|diez\\b|once\\b|doce\\b)"
    private val labelRe = Regex(
        """\b(?:que diga|con (?:el )?(?:nombre|titulo|etiqueta)(?: de)?|para(?!\s+(?:las?\s+$NUMW|hoy\b|manana\b|mediodia\b|medianoche\b|dentro\b|en\s+(?:\d|una?\b|media\b|medio\b)|\d)))\s+(.+?)(?=\s+(?:a|para|como a) las?\s+$NUMW|\s+(?:a|al|para el|para) (?:mediodia|medianoche)\b|\s+(?:en|dentro de) (?:\d|una?\b|media\b|medio\b)|$)"""
    )

    private val torchOn = Regex(
        "^(?:prende|prendeme|prender|enciende|enciendeme|encender|activa|activame|activar|pon|ponme|poner|abre|abreme|abrir)\\b.*\\b$TORCH\\b"
    )
    private val torchOff = Regex(
        "^(?:apaga|apagame|apagar|desactiva|desactivame|desactivar|quita|quitame|quitar|cierra|cerrar)\\b.*\\b$TORCH\\b"
    )
    private val torchBare = Regex("^(?:la )?(?:linterna|lamparita)$")

    private val volMute = Regex(
        "^(?:silencia|silenciar|mutea|mutear)\\b|\\b(?:en|modo) silencio(?:so)?\\b|^(?:quita|quitale|apaga)\\s+(?:el\\s+)?(?:sonido|volumen)\\b|^(?:sin sonido|mute)$"
    )
    private val volMax = Regex("\\b$VOL\\b.*\\b(?:al maximo|a tope|a todo|full|hasta arriba)\\b|^(?:sube|subele|pon|ponle)\\b.*\\b(?:al maximo|a tope|a todo)\\b")
    private val volMin = Regex("\\b$VOL\\b.*\\b(?:al minimo|hasta abajo)\\b")
    private val volHalf = Regex("\\b$VOL\\b.*\\b(?:a la mitad|al medio)\\b")
    private val volAbs = Regex("""\b$VOL\b.*?\b(?:al|a|en)\s+(\d{1,3})\b""")
    private val volAbs2 = Regex(
        """^(?:pon|ponme|ponle|poner|deja|dejame|sube|subele|baja|bajale)\b.*?\b(?:al|a|en)\s+(\d{1,3})\b.*\b$VOL\b"""
    )
    private val volUp = Regex(
        "^(?:sube|subele|subir|aumenta|aumentale|aumentar|mas)\\b.*\\b$VOL\\b|^(?:subele|sube)$LITTLE$|^mas (?:fuerte|alto|recio)$"
    )
    private val volDown = Regex(
        "^(?:baja|bajale|bajar|disminuye|disminuir|reduce|reducir|menos)\\b.*\\b$VOL\\b|^(?:bajale|baja)$LITTLE$|^mas (?:bajo|bajito|quedito)$"
    )
    private val volPanel = Regex("^(?:(?:abre|abreme|muestrame|ajusta|ajustar|cambia|cambiar)\\s+)?(?:el\\s+)?$VOL$")

    private val batWord = Regex("\\b(?:pila|bateria)\\b|\\bcuanta carga\\b")
    private val batAsk = Regex(
        "\\b(?:cuant[ao]s?|que tant[ao]|como (?:esta|va|ando|voy|anda|vamos|estoy|estamos)|nivel|porcentaje|me queda|queda|tengo|traigo|tiene|hay|dime)\\b"
    )
    private val batBare = Regex("^(?:(?:la|mi) )?(?:pila|bateria)$")

    private val timeAsk = Regex(
        "^(?:(?:me (?:dices|das|puedes decir|podrias decir)|dime|sabes) )?(?:que|q|ke) horas? (?:es|son|tienes|traes|seran|sera|marca)(?: (?:ahorita|ahora|ya))?$|^(?:dime|me dices|me das|sabes|dame) (?:la|que) hora(?: es)?(?: (?:ahorita|ahora))?$|^(?:la )?hora$"
    )

    private val panels = listOf(
        "wifi" to "(?:wi ?-?fi|guaifai|wai ?fai)",
        "bluetooth" to "(?:bluetooth|blutu|blututh|bluetut)",
        "airplane" to "(?:modo avion)",
        "internet" to "(?:datos(?: moviles)?|internet|red movil)",
        "nfc" to "(?:nfc)",
        "location" to "(?:ubicacion|gps|localizacion)",
        "display" to "(?:brillo|pantalla)",
        "volume" to "(?:sonido|volumen|tonos?|timbre)",
        "settings" to "(?:ajustes|configuracion|configuraciones|config)"
    ).map { (k, v) -> Triple(k, Regex("\\b$v\\b"), Regex("^$v$")) }
    private val setVerb = Regex(
        "^(?:abre|abreme|abrir|prende|prendeme|prender|enciende|encender|activa|activame|activar|apaga|apagame|apagar|desactiva|desactivar|pon|ponme|poner|quita|quitame|quitar|conecta|conectate|conectame|conectar|desconecta|desconectate|desconectar|ve a|vete a|entra a|muestrame|configura|ajusta|cambia|sube|subele|baja|bajale)\\b"
    )
    private val setBare = Regex("^(?:(?:los |las |la |el )?(?:ajustes|configuracion)(?: (?:de|del))? )?(?:el |la |los )?(.+)$")

    private val openRe = Regex(
        """^(?:abre|abreme|abrir|inicia|iniciar|lanza|ejecuta|arranca|entra a|entra en|entrar a|metete a|ve a|vete a|muestrame)\s+(?:(?:la\s+)?(?:app|aplicacion)\s+(?:de\s+|del\s+)?)?(?:el\s+|la\s+|los\s+|las\s+|mis\s+|mi\s+)?(.+)$"""
    )

    private val backRe = Regex("^(?:regresa|regresate|regresar|atras|ve atras|ve para atras|ve pa atras|vuelve|vuelve atras|para atras|pa atras|retrocede)$")
    private val homeRe = Regex("^(?:(?:ve|vete|ir|regresa|vuelve|llevame) (?:a la |al |a )?(?:pantalla de )?(?:inicio|home|escritorio)|pantalla de inicio|inicio|home|salte|sal de (?:la|esta) app|cierra (?:la|esta) app|minimiza (?:todo|la app|esto))$")
    private val recentsRe = Regex("^(?:(?:abre|muestrame|ensename) )?(?:las )?(?:apps|aplicaciones)? ?(?:recientes|abiertas)$|^multitarea$|^cambia de app$")
    private val notifRe = Regex("^(?:(?:abre|abreme|baja|bajame|muestrame|ensename|ver|checa) )?(?:las |mis )?notificaciones$")
    private val quickRe = Regex("^(?:(?:abre|abreme|baja|muestrame) )?(?:los |el )?(?:ajustes|accesos|controles|panel) rapidos?$")
    private val shotRe = Regex("^(?:(?:toma|tomale|saca|sacale|haz|hazme|tomame|sacame) )?(?:una |un )?(?:captura(?: de pantalla)?|screenshot|pantallazo|screen)(?: a (?:la|esta) pantalla)?$")
    private val lockRe = Regex("^(?:bloquea|bloqueame|apaga|apagame) (?:el |la |mi )?(?:cel|celular|telefono|pantalla)$|^bloquealo$")
    private val scrollDown = Regex("^(?:desliza|deslizale|scrollea|scroll|baja la pantalla|bajale a la pantalla|sigue bajando|mas abajo|ve mas abajo)(?: (?:hacia|para|pa) abajo| abajo)?$")
    private val scrollUp = Regex("^(?:(?:desliza|deslizale|scrollea|scroll)(?: (?:hacia|para|pa))? arriba|sube la pantalla|subele a la pantalla|mas arriba|ve mas arriba)$")
    private val tapRe = Regex("^(?:toca|tocale|tocame|picale|pica|presiona|presionale|aprieta|aprietale|selecciona|dale (?:click|clic|clik) a|dale (?:click|clic|clik) en|dale click|dale a|da (?:click|clic) en)\\s+(?:en\\s+|a\\s+)?(?:el\\s+|la\\s+|los\\s+|las\\s+|donde dice\\s+)?(.+)$")
    private val typeRe = Regex("^(?:escribe|teclea|tecleame|pon el texto|redacta)\\s+(?!(?:a|al|le|les|un|una|unos|mensaje|mensajito|sms|whatsapp|wasap|texto|recado|por|en)\\b)(.+)$")
    private val readRe = Regex("^(?:que (?:hay|dice|sale|tengo|ves) en (?:la |mi |esta )?pantalla|que (?:dice|sale) (?:aqui|aca|ahi|esto)|leeme (?:la pantalla|esto|lo que dice|lo que sale)|lee (?:la pantalla|esto)|describe (?:la|mi) pantalla|que ves)$")
    private val agentHead = Regex("^(?:en (?:el|mi) (?:cel|celular|telefono)|en el cel|hazme|haz que|ayudame a|puedes)\\s+(.+)$")
    private val agentVerb = Regex("^(?:busca|buscame|buscar|reproduce|reproduceme|ponme|pon|activa|activame|desactiva|prende|apaga|cambia|sigue a|publica|comparte|descarga|descargame|instala|guarda|marca|responde|contesta|dale like|likea|silencia|archiva|agrega|anade|crea|programa|pide|ordena|ve a|entra a|entra en|metete a)\\b.+\\b(?:en|de|del|con)\\s+(?:el |la |mi )?[a-z0-9]+.*$")

    private val ampm = Regex("""(\d)\s*([ap])\.?\s?m\.?(?=\s|$)""")
    private val dotTime = Regex("""\b(\d{1,2})\.(\d{2})\b""")
    private val punct = Regex("[¿¡?!,;\"“”]")

    private val small = mapOf(
        "cero" to 0, "dos" to 2, "tres" to 3, "cuatro" to 4, "cinco" to 5, "seis" to 6, "siete" to 7, "ocho" to 8,
        "nueve" to 9, "diez" to 10, "once" to 11, "doce" to 12, "trece" to 13, "catorce" to 14, "quince" to 15,
        "dieciseis" to 16, "diecisiete" to 17, "dieciocho" to 18, "diecinueve" to 19, "veinte" to 20,
        "veintiuno" to 21, "veintiun" to 21, "veintiuna" to 21, "veintidos" to 22, "veintitres" to 23,
        "veinticuatro" to 24, "veinticinco" to 25, "veintiseis" to 26, "veintisiete" to 27, "veintiocho" to 28,
        "veintinueve" to 29, "cien" to 100
    )
    private val tens = mapOf(
        "treinta" to 30, "cuarenta" to 40, "cincuenta" to 50, "sesenta" to 60, "setenta" to 70, "ochenta" to 80,
        "noventa" to 90
    )
    private val ones = mapOf(
        "un" to 1, "uno" to 1, "una" to 1, "dos" to 2, "tres" to 3, "cuatro" to 4, "cinco" to 5, "seis" to 6,
        "siete" to 7, "ocho" to 8, "nueve" to 9
    )

    private val panelNames = mapOf(
        "wifi" to "Wi-Fi", "bluetooth" to "Bluetooth", "internet" to "datos", "nfc" to "NFC",
        "airplane" to "modo avión", "location" to "ubicación", "display" to "pantalla", "volume" to "sonido"
    )

    fun parse(text: String, now: LocalDateTime): Command {
        val raw = text.trim()
        val s = core(raw)
        if (s.isEmpty()) return Command.Chat(raw)
        val f = fold(s)
        val n = numeric(f)
        pcHead.find(f)?.let { m -> cut(s, m.groups[1]!!.range).takeIf { it.isNotEmpty() }?.let { return Command.Pc(it) } }
        typeRe.find(f)?.let { m -> cut(s, m.groups[1]!!.range).trim { it.isWhitespace() || it in QUOTES }.takeIf { it.isNotEmpty() }?.let { return Command.Type(it) } }
        message(s, f)?.let { return it }
        callRe.find(f)?.let { m -> cut(s, m.groups[1]!!.range).takeIf { it.isNotEmpty() }?.let { return Command.Call(it) } }
        pcTail.find(f)?.let { m -> return Command.Pc(cut(s, m.groups[1]!!.range)) }
        screen(s, f)?.let { return it }
        if (timerWord.containsMatchIn(f)) {
            val secs = duration(n)
            return if (secs > 0) Command.Timer(secs) else Command.Chat(raw)
        }
        if (alarmWord.containsMatchIn(f) && !alarmNo.containsMatchIn(f)) return alarm(s, f, n, now) ?: Command.Chat(raw)
        torch(f)?.let { return it }
        volume(f, n)?.let { return it }
        if ((batWord.containsMatchIn(f) && batAsk.containsMatchIn(f)) || batBare.matches(f)) return Command.Battery
        if (timeAsk.matches(f)) return Command.Time
        settings(f)?.let { return it }
        if (agentVerb.matches(f)) return Command.Agent(s)
        openRe.find(f)?.let { m -> cut(s, m.groups[1]!!.range).takeIf { it.isNotEmpty() }?.let { return Command.OpenApp(it) } }
        return Command.Chat(raw)
    }

    private fun screen(s: String, f: String): Command? {
        agentHead.find(f)?.let { m -> cut(s, m.groups[1]!!.range).takeIf { it.isNotEmpty() }?.let { return Command.Agent(it) } }
        if (backRe.matches(f)) return Command.Screen(Command.Screen.BACK)
        if (homeRe.matches(f)) return Command.Screen(Command.Screen.HOME)
        if (recentsRe.matches(f)) return Command.Screen(Command.Screen.RECENTS)
        if (notifRe.matches(f)) return Command.Screen(Command.Screen.NOTIFICATIONS)
        if (quickRe.matches(f)) return Command.Screen(Command.Screen.QUICK)
        if (shotRe.matches(f)) return Command.Screen(Command.Screen.SCREENSHOT)
        if (lockRe.matches(f)) return Command.Screen(Command.Screen.LOCK)
        if (scrollUp.matches(f)) return Command.Scroll(false)
        if (scrollDown.matches(f)) return Command.Scroll(true)
        if (readRe.matches(f)) return Command.ReadScreen
        tapRe.find(f)?.let { m -> cut(s, m.groups[1]!!.range).trim { it in EDGE }.takeIf { it.isNotEmpty() }?.let { return Command.Tap(it) } }
        typeRe.find(f)?.let { m -> cut(s, m.groups[1]!!.range).trim { it.isWhitespace() || it in QUOTES }.takeIf { it.isNotEmpty() }?.let { return Command.Type(it) } }
        return null
    }

    fun needsConfirm(c: Command): Boolean = c is Command.Call || c is Command.Sms || c is Command.WhatsApp

    fun confirmText(c: Command): String = when (c) {
        is Command.Call -> "¿Le marco a ${c.who}?"
        is Command.Sms -> if (c.text.isEmpty()) "¿Le mando un mensaje a ${c.who}?" else "¿Le mando un mensaje a ${c.who} que diga “${c.text}”?"
        is Command.WhatsApp -> if (c.text.isEmpty()) "¿Le abro WhatsApp a ${c.who}?" else "¿Le escribo por WhatsApp a ${c.who}: “${c.text}”?"
        is Command.OpenApp -> "¿Abro ${c.name}?"
        is Command.Alarm -> "¿Pongo una alarma a ${clockText(c.hour, c.minute)}${c.label?.let { " para $it" } ?: ""}?"
        is Command.Timer -> "¿Pongo un temporizador de ${durationText(c.seconds)}?"
        is Command.Torch -> if (c.on) "¿Prendo la linterna?" else "¿Apago la linterna?"
        is Command.Volume -> when (c.level) {
            null -> "¿Abro el control de volumen?"
            Command.Volume.UP -> "¿Subo el volumen?"
            Command.Volume.DOWN -> "¿Bajo el volumen?"
            0 -> "¿Silencio el cel?"
            else -> "¿Pongo el volumen al ${c.level}%?"
        }
        is Command.Settings -> panelNames[c.panel]?.let { "¿Abro los ajustes de $it?" }
            ?: if (c.panel == "settings") "¿Abro los ajustes?" else "¿Abro los ajustes de ${c.panel}?"
        Command.Time -> "¿Te digo la hora?"
        Command.Battery -> "¿Te digo cuánta pila te queda?"
        is Command.Pc -> "¿Le paso a la PC “${c.text}”?"
        is Command.Chat -> "¿Te contesto “${c.text}”?"
        is Command.Screen -> when (c.action) {
            Command.Screen.BACK -> "¿Me regreso?"
            Command.Screen.HOME -> "¿Te llevo al inicio?"
            Command.Screen.RECENTS -> "¿Te enseño las apps recientes?"
            Command.Screen.NOTIFICATIONS -> "¿Te bajo las notificaciones?"
            Command.Screen.QUICK -> "¿Te abro los ajustes rápidos?"
            Command.Screen.SCREENSHOT -> "¿Tomo captura de pantalla?"
            else -> "¿Bloqueo el cel?"
        }
        is Command.Tap -> "¿Toco “${c.target}”?"
        is Command.Scroll -> if (c.down) "¿Bajo la pantalla?" else "¿Subo la pantalla?"
        is Command.Type -> "¿Escribo “${c.text}”?"
        Command.ReadScreen -> "¿Te digo qué hay en la pantalla?"
        is Command.Agent -> "¿Hago esto en tu cel: “${c.goal}”?"
    }

    private fun message(s: String, f: String): Command? {
        msgFull.find(f)?.let { m ->
            val whoRange = m.groups[1]!!.range
            var textRange = m.groups[2]!!.range
            val who = cleanWho(s, f, whoRange) ?: return@let
            var wa = waWord.containsMatchIn(f.substring(0, textRange.first))
            viaTail.find(f.substring(textRange.first, textRange.last + 1))?.let { t ->
                wa = true
                textRange = textRange.first until textRange.first + t.range.first
            }
            val body = balance(s.substring(textRange.first, textRange.last + 1).trim { it.isWhitespace() || it in QUOTES })
            if (body.isEmpty()) return@let
            return if (wa) Command.WhatsApp(who, body) else Command.Sms(who, body)
        }
        msgBare.find(f)?.let { m ->
            val who = cleanWho(s, f, m.groups[1]!!.range) ?: return null
            return if (waWord.containsMatchIn(f)) Command.WhatsApp(who, "") else Command.Sms(who, "")
        }
        return null
    }

    private fun cleanWho(s: String, f: String, r: IntRange): String? {
        val who = cut(s, r)
        if (who.isEmpty() || nounWho.containsMatchIn(f.substring(r.first, r.last + 1))) return null
        return who
    }

    private fun alarm(s: String, f: String, n: String, now: LocalDateTime): Command? {
        val label = labelRe.find(f)?.let { cut(s, it.groups[1]!!.range) }?.takeIf { it.isNotEmpty() }
        relRe.find(n)?.let { m ->
            val secs = duration(n.substring(m.range.first))
            if (secs > 0) {
                val t = now.plusSeconds(secs.toLong())
                return Command.Alarm(t.hour, t.minute, label)
            }
        }
        val hm = timeAt.find(n)?.let { clock(it) }
            ?: if (noon.containsMatchIn(n)) 12 to 0 else null
            ?: if (midnight.containsMatchIn(n)) 0 to 0 else null
            ?: timeBare.find(n)?.let { clock(it) }
            ?: return null
        return Command.Alarm(hm.first, hm.second, label)
    }

    private fun clock(m: MatchResult): kotlin.Pair<Int, Int>? {
        var h = num(m.groupValues[1]) ?: return null
        val colon = m.groupValues[2]
        val plus = m.groupValues[3]
        val minus = m.groupValues[4]
        val period = m.groupValues[5]
        if (h > 23) return null
        h = when (period) {
            "am", "de la manana", "en la manana", "por la manana", "de la madrugada", "en la madrugada" ->
                if (h > 12) return null else if (h == 12) 0 else h
            "pm", "de la tarde", "en la tarde", "por la tarde" -> if (h in 1..11) h + 12 else h
            "de la noche", "en la noche", "por la noche" -> when (h) {
                12 -> 0
                in 5..11 -> h + 12
                else -> h
            }
            "del mediodia", "de mediodia" -> if (h in 1..5) h + 12 else h
            else -> h
        }
        var min = when {
            colon.isNotEmpty() -> colon.toInt()
            plus == "media" -> 30
            plus == "cuarto" -> 15
            plus.isNotEmpty() -> plus.toInt()
            else -> 0
        }
        if (minus.isNotEmpty()) {
            val back = if (minus == "cuarto") 15 else minus.toInt()
            if (back !in 1..59) return null
            min = 60 - back
            h = (h + 23) % 24
        }
        if (min !in 0..59) return null
        return h to min
    }

    private fun duration(n: String): Int {
        var total = 0.0
        for (m in durRe.findAll(n)) {
            val unit = when (m.groupValues[2].trimEnd('s').removeSuffix("r")) {
                "hora", "h" -> 3600.0
                "minuto", "min" -> 60.0
                else -> 1.0
            }
            val q = when (val v = m.groupValues[1]) {
                "un", "una", "uno" -> 1.0
                "medio", "media" -> 0.5
                else -> v.toDouble()
            }
            val extra = when (m.groupValues[3]) {
                "medio", "media" -> 0.5
                "cuarto" -> 0.25
                else -> 0.0
            }
            total += (q + extra) * unit
        }
        for (m in quarterRe.findAll(n)) total += (num(m.groupValues[1]) ?: 1) * 900.0
        return total.toInt().coerceAtMost(86_400 * 7)
    }

    private fun torch(f: String): Command? {
        val off = torchOff.find(f)
        val on = torchOn.find(f)
        return when {
            off != null -> Command.Torch(false)
            on != null || torchBare.matches(f) -> Command.Torch(true)
            else -> null
        }
    }

    private fun volume(f: String, n: String): Command? = when {
        volMute.containsMatchIn(f) -> Command.Volume(0)
        volMax.containsMatchIn(f) -> Command.Volume(100)
        volMin.containsMatchIn(f) -> Command.Volume(0)
        volHalf.containsMatchIn(f) -> Command.Volume(50)
        else -> (volAbs.find(n) ?: volAbs2.find(n))?.let { Command.Volume(it.groupValues[1].toInt().coerceIn(0, 100)) }
            ?: when {
                volUp.containsMatchIn(f) -> Command.Volume(Command.Volume.UP)
                volDown.containsMatchIn(f) -> Command.Volume(Command.Volume.DOWN)
                volPanel.matches(f) -> Command.Volume(null)
                else -> null
            }
    }

    private fun settings(f: String): Command? {
        if (setVerb.containsMatchIn(f)) {
            val rest = f.substring(setVerb.find(f)!!.range.last + 1)
            panels.firstOrNull { it.second.containsMatchIn(rest) }?.let { return Command.Settings(it.first) }
        }
        val bare = setBare.find(f)?.groupValues?.get(1) ?: return null
        if (bare.isEmpty()) return null
        panels.firstOrNull { it.third.matches(bare) }?.let { return Command.Settings(it.first) }
        if (f == "ajustes" || f == "configuracion" || f == "los ajustes" || f == "la configuracion") return Command.Settings("settings")
        return null
    }

    private fun core(raw: String): String {
        var s = trimEdges(spaces.replace(raw, " "))
        while (s.isNotEmpty()) {
            val f = fold(s)
            val a = lead.find(f)?.let { it.range.last + 1 } ?: 0
            val b = trail.find(f)?.range?.first ?: f.length
            if (a == 0 && b == f.length) return s
            if (a >= b) return ""
            s = trimEdges(s.substring(a, b))
        }
        return s
    }

    private fun fold(s: String): String {
        val b = StringBuilder(s.length)
        for (c in s) {
            val d = Normalizer.normalize(c.toString(), Normalizer.Form.NFD).firstOrNull() ?: c
            b.append(d.lowercaseChar())
        }
        return b.toString()
    }

    private fun numeric(f: String): String {
        var t = punct.replace(f, " ")
        t = ampm.replace(t, "$1 $2m")
        t = dotTime.replace(t, "$1:$2")
        val words = spaces.split(t.trim()).filter { it.isNotEmpty() }
        val out = ArrayList<String>(words.size)
        var i = 0
        while (i < words.size) {
            val w = words[i]
            val ten = tens[w]
            if (ten != null) {
                val unit = if (i + 2 < words.size && words[i + 1] == "y") ones[words[i + 2]] else null
                if (unit != null) {
                    out.add((ten + unit).toString())
                    i += 3
                } else {
                    out.add(ten.toString())
                    i++
                }
                continue
            }
            out.add(small[w]?.toString() ?: w)
            i++
        }
        return out.joinToString(" ")
    }

    private fun num(v: String): Int? = v.toIntOrNull() ?: if (v == "un" || v == "una" || v == "uno") 1 else null

    private fun cut(s: String, r: IntRange): String =
        if (r.isEmpty()) "" else trimEdges(s.substring(r.first, r.last + 1))

    private fun trimEdges(s: String): String = s.trim { it in EDGE || it.isWhitespace() }

    private fun balance(t: String): String = when {
        t.contains('¿') && !t.endsWith("?") -> "$t?"
        t.contains('¡') && !t.endsWith("!") -> "$t!"
        else -> t
    }

    private fun clockText(h: Int, m: Int): String {
        val h12 = when {
            h == 0 -> 12
            h > 12 -> h - 12
            else -> h
        }
        val part = when (h) {
            0 -> "de la noche"
            in 1..5 -> "de la madrugada"
            in 6..11 -> "de la mañana"
            12 -> "del mediodía"
            in 13..19 -> "de la tarde"
            else -> "de la noche"
        }
        val art = if (h12 == 1) "la" else "las"
        return "$art $h12:${m.toString().padStart(2, '0')} $part"
    }

    private fun durationText(total: Int): String {
        val parts = ArrayList<String>()
        val h = total / 3600
        val m = total % 3600 / 60
        val sec = total % 60
        if (h > 0) parts.add(if (h == 1) "1 hora" else "$h horas")
        if (m > 0) parts.add(if (m == 1) "1 minuto" else "$m minutos")
        if (sec > 0 || parts.isEmpty()) parts.add(if (sec == 1) "1 segundo" else "$sec segundos")
        return if (parts.size == 1) parts[0] else parts.dropLast(1).joinToString(", ") + " y " + parts.last()
    }
}
