package io.github.yokyznt.sapo.flotante

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.setValue
import io.github.yokyznt.sapo.Permisos
import io.github.yokyznt.sapo.ui.SapoTema

class PermisoActivity : ComponentActivity() {
    private var paso by mutableIntStateOf(0)
    private var avisado = false
    private lateinit var permiso: String

    private val pedir = registerForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        if (ok || shouldShowRequestPermissionRationale(permiso)) terminar(ok) else paso = 1
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        permiso = intent.getStringExtra(PERMISO) ?: run {
            finish()
            return
        }
        val razon = intent.getStringExtra(RAZON).orEmpty()
        if (Permisos.tiene(this, permiso)) {
            terminar(true)
            return
        }
        setContent {
            SapoTema {
                if (paso == 0) {
                    AlertDialog(
                        onDismissRequest = { terminar(false) },
                        title = { Text("Permiso para el sapito 🐸") },
                        text = { Text(razon) },
                        confirmButton = { TextButton(onClick = { pedir.launch(permiso) }) { Text("Dale") } },
                        dismissButton = { TextButton(onClick = { terminar(false) }) { Text("Ahora no") } }
                    )
                } else {
                    AlertDialog(
                        onDismissRequest = { terminar(false) },
                        title = { Text("Android ya no me deja preguntar") },
                        text = { Text("Actívalo tú en la info de la app › Permisos, y luego vuelve a tocarme.") },
                        confirmButton = {
                            TextButton(onClick = {
                                Permisos.abrirApp(this)
                                terminar(false)
                            }) { Text("Abrir info") }
                        },
                        dismissButton = { TextButton(onClick = { terminar(false) }) { Text("Ahora no") } }
                    )
                }
            }
        }
    }

    private fun terminar(ok: Boolean) {
        if (!avisado) {
            avisado = true
            SapoFlotante.permisoListo(permiso, ok)
        }
        finish()
    }

    override fun onDestroy() {
        if (!avisado && isFinishing && ::permiso.isInitialized) {
            avisado = true
            SapoFlotante.permisoListo(permiso, Permisos.tiene(this, permiso))
        }
        super.onDestroy()
    }

    companion object {
        const val PERMISO = "permiso"
        const val RAZON = "razon"
    }
}
