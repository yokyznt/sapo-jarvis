package io.github.yokyznt.sapo

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.io.File
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

object Llave {
    private const val ALIAS = "sapo_gemini"
    private const val TRANSFORMACION = "AES/GCM/NoPadding"
    private const val GEMINI = "gemini.key"

    private fun archivo(ctx: Context, nombre: String) = File(ctx.filesDir, nombre)

    private fun secreta(): SecretKey {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (ks.getEntry(ALIAS, null) as? KeyStore.SecretKeyEntry)?.let { return it.secretKey }
        val gen = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        gen.init(
            KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build()
        )
        return gen.generateKey()
    }

    fun existe(ctx: Context) = archivo(ctx, GEMINI).exists()

    fun guardar(ctx: Context, key: String) = guardarEn(ctx, GEMINI, key)

    fun leer(ctx: Context): String? = leerDe(ctx, GEMINI)

    fun borrar(ctx: Context) = borrarDe(ctx, GEMINI)

    fun guardarEn(ctx: Context, nombre: String, valor: String) {
        if (valor.isBlank()) {
            borrarDe(ctx, nombre)
            return
        }
        val c = Cipher.getInstance(TRANSFORMACION)
        c.init(Cipher.ENCRYPT_MODE, secreta())
        val iv = c.iv
        val datos = c.doFinal(valor.trim().toByteArray(Charsets.UTF_8))
        archivo(ctx, nombre).writeBytes(byteArrayOf(iv.size.toByte()) + iv + datos)
    }

    fun leerDe(ctx: Context, nombre: String): String? = runCatching {
        val f = archivo(ctx, nombre)
        if (!f.exists()) return null
        val b = f.readBytes()
        val n = b[0].toInt()
        val c = Cipher.getInstance(TRANSFORMACION)
        c.init(Cipher.DECRYPT_MODE, secreta(), GCMParameterSpec(128, b.copyOfRange(1, 1 + n)))
        String(c.doFinal(b.copyOfRange(1 + n, b.size)), Charsets.UTF_8)
    }.getOrNull()

    fun borrarDe(ctx: Context, nombre: String) {
        archivo(ctx, nombre).delete()
    }
}
