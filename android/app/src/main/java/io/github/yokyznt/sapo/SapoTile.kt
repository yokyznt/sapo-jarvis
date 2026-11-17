package io.github.yokyznt.sapo

import android.graphics.drawable.Icon
import android.os.Build
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService
import android.widget.Toast

class SapoTile : TileService() {

    override fun onStartListening() {
        super.onStartListening()
        pintar()
    }

    override fun onClick() {
        super.onClick()
        Store.init(this)
        val a = Store.ajustes.auto
        if (!a.activo) {
            Toast.makeText(this, "Prende el modo automático en Ajustes del Sapo", Toast.LENGTH_LONG).show()
            pintar()
            return
        }
        Modo.pausar(this, !a.pausado)
        pintar()
    }

    private fun pintar() {
        Store.init(this)
        val t = qsTile ?: return
        val a = Store.ajustes.auto
        t.icon = Icon.createWithResource(this, R.drawable.ic_stat_sapo)
        t.label = "Sapo auto"
        t.state = when {
            !a.activo -> Tile.STATE_UNAVAILABLE
            a.pausado -> Tile.STATE_INACTIVE
            else -> Tile.STATE_ACTIVE
        }
        if (Build.VERSION.SDK_INT >= 29) {
            t.subtitle = when {
                !a.activo -> "Apagado"
                a.pausado -> "En pausa"
                else -> "Contestando 🤖"
            }
        }
        t.updateTile()
    }
}
