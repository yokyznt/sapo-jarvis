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

    private fun archivo(ctx: Context) = File(ctx.filesDir, "gemini.key")

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

    fun existe(ctx: Context) = archivo(ctx).exists()

    fun guardar(ctx: Context, key: String) {
        if (key.isBlank()) {
            borrar(ctx)
            return
        }
        val c = Cipher.getInstance(TRANSFORMACION)
        c.init(Cipher.ENCRYPT_MODE, secreta())
        val iv = c.iv
        val datos = c.doFinal(key.trim().toByteArray(Charsets.UTF_8))
        archivo(ctx).writeBytes(byteArrayOf(iv.size.toByte()) + iv + datos)
    }

    fun leer(ctx: Context): String? = runCatching {
        val f = archivo(ctx)
        if (!f.exists()) return null
        val b = f.readBytes()
        val n = b[0].toInt()
        val c = Cipher.getInstance(TRANSFORMACION)
        c.init(Cipher.DECRYPT_MODE, secreta(), GCMParameterSpec(128, b.copyOfRange(1, 1 + n)))
        String(c.doFinal(b.copyOfRange(1 + n, b.size)), Charsets.UTF_8)
    }.getOrNull()

    fun borrar(ctx: Context) {
        archivo(ctx).delete()
    }
}
