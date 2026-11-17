package io.github.yokyznt.sapo.flotante

import android.content.Context
import android.content.Intent
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraManager
import android.media.AudioManager
import android.net.Uri
import android.os.BatteryManager
import android.os.Build
import android.provider.AlarmClock
import android.provider.ContactsContract.CommonDataKinds.Phone
import android.provider.Settings
import android.telephony.SmsManager
import io.github.yokyznt.sapo.Enlace
import io.github.yokyznt.sapo.Gemini
import io.github.yokyznt.sapo.Llave
import io.github.yokyznt.sapo.Store
import io.github.yokyznt.sapo.core.Command
import io.github.yokyznt.sapo.core.Contacts
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.URLEncoder
import java.text.Normalizer
import java.time.LocalTime
import kotlin.math.roundToInt

data class Contacto(val nombre: String, val numero: String)

class Ejecutor(private val ctx: Context) {

    fun contacto(quien: String): Contacto? {
        val filas = LinkedHashMap<String, MutableList<Triple<String, Int, Boolean>>>()
        ctx.contentResolver.query(
            Phone.CONTENT_URI,
            arrayOf(Phone.DISPLAY_NAME, Phone.NUMBER, Phone.TYPE, Phone.IS_SUPER_PRIMARY),
            null,
            null,
            null
        )?.use { c ->
            while (c.moveToNext()) {
                val nombre = c.getString(0)?.trim()?.ifBlank { null } ?: continue
                val numero = c.getString(1)?.trim()?.ifBlank { null } ?: continue
                filas.getOrPut(nombre) { mutableListOf() }.add(Triple(numero, c.getInt(2), c.getInt(3) == 1))
            }
        }
        val nombre = Contacts.best(quien, filas.keys.toList()) ?: return null
        val numeros = filas[nombre] ?: return null
        val mejor = numeros.firstOrNull { it.third } ?: numeros.firstOrNull { it.second == Phone.TYPE_MOBILE } ?: numeros.first()
        return Contacto(nombre, mejor.first)
    }

    fun llamar(k: Contacto): String = abrir(
        Intent(Intent.ACTION_CALL, Uri.fromParts("tel", k.numero, null)),
        "Llamando a ${k.nombre} 📞",
        "No pude marcarle a ${k.nombre} 😕"
    )

    fun sms(k: Contacto, texto: String): String = if (texto.isBlank()) abrir(
        Intent(Intent.ACTION_SENDTO, Uri.fromParts("smsto", k.numero, null)),
        "Te abrí los mensajes con ${k.nombre} ✉️",
        "No encontré la app de mensajes 😕"
    ) else runCatching {
        val sm = (if (Build.VERSION.SDK_INT >= 31) ctx.getSystemService(SmsManager::class.java) else null)
            ?: @Suppress("DEPRECATION") SmsManager.getDefault()
        val partes = sm.divideMessage(texto)
        if (partes.size > 1) sm.sendMultipartTextMessage(k.numero, null, partes, null, null)
        else sm.sendTextMessage(k.numero, null, texto, null, null)
        "Listo, le mandé el mensaje a ${k.nombre} ✉️"
    }.getOrElse { "No pude mandar el mensaje 😕 ${it.message.orEmpty()}".trim() }

    fun whatsapp(k: Contacto, texto: String): String {
        val numero = numeroWa(k.numero) ?: return "El número de ${k.nombre} no me cuadra para WhatsApp 🤔"
        val url = "https://wa.me/$numero" + if (texto.isBlank()) "" else "?text=" + URLEncoder.encode(texto, "UTF-8").replace("+", "%20")
        val base = Intent(Intent.ACTION_VIEW, Uri.parse(url))
        for (paquete in listOf("com.whatsapp", "com.whatsapp.w4b", null)) {
            val i = Intent(base).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            if (paquete != null) i.setPackage(paquete)
            if (runCatching { ctx.startActivity(i) }.isSuccess) return "Te dejé el mensaje listo para ${k.nombre}; tú le das enviar 💬"
        }
        return "No encontré WhatsApp 😕"
    }

    fun numeroWa(crudo: String): String? {
        val mas = crudo.trim().startsWith("+")
        var d = crudo.filter { it.isDigit() }
        if (d.startsWith("00")) d = d.drop(2)
        if (!mas && (d.startsWith("044") || d.startsWith("045")) && d.length == 13) d = d.drop(3)
        if (d.startsWith("521") && d.length == 13) d = "52" + d.drop(3)
        if (!mas && d.length == 10) d = "52$d"
        return d.takeIf { it.length in 11..15 }
    }

    suspend fun hacer(c: Command): String = when (c) {
        is Command.OpenApp -> abrirApp(c.name)
        is Command.Alarm -> alarma(c)
        is Command.Timer -> temporizador(c.seconds)
        is Command.Torch -> linterna(c.on)
        is Command.Volume -> volumen(c.level)
        is Command.Settings -> ajuste(c.panel)
        is Command.Time -> hora()
        is Command.Battery -> pila()
        is Command.Pc -> pc(c.text)
        is Command.Chat -> platicar(c.text)
        is Command.Call, is Command.Sms, is Command.WhatsApp -> "Eso necesita que me confirmes 🙏"
    }

