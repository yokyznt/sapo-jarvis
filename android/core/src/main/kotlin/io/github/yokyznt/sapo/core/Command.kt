package io.github.yokyznt.sapo.core

sealed interface Command {
    data class Call(val who: String) : Command
    data class Sms(val who: String, val text: String) : Command
    data class WhatsApp(val who: String, val text: String) : Command
    data class OpenApp(val name: String) : Command
    data class Alarm(val hour: Int, val minute: Int, val label: String?) : Command
    data class Timer(val seconds: Int) : Command
    data class Torch(val on: Boolean) : Command
    data class Volume(val level: Int?) : Command {
        companion object {
            const val UP = 101
            const val DOWN = -1
        }
    }
    data class Settings(val panel: String) : Command
    data object Time : Command
    data object Battery : Command
    data class Pc(val text: String) : Command
    data class Chat(val text: String) : Command
}
