package com.fallaxvision.docunlocker

import com.fallaxvision.docunlocker.engine.Cfbf
import com.fallaxvision.docunlocker.engine.OfficeCrypto

/**
 * Barebone password-recovery engine for the Android build. Office 2013+ agile
 * encryption only (.docx / .xlsx / .pptx), powered by the pure-Java
 * OfficeCrypto engine (verified on the JVM).
 */
object Cracker {

    private val PRIORITY = listOf(
        "123", "1234", "12345", "123456", "1234567", "12345678", "123456789",
        "0000", "1111", "111111", "000000", "121212", "654321", "qwerty",
        "azerty", "password", "Password", "Password1", "Password1!", "passw0rd",
        "P@ssw0rd", "motdepasse", "secret", "admin", "welcome", "Welcome1",
        "letmein", "iloveyou", "test", "test123", "office", "document",
        "2020", "2021", "2022", "2023", "2024", "2025", "2026"
    )

    private val WORDS = listOf(
        "love", "money", "family", "freedom", "hello", "summer", "winter",
        "secret", "angel", "dream", "star", "sunshine", "computer", "office",
        "school", "company", "jesus", "god", "grace", "hope", "amour", "soleil",
        "famille", "maison", "bonjour", "amor", "familia", "alex", "maria",
        "david", "sarah", "james", "daniel", "michael", "thomas", "peter"
    )

    private val SUFFIXES = listOf(
        "", "1", "12", "123", "1234", "2023", "2024", "2025", "2026",
        "!", "@", "#", "1!", "123!", "2025!", "2026!"
    )

    fun isEncrypted(bytes: ByteArray): Boolean = try {
        Cfbf(bytes).has("EncryptionInfo")
    } catch (e: Exception) {
        false
    }

    /** Approximate number of candidates, for the progress bar. */
    fun estimate(maxDigits: Int): Long {
        var n = PRIORITY.size.toLong()
        n += WORDS.size.toLong() * SUFFIXES.size * 3   // lower / Cap / UPPER
        for (d in 1..maxDigits) n += Math.pow(10.0, d.toDouble()).toLong()
        return n
    }

    /** Lazy candidate stream: priority -> mutated words -> numeric PINs. */
    fun candidates(maxDigits: Int): Sequence<String> = sequence {
        for (p in PRIORITY) yield(p)
        for (w in WORDS) {
            val forms = listOf(w, w.replaceFirstChar { it.uppercase() }, w.uppercase())
            for (form in forms) for (s in SUFFIXES) yield(form + s)
        }
        for (d in 1..maxDigits) {
            val end = Math.pow(10.0, d.toDouble()).toLong()
            var i = 0L
            while (i < end) {
                yield(i.toString().padStart(d, '0'))
                i++
            }
        }
    }

    fun test(bytes: ByteArray, password: String): Boolean = try {
        OfficeCrypto.decrypt(bytes, password).ok
    } catch (e: Exception) {
        false
    }

    /** Returns the decrypted bytes if the password is correct, else null. */
    fun unlock(bytes: ByteArray, password: String): ByteArray? = try {
        val r = OfficeCrypto.decrypt(bytes, password)
        if (r.ok) r.plaintext else null
    } catch (e: Exception) {
        null
    }
}