    private fun abrir(i: Intent, ok: String, mal: String): String =
        if (runCatching { ctx.startActivity(i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }.isSuccess) ok else mal

    private fun plano(s: String) = Normalizer.normalize(s, Normalizer.Form.NFD)
        .replace(Regex("\\p{M}+"), "")
        .lowercase()
        .filter { it.isLetterOrDigit() }

    private fun abrirApp(nombre: String): String {
        val pm = ctx.packageManager
        val apps = pm.queryIntentActivities(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER), 0)
            .filter { it.activityInfo.packageName != ctx.packageName || plano(nombre) == "sapo" }
        val porNombre = apps.groupBy { it.loadLabel(pm).toString() }
        val buscado = plano(nombre)
        val elegido = porNombre.keys.firstOrNull { plano(it) == buscado }
            ?: Contacts.best(nombre, porNombre.keys.toList())
            ?: porNombre.keys.filter { buscado.length >= 3 && plano(it).contains(buscado) }.singleOrNull()
            ?: return "No encontré la app «$nombre» 🤔"
        val ri = porNombre.getValue(elegido).first()
        val i = Intent(Intent.ACTION_MAIN)
            .addCategory(Intent.CATEGORY_LAUNCHER)
            .setClassName(ri.activityInfo.packageName, ri.activityInfo.name)
            .addFlags(Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED)
        return abrir(i, "Abriendo $elegido 🚀", "No pude abrir $elegido 😕")
    }

    private fun alarma(c: Command.Alarm): String {
        val i = Intent(AlarmClock.ACTION_SET_ALARM)
            .putExtra(AlarmClock.EXTRA_HOUR, c.hour)
            .putExtra(AlarmClock.EXTRA_MINUTES, c.minute)
            .putExtra(AlarmClock.EXTRA_SKIP_UI, true)
        c.label?.takeIf { it.isNotBlank() }?.let { i.putExtra(AlarmClock.EXTRA_MESSAGE, it) }
        return abrir(i, "Alarma lista para las ${hhmm(c.hour, c.minute)} ⏰", "No encontré la app de alarmas 😕")
    }

    private fun temporizador(s: Int): String {
        val i = Intent(AlarmClock.ACTION_SET_TIMER)
            .putExtra(AlarmClock.EXTRA_LENGTH, s.coerceIn(1, 86_400))
            .putExtra(AlarmClock.EXTRA_MESSAGE, "Sapito")
            .putExtra(AlarmClock.EXTRA_SKIP_UI, true)
        return abrir(i, "Temporizador de ${duracion(s)} corriendo ⏳", "No encontré la app de temporizador 😕")
    }

    private fun duracion(s: Int): String {
        val h = s / 3600
        val m = (s % 3600) / 60
        val seg = s % 60
        return listOfNotNull(
            h.takeIf { it > 0 }?.let { "$it ${if (it == 1) "hora" else "horas"}" },
            m.takeIf { it > 0 }?.let { "$it ${if (it == 1) "minuto" else "minutos"}" },
            seg.takeIf { it > 0 }?.let { "$it ${if (it == 1) "segundo" else "segundos"}" }
        ).joinToString(" y ").ifBlank { "$s segundos" }
    }

    private fun linterna(on: Boolean): String = runCatching {
        val cm = ctx.getSystemService(CameraManager::class.java)
        val id = cm.cameraIdList.firstOrNull { cm.getCameraCharacteristics(it).get(CameraCharacteristics.FLASH_INFO_AVAILABLE) == true }
            ?: return "Tu cel no tiene linterna 😕"
        cm.setTorchMode(id, on)
        if (on) "Linterna prendida 🔦" else "Linterna apagada 🌑"
    }.getOrElse { "No pude con la linterna; ¿la cámara está ocupada? 😕" }

    private fun volumen(nivel: Int?): String {
        val am = ctx.getSystemService(AudioManager::class.java)
        val s = AudioManager.STREAM_MUSIC
        val max = am.getStreamMaxVolume(s)
        when (nivel) {
            null -> am.adjustStreamVolume(s, AudioManager.ADJUST_SAME, AudioManager.FLAG_SHOW_UI)
            Command.Volume.UP -> am.adjustStreamVolume(s, AudioManager.ADJUST_RAISE, AudioManager.FLAG_SHOW_UI)
            Command.Volume.DOWN -> am.adjustStreamVolume(s, AudioManager.ADJUST_LOWER, AudioManager.FLAG_SHOW_UI)
            else -> runCatching {
                am.setStreamVolume(s, (nivel.coerceIn(0, 100) * max / 100f).roundToInt(), AudioManager.FLAG_SHOW_UI)
            }
        }
        val pct = if (max > 0) am.getStreamVolume(s) * 100 / max else 0
        return when (nivel) {
            null -> "El volumen está en $pct% 🔉"
            Command.Volume.UP -> "Le subí: $pct% 🔊"
            Command.Volume.DOWN -> "Le bajé: $pct% 🔉"
            else -> "Volumen al $pct% 🔊"
        }
    }

