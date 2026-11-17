package io.github.yokyznt.sapo

import android.app.Application
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob

class SapoApp : Application() {
    override fun onCreate() {
        super.onCreate()
        Store.init(this)
        Avisos.crearCanal(this)
        Modo.crearCanal(this)
        Modo.refrescar(this)
        Enlace.arrancar(this)
    }

    companion object {
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    }
}
