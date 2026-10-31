# Etapa 8 · contrato de respuesta automática

## `:core` (JVM, con pruebas)

```kotlin
enum class BusyReason { Manual, NoMolestar, PantallaApagada, Horario }
data class BusyState(val manual: Boolean, val dnd: Boolean, val screenOffSince: Long?, val schedule: List<IntRange>, val idleMinutes: Int)
object Busy { fun reason(s: BusyState, now: java.time.LocalDateTime, nowMs: Long): BusyReason? }

data class Sent(val contact: String, val atMs: Long)
data class Limits(val perContactGapMin: Int = 10, val perContactHour: Int = 3, val globalHour: Int = 12)
object Policy {
    fun allow(contact: String, whitelisted: Boolean, isGroup: Boolean, paused: Boolean, history: List<Sent>, nowMs: Long, limits: Limits = Limits()): Decision
}
sealed interface Decision { data object Ok : Decision; data class No(val why: String) : Decision }
object Delay { fun ms(text: String, rnd: kotlin.random.Random): Long }
```

- `schedule`: minutos del día (`0..1439`) en que está ocupado; rangos que cruzan medianoche se parten en dos.
- `Busy.reason`: prioridad `Manual` > `NoMolestar` > `Horario` > `PantallaApagada` (solo si lleva ≥ `idleMinutes` apagada).
- `Policy.allow` niega: grupo, fuera de lista blanca, pausado (pánico), menos de `perContactGapMin` desde la última a ese contacto, `perContactHour` en la última hora, `globalHour` en total.
- `Delay.ms`: 15–45 s más ~60 ms por carácter, tope 90 s.

## `:app`

- Ajustes: interruptor "Responder solo cuando esté ocupado" con modos (manual, No molestar, pantalla apagada X min, horario), tope de límites.
- Al llegar mensaje y `Busy.reason != null` y `Policy.allow == Ok`: genera con `Prompt.reply(auto=true)`, espera `Delay.ms`; si en ese tiempo el usuario abrió/contestó el chat (la notificación desaparece o aparece un mensaje propio en MessagingStyle) se cancela; si no, envía `Guard.mark(texto)` por RemoteInput y lo guarda en historial.
- Pánico: acción "Parar al sapo" en la notificación persistente y un mosaico de Ajustes rápidos; pausa todo hasta reactivar.
- Pestaña Historial: lo que respondió, a quién, cuándo y por qué estaba ocupado.
- Notificación persistente mientras el modo automático está activo ("El sapo contesta por ti 🤖").