    private fun ajuste(panel: String): String {
        val p = plano(panel)
        val (i, que) = when {
            p.contains("blue") -> Intent(Settings.ACTION_BLUETOOTH_SETTINGS) to "el Bluetooth"
            p.contains("wifi") || p.contains("wi") && p.contains("fi") ->
                (if (Build.VERSION.SDK_INT >= 29) Intent(Settings.Panel.ACTION_WIFI) else Intent(Settings.ACTION_WIFI_SETTINGS)) to "el wifi"
            p.contains("internet") || p.contains("datos") || p.contains("red") ->
                (if (Build.VERSION.SDK_INT >= 29) Intent(Settings.Panel.ACTION_INTERNET_CONNECTIVITY) else Intent(Settings.ACTION_WIRELESS_SETTINGS)) to "el internet"
            p.contains("vol") || p.contains("sonido") ->
                (if (Build.VERSION.SDK_INT >= 29) Intent(Settings.Panel.ACTION_VOLUME) else Intent(Settings.ACTION_SOUND_SETTINGS)) to "el volumen"
            p.contains("nfc") ->
                (if (Build.VERSION.SDK_INT >= 29) Intent(Settings.Panel.ACTION_NFC) else Intent(Settings.ACTION_NFC_SETTINGS)) to "el NFC"
            p.contains("avion") || p == "airplane" -> Intent(Settings.ACTION_AIRPLANE_MODE_SETTINGS) to "el modo avión"
            p.contains("pantalla") || p.contains("brillo") || p == "display" -> Intent(Settings.ACTION_DISPLAY_SETTINGS) to "la pantalla"
            p.contains("bateria") || p.contains("pila") -> Intent(Intent.ACTION_POWER_USAGE_SUMMARY) to "la batería"
            p.contains("ubicacion") || p.contains("gps") || p == "location" -> Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS) to "la ubicación"
            else -> Intent(Settings.ACTION_SETTINGS) to "los ajustes"
        }
        return abrir(i, "Te abrí $que ⚙️", "No pude abrir $que 😕")
    }

    private fun hhmm(h: Int, m: Int) = "%d:%02d".format(if (h % 12 == 0) 12 else h % 12, m) + " " + parteDelDia(h)

    private fun parteDelDia(h: Int) = when (h) {
        in 0..5 -> "de la madrugada"
        in 6..11 -> "de la mañana"
        in 12..18 -> "de la tarde"
        else -> "de la noche"
    }

    private fun hora(): String {
        val t = LocalTime.now()
        val h12 = if (t.hour % 12 == 0) 12 else t.hour % 12
        val m = "%02d".format(t.minute)
        return (if (h12 == 1) "Es la $h12:$m " else "Son las $h12:$m ") + parteDelDia(t.hour) + " 🕒"
    }

    private fun pila(): String {
        val bm = ctx.getSystemService(BatteryManager::class.java)
        val pct = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
        if (pct !in 0..100) return "No pude ver la pila 😕"
        val cargando = bm.isCharging
        return buildString {
            append("Traes $pct% de pila 🔋")
            if (cargando) append(" y estás cargando ⚡")
            else if (pct <= 20) append(". ¡Cárgame tantito!")
        }
    }

    private suspend fun pc(texto: String): String {
        if (Store.ajustes.pc == null) return "Aún no me vinculas con tu PC; hazlo en Ajustes › Tu PC 💻"
        return Enlace.preguntar(texto) ?: "No estoy conectado a tu PC 💻"
    }

    private suspend fun platicar(texto: String): String {
        val key = withContext(Dispatchers.IO) { Llave.leer(ctx) }
            ?: return "Croac 🐸 Para platicar necesito tu key de Gemini; ponla en Ajustes."
        val prompt = "Eres el Sapo, un sapito mexicano tierno, chistoso y buena onda que vive flotando en el celular de tu dueño. " +
            "Contesta en español de México, cálido y breve: una o dos frases cortas, sin listas, sin markdown y con un emoji como mucho. " +
            "Si te piden algo que no puedes hacer, dilo con cariño.\n\nTu dueño te dice: «$texto»"
        return runCatching { Gemini.generar(key, Store.ajustes.modelo, prompt) }
            .getOrElse { "Se me trabó la lengua 😵 ${it.message.orEmpty().take(90)}".trim() }
            .replace(Regex("[*_#`]"), "")
            .trim()
            .ifBlank { "Croac… me quedé sin palabras 🐸" }
    }
}
