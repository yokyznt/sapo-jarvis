package io.github.yokyznt.sapo

import android.content.Context
import io.github.yokyznt.sapo.core.Command
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

object Agente {
    private const val PASOS = 14
    private val peligro = Regex(
        "\\b(pagar|paga ahora|comprar|compra ahora|confirmar (pago|compra)|transferir|enviar dinero|eliminar cuenta|borrar cuenta|cerrar sesi[oó]n|desinstalar|restablecer|formatear|borrar todo)\\b",
        RegexOption.IGNORE_CASE
    )

    private val ajustes = Regex("^(ajustes|configuracion|configuración|settings|config)$", RegexOption.IGNORE_CASE)

    private fun abrir(ctx: Context, nombre: String, abrirApp: (String) -> String): Boolean {
        if (ajustes.matches(nombre.trim())) {
            return runCatching { ctx.startActivity(android.content.Intent(android.provider.Settings.ACTION_SETTINGS).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)) }.isSuccess
        }
        val r = abrirApp(nombre)
        return !r.startsWith("No ")
    }

    suspend fun hacer(ctx: Context, meta: String, abrirApp: (String) -> String): String {
        val key = withContext(Dispatchers.IO) { Llave.leer(ctx) }
            ?: return "Para mover tu cel necesito tu key de Gemini; ponla en Ajustes."
        if (!Control.listo()) {
            Permisos.abrirAccesibilidad(ctx)
            return "Actívame en Accesibilidad → Sapo para poder mover tu cel, y vuelve a pedírmelo."
        }
        val hecho = ArrayList<String>()
        var fallos = 0
        var antes = ""
        var ultimo = ""
        var iguales = 0
        repeat(PASOS) {
            val nodos = Control.nodos()
            val pantalla = nodos.mapIndexed { i, n ->
                val tipo = when {
                    n.editable -> "campo"
                    n.desplazable -> "lista"
                    n.clic -> "botón"
                    else -> "texto"
                }
                "$i [$tipo] ${n.texto.ifEmpty { "(sin texto)" }}"
            }.joinToString("\n")
            if (hecho.isNotEmpty() && pantalla == antes) hecho[hecho.size - 1] = hecho.last() + " (la pantalla NO cambió)"
            antes = pantalla
            val prompt = buildString {
                append("Controlas un celular Android para cumplir lo que pidió su dueño. Responde SOLO un JSON en una línea.\n")
                append("Acciones: {\"accion\":\"tocar\",\"id\":N} | {\"accion\":\"escribir\",\"id\":N,\"texto\":\"...\"} | {\"accion\":\"enter\"} | ")
                append("{\"accion\":\"deslizar\",\"dir\":\"abajo|arriba\"} | {\"accion\":\"abrir_app\",\"texto\":\"nombre\"} | {\"accion\":\"atras\"} | ")
                append("{\"accion\":\"inicio\"} | {\"accion\":\"listo\",\"resumen\":\"frase corta de lo que hiciste\"} | {\"accion\":\"no_puedo\",\"resumen\":\"por qué\"}\n")
                append("Reglas: un paso a la vez; si la app correcta no está abierta, ábrela primero; nunca pagues, compres, borres cuentas ni cierres sesión; ")
                append("si algo pide contraseña o confirmar dinero, usa no_puedo. Los interruptores dicen [prendido] o [apagado]: revísalo antes de tocarlo otra vez. Cuando ya se cumplió, usa listo.\n\n")
                append("PEDIDO: ").append(meta).append("\n")
                append("APP ABIERTA: ").append(Control.app().ifEmpty { "desconocida" }).append("\n")
                if (hecho.isNotEmpty()) append("YA HICISTE: ").append(hecho.takeLast(8).joinToString("; ")).append("\n")
                if (iguales >= 2) append("OJO: repetiste la misma acción y no funcionó; haz algo distinto (atras, deslizar, otro botón o abrir_app).\n")
                append("PANTALLA:\n").append(pantalla.ifEmpty { "(vacía o cargando)" }).append("\n\nJSON:")
            }
            val crudo = runCatching { Gemini.generar(key, Store.ajustes.modelo, prompt, json = true) }.getOrElse {
                return "Se me trabó el cerebro a medio camino 😵 ${it.message.orEmpty().take(80)}".trim()
            }
            val j = runCatching {
                Json.parseToJsonElement(crudo.substring(crudo.indexOf('{'), crudo.lastIndexOf('}') + 1)).jsonObject
            }.getOrNull()
            if (j == null) {
                if (++fallos >= 3) return "No le entendí a la pantalla, mejor hazlo tú 😕"
                return@repeat
            }
            val accion = j["accion"]?.jsonPrimitive?.contentOrNull.orEmpty()
            val firma = j.toString()
            iguales = if (firma == ultimo) iguales + 1 else 0
            ultimo = firma
            if (iguales >= 4) return "Me atoré en la misma pantalla 😕 mejor hazlo tú"
            val id = j["id"]?.jsonPrimitive?.intOrNull
            val texto = j["texto"]?.jsonPrimitive?.contentOrNull.orEmpty()
            val nodo = id?.let { nodos.getOrNull(it) }
            val ok = when (accion) {
                "listo" -> return j["resumen"]?.jsonPrimitive?.contentOrNull?.ifBlank { null } ?: "Listo ✅"
                "no_puedo" -> return j["resumen"]?.jsonPrimitive?.contentOrNull?.ifBlank { null } ?: "Eso no lo pude hacer 😕"
                "tocar" -> {
                    if (nodo == null) false
                    else if (peligro.containsMatchIn(nodo.texto)) return "Eso («${nodo.texto.take(40)}») lo tienes que tocar tú 🙏"
                    else Control.tocar(nodo).also { hecho += "toqué «${nodo.texto.take(30)}»" }
                }
                "escribir" -> Control.escribir(texto, nodo).also { hecho += "escribí «${texto.take(30)}»" }
                "enter" -> Control.enter().also { hecho += "di enter" }
                "deslizar" -> Control.deslizar(j["dir"]?.jsonPrimitive?.contentOrNull != "arriba").also { hecho += "deslicé" }
                "abrir_app" -> abrir(ctx, texto, abrirApp).also { hecho += if (it) "abrí $texto" else "NO pude abrir «$texto», busca otra forma" }
                "atras" -> Control.global(Command.Screen.BACK).also { hecho += "regresé" }
                "inicio" -> Control.global(Command.Screen.HOME).also { hecho += "fui al inicio" }
                else -> false
            }
            if (!ok && ++fallos >= 4) return "Me atoré intentando eso 😕 Ya llevaba: ${hecho.takeLast(3).joinToString(", ")}"
            delay(if (accion == "abrir_app") 2500 else 1400)
            var espera = 0
            while (espera < 8 && Control.app() == "com.android.systemui" && accion != "deslizar") {
                delay(500)
                espera++
            }
        }
        return "Le di $PASOS pasos y no terminé; te lo dejo a medias 😅"
    }
}
