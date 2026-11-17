package io.github.yokyznt.sapo

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import io.github.yokyznt.sapo.core.Pairs
import io.github.yokyznt.sapo.core.Style
import io.github.yokyznt.sapo.core.WhatsAppExport
import java.io.File
import java.util.zip.ZipInputStream

object Importador {
    private val prefijo = Regex(
        "^(chat de whatsapp con|whatsapp chat with|whatsapp chat -|chat de whatsapp -|conversa do whatsapp com)\\s*",
        RegexOption.IGNORE_CASE
    )
    private val raros = Regex("[\\\\/:*?\"<>|]")

    private fun carpeta(ctx: Context) = File(ctx.filesDir, "chats").apply { mkdirs() }

    fun importar(ctx: Context, uris: List<Uri>): Int {
        var n = 0
        for (uri in uris) {
            val nombre = nombreDe(ctx, uri)
            val tipo = ctx.contentResolver.getType(uri).orEmpty()
            val esZip = tipo.contains("zip") || nombre.endsWith(".zip", true)
            val textos = if (esZip) delZip(ctx, uri) else listOf(nombre to leerTexto(ctx, uri))
            for ((archivo, texto) in textos) {
                if (texto.isBlank()) continue
                val limpio = limpiar(if (esZip && archivo.isBlank()) nombre else archivo).ifBlank { limpiar(nombre) }
                File(carpeta(ctx), raros.replace(limpio, "_") + ".txt").writeText(texto)
                n++
            }
        }
        reconstruir(ctx)
        return n
    }

    fun reconstruir(ctx: Context) {
        val archivos = carpeta(ctx).listFiles { f -> f.extension == "txt" }.orEmpty().sortedBy { it.name }
        val crudos = archivos.map { it.nameWithoutExtension to it.readText() }
        val primeros = crudos.map { (n, t) -> WhatsAppExport.parse(n, t) }
        val yo = Store.ajustes.yoManual ?: WhatsAppExport.guessMe(primeros)
        val chats = if (yo != null) crudos.map { (n, t) -> WhatsAppExport.parse(n, t, yo) } else primeros
        val pares = chats.flatMap { Pairs.build(it) }.map { ParGuardado(it.them, it.me, it.contact) }
        val mios = chats.flatMap { c -> c.lines.filter { it.author == c.me && c.me.isNotBlank() }.map { it.text } }
        val perfil = if (mios.isEmpty()) null else Style.profile(mios)
        Store.guardarImportacion(
            Importado(
                yo = yo ?: chats.map { it.me }.firstOrNull { it.isNotBlank() },
                chats = chats.size,
                mensajes = chats.sumOf { it.lines.size },
                mios = mios.size,
                pares = pares.size,
                descripcion = perfil?.let { Style.describe(it) }.orEmpty()
            ),
            pares,
            perfil?.let { EstiloGuardado.de(it) }
        )
    }

    fun borrar(ctx: Context) {
        carpeta(ctx).deleteRecursively()
        Store.guardarImportacion(Importado(), emptyList(), null)
    }

    private fun limpiar(nombre: String): String =
        prefijo.replace(nombre.substringAfterLast('/').substringBeforeLast('.'), "").trim()

    private fun nombreDe(ctx: Context, uri: Uri): String {
        val nombre = runCatching {
            ctx.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
                if (c.moveToFirst()) c.getString(0) else null
            }
        }.getOrNull()
        return nombre ?: uri.lastPathSegment.orEmpty()
    }

    private fun leerTexto(ctx: Context, uri: Uri): String =
        ctx.contentResolver.openInputStream(uri)?.use { it.readBytes().toString(Charsets.UTF_8) }.orEmpty()

    private fun delZip(ctx: Context, uri: Uri): List<kotlin.Pair<String, String>> {
        val salida = ArrayList<kotlin.Pair<String, String>>()
        ctx.contentResolver.openInputStream(uri)?.use { entrada ->
            ZipInputStream(entrada).use { zip ->
                var e = zip.nextEntry
                while (e != null) {
                    if (!e.isDirectory && e.name.endsWith(".txt", true)) {
                        salida.add(e.name to zip.readBytes().toString(Charsets.UTF_8))
                    }
                    e = zip.nextEntry
                }
            }
        }
        return salida
    }
}
