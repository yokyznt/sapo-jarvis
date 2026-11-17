package io.github.yokyznt.sapo.core

object Prompt {
    fun reply(
        incoming: String,
        contact: String,
        history: List<ChatLine>,
        style: StyleProfile,
        examples: List<Pair>,
        auto: Boolean,
        group: String? = null,
        sender: String? = null
    ): String {
        val me = history.firstOrNull { it.author != contact && it.author.isNotBlank() }?.author ?: "el dueño del teléfono"
        val sb = StringBuilder()
        if (group != null) sb.append("Eres ").append(me).append(" respondiendo en el grupo de WhatsApp «").append(group).append("».\n")
        else sb.append("Eres ").append(me).append(" respondiendo por WhatsApp a ").append(contact).append(".\n")
        sb.append("Escribe exactamente como escribiría ").append(me).append(", en español, con su mismo tono y forma de escribir.\n\n")
        sb.append("PERFIL DE ESTILO\n").append(Style.describe(style)).append("\n\n")
        if (examples.isNotEmpty()) {
            sb.append("EJEMPLOS REALES DE CÓMO RESPONDE\n")
            for (e in examples) {
                sb.append("- Le escriben: ").append(oneLine(e.them)).append('\n')
                sb.append("  Responde: ").append(oneLine(e.me)).append('\n')
            }
            sb.append('\n')
        }
        val recent = history.takeLast(15)
        if (recent.isNotEmpty()) {
            sb.append("ÚLTIMOS MENSAJES\n")
            for (l in recent) sb.append(l.author).append(": ").append(oneLine(l.text)).append('\n')
            sb.append('\n')
        }
        sb.append("REGLAS\n")
        sb.append("- No inventes planes, horarios, citas ni compromisos; no aceptes ni confirmes nada en nombre de ").append(me).append(".\n")
        sb.append("- Si piden algo importante, urgente, dinero o una decisión, di que luego le respondes con calma.\n")
        sb.append("- Nada de datos personales: no compartas direcciones, teléfonos, contraseñas, códigos, cuentas ni ubicación.\n")
        sb.append("- Responde en 1 o 2 frases cortas, sin explicar ni justificar.\n")
        sb.append("- Nunca digas que eres una IA, un asistente o un bot.\n")
        sb.append("- Devuelve solo el texto del mensaje, sin comillas ni prefijos como \"Yo:\".\n")
        if (auto) sb.append("- Este mensaje se enviará automáticamente sin revisión: sé prudente y neutral.\n")
        if (group != null) sb.append("- Es un grupo: contesta solo a lo que te dijeron a ti, corto y sin meterte en otras pláticas.\n")
        sb.append('\n')
        if (group != null) sb.append("MENSAJE NUEVO DE ").append(sender ?: "alguien").append(" EN EL GRUPO:\n")
        else sb.append("MENSAJE NUEVO DE ").append(contact).append(":\n").append(incoming.trim()).append("\n\n")
        sb.append("Tu respuesta:")
        return sb.toString()
    }

    private fun oneLine(s: String): String = s.replace(Regex("\\s*\\n\\s*"), " / ").trim()
}
