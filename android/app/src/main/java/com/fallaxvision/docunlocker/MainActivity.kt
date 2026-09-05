package com.fallaxvision.docunlocker

import android.content.ContentValues
import android.content.Context
import android.content.SharedPreferences
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.provider.MediaStore
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.semantics.Role
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.isActive
import com.fallaxvision.docunlocker.engine.OfficeCrypto
import com.fallaxvision.docunlocker.engine.DocumentInput
import java.io.File

private val Blue = Color(0xFF3B82F6)
private val Purple = Color(0xFF8B5CF6)

private fun darkScheme() = darkColorScheme(
    primary = Blue, secondary = Purple,
    background = Color(0xFF0B0F17), surface = Color(0xFF121826),
    surfaceVariant = Color(0xFF1B2333)
)

private fun lightScheme() = lightColorScheme(
    primary = Blue, secondary = Purple,
    background = Color(0xFFEEF1F7), surface = Color(0xFFFFFFFF),
    surfaceVariant = Color(0xFFE5E9F2)
)

private val OFFICE_EXTS = listOf(
    ".docx", ".docm", ".doc", ".xlsx", ".xlsm", ".xls", ".pptx", ".pptm", ".ppt"
)

class MainActivity : ComponentActivity() {
    @Volatile private var stopFlag = false
    private lateinit var prefs: SharedPreferences

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = getSharedPreferences("doc_unlocker", Context.MODE_PRIVATE)
        setContent {
            var themeMode by remember { mutableIntStateOf(prefs.getInt("theme", 0).coerceIn(0, 2)) }
            var keepAwake by remember { mutableStateOf(prefs.getBoolean("keepAwake", true)) }
            var vibrate by remember { mutableStateOf(prefs.getBoolean("vibrate", true)) }
            fun save() = prefs.edit()
                .putInt("theme", themeMode)
                .putBoolean("keepAwake", keepAwake)
                .putBoolean("vibrate", vibrate).apply()

            val dark = when (themeMode) { 1 -> false; 2 -> true; else -> isSystemInDarkTheme() }
            MaterialTheme(colorScheme = if (dark) darkScheme() else lightScheme()) {
                Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    AppScreen(
                        themeMode, keepAwake, vibrate,
                        onThemeChange = { themeMode = it; save() },
                        onKeepAwakeChange = { keepAwake = it; save() },
                        onVibrateChange = { vibrate = it; save() },
                    )
                }
            }
        }
    }

    @Composable
    private fun AppScreen(
        themeMode: Int, keepAwake: Boolean, vibrate: Boolean,
        onThemeChange: (Int) -> Unit,
        onKeepAwakeChange: (Boolean) -> Unit,
        onVibrateChange: (Boolean) -> Unit,
    ) {
        val scope = rememberCoroutineScope()
        var fileBytes by remember { mutableStateOf<ByteArray?>(null) }
        var fileName by remember { mutableStateOf("") }
        var knownPw by remember { mutableStateOf("") }
        var maxDigits by remember { mutableStateOf(6) }
        var running by remember { mutableStateOf(false) }
        var loading by remember { mutableStateOf(false) }
        var progress by remember { mutableStateOf(0f) }
        var status by remember { mutableStateOf("Idle") }
        var tries by remember { mutableStateOf(0L) }
        var showSettings by remember { mutableStateOf(false) }
        var warnKind by remember { mutableStateOf<String?>(null) }   // "office"/"pdf"/"unsupported"
        val busy = running || loading
        DisposableEffect(Unit) {
            onDispose { stopFlag = true; keepScreenOn(false) }
        }
        LaunchedEffect(running, keepAwake) { keepScreenOn(running && keepAwake) }

        val picker = rememberLauncherForActivityResult(
            ActivityResultContracts.OpenDocument()
        ) { uri: Uri? ->
            if (uri != null && !busy) {
                loading = true; fileBytes = null; fileName = ""; status = "Reading document..."
                stopFlag = false
                scope.launch {
                    try {
                        val imported = withContext(Dispatchers.IO) {
                            val job = coroutineContext
                            val name = queryName(uri)
                            val bytes = contentResolver.openInputStream(uri)?.use {
                                DocumentInput.read(it) { stopFlag || !job.isActive }
                            } ?: error("This document could not be opened.")
                            name to bytes
                        }
                        fileName = imported.first; fileBytes = imported.second
                        progress = 0f; tries = 0; status = "Ready"
                    } catch (e: CancellationException) {
                        status = "Stopped."; throw e
                    } catch (e: Exception) {
                        status = "Could not read document: ${e.message}"
                    } finally { loading = false }
                }
            }
        }

        fun finishRun(msg: String) {
            running = false; status = msg
            keepScreenOn(false)
            if (vibrate) doVibrate()
        }

        fun beginCrack() {
            val data = fileBytes ?: return
            if (busy) return
            val password = knownPw
            val digits = maxDigits
            val name = fileName
            stopFlag = false; running = true; progress = 0f; tries = 0
            status = "Reading..."
            keepScreenOn(keepAwake)
            scope.launch {
                try {
                val res = withContext(Dispatchers.Default) {
                    val job = coroutineContext
                    val prepared = OfficeCrypto.prepare(data)
                    fun unlock(candidate: String) = prepared.decrypt(candidate) {
                        stopFlag || !job.isActive
                    }
                    if (password.isNotEmpty()) {
                        val result = unlock(password)
                        return@withContext if (result.ok) password to result.plaintext else null
                    }
                    val total = Cracker.estimate(digits).coerceAtLeast(1)
                    var n = 0L
                    var lastUpdate = 0L
                    for (cand in Cracker.candidates(digits)) {
                        if (stopFlag || !job.isActive) throw CancellationException("Stopped")
                        n++
                        val now = android.os.SystemClock.elapsedRealtime()
                        if (now - lastUpdate >= 200) {
                            lastUpdate = now
                            withContext(Dispatchers.Main) {
                                tries = n; progress = (n.toFloat() / total).coerceIn(0f, 0.99f)
                            }
                        }
                        val result = unlock(cand)
                        if (result.ok) {
                            withContext(Dispatchers.Main) { tries = n }
                            return@withContext cand to result.plaintext
                        }
                    }
                    null
                }
                if (res == null) {
                    finishRun(if (password.isNotEmpty()) "That password did not work."
                              else "Not found. Try a longer PIN length.")
                } else {
                    if (stopFlag) throw CancellationException("Stopped")
                    status = "Saving unlocked copy..."
                    val where = withContext(Dispatchers.IO) { saveToDownloads("Unlocked_$name", res.second) }
                    progress = 1f; knownPw = ""
                    finishRun("Password: ${res.first}\nSaved: $where")
                }
                } catch (e: CancellationException) {
                    status = "Stopped."
                } catch (e: Exception) {
                    status = "Unable to unlock: ${e.message}"
                } finally { running = false; keepScreenOn(false) }
            }
        }

        fun onStart() {
            if (busy) return
            val data = fileBytes
            if (data == null) { status = "Pick a document first."; return }
            val lower = fileName.lowercase()
            val office = OFFICE_EXTS.any { lower.endsWith(it) }
            if (!office) { warnKind = if (lower.endsWith(".pdf")) "pdf" else "unsupported"; return }
            // Container validation happens once in the recovery worker.
            beginCrack()
        }

        // ---- dialogs ----
        if (showSettings) {
            SettingsDialog(themeMode, keepAwake, vibrate,
                onThemeChange, onKeepAwakeChange, onVibrateChange) { showSettings = false }
        }
        warnKind?.let { kind ->
            val msg = when (kind) {
                "pdf" -> "PDFs aren't supported on Android yet — use the desktop app. " +
                    "Open the PDF in Acrobat Reader or your browser to check its protection."
                "unsupported" -> "Unsupported file type. The Android app handles Word, Excel and " +
                    "PowerPoint. Choose a supported Office document."
                else -> "This file doesn't look encrypted. Try opening it first in Word / Excel / " +
                    "PowerPoint, Google Docs, or WPS Office — it may open with no password. " +
                    "Continue anyway?"
            }
            AlertDialog(
                onDismissRequest = { warnKind = null },
                title = { Text("Heads up") },
                text = { Text(msg, fontSize = 14.sp) },
                confirmButton = {
                    TextButton(onClick = { warnKind = null }) {
                        Text("OK")
                    }
                },
            )
        }

        val scroll = rememberScrollState()
        Column(
            Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.systemBars).imePadding()
                .verticalScroll(scroll).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Image(
                    painter = painterResource(R.mipmap.ic_launcher),
                    contentDescription = "Doc Unlocker",
                    modifier = Modifier.size(40.dp).clip(RoundedCornerShape(10.dp))
                )
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text("Doc Unlocker", fontWeight = FontWeight.Bold, fontSize = 22.sp)
                    Text("Password Recovery · v${BuildConfig.VERSION_NAME}",
                        fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                IconButton(onClick = { showSettings = true }) {
                    Icon(Icons.Filled.Settings, contentDescription = "Settings")
                }
            }

            Card(modifier = Modifier.fillMaxWidth(), shape = MaterialTheme.shapes.large) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("Locked document", fontWeight = FontWeight.SemiBold)
                    Text(if (fileName.isBlank()) "No file selected" else fileName,
                        color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 13.sp)
                    OutlinedButton(
                        onClick = {
                            picker.launch(arrayOf(
                                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                "application/octet-stream", "application/*", "*/*"))
                        },
                        enabled = !busy, shape = MaterialTheme.shapes.large,
                        modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)
                    ) { Text("📁  Choose document") }
                }
            }

            Card(modifier = Modifier.fillMaxWidth(), shape = MaterialTheme.shapes.large) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("Options", fontWeight = FontWeight.SemiBold)
                    OutlinedTextField(
                        value = knownPw, onValueChange = { if (it.length <= 1024) knownPw = it },
                        label = { Text("Known password (optional)") },
                        singleLine = true, enabled = !busy,
                        visualTransformation = PasswordVisualTransformation(),
                        modifier = Modifier.fillMaxWidth(), shape = MaterialTheme.shapes.large
                    )
                    Text("Try numeric PINs up to: $maxDigits digits", fontSize = 13.sp)
                    Slider(
                        value = maxDigits.toFloat(), onValueChange = { maxDigits = it.toInt() },
                        valueRange = 1f..8f, steps = 6, enabled = !busy && knownPw.isEmpty()
                    )
                }
            }

            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Button(
                    onClick = { onStart() }, enabled = !busy && fileBytes != null,
                    modifier = Modifier.weight(1f).heightIn(min = 50.dp), shape = MaterialTheme.shapes.large
                ) { Text(if (knownPw.isNotEmpty()) "Unlock document" else "Start Unlocking", fontWeight = FontWeight.Bold) }
                OutlinedButton(
                    onClick = { stopFlag = true; status = "Stopping..." }, enabled = busy,
                    modifier = Modifier.heightIn(min = 50.dp), shape = MaterialTheme.shapes.large
                ) { Text("■ Stop") }
            }

            Card(modifier = Modifier.fillMaxWidth(), shape = MaterialTheme.shapes.large) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("Progress & Status", fontWeight = FontWeight.SemiBold)
                    if (loading) LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                    else LinearProgressIndicator(progress = { progress }, modifier = Modifier.fillMaxWidth())
                    Text(status, fontSize = 13.sp)
                    if (running || tries > 0)
                        Text("Tries: $tries", fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }

            Text("Office (.docx/.xlsx/.pptx) only on Android for now. " +
                 "Use the desktop app for PDFs.",
                 fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }

    @Composable
    private fun SettingsDialog(
        themeMode: Int, keepAwake: Boolean, vibrate: Boolean,
        onThemeChange: (Int) -> Unit,
        onKeepAwakeChange: (Boolean) -> Unit,
        onVibrateChange: (Boolean) -> Unit,
        onClose: () -> Unit,
    ) {
        AlertDialog(
            onDismissRequest = onClose,
            confirmButton = { TextButton(onClick = onClose) { Text("Close") } },
            title = { Text("Settings") },
            text = {
                Column(
                    Modifier.verticalScroll(rememberScrollState()).selectableGroup(),
                    verticalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    Text("Theme", fontWeight = FontWeight.SemiBold)
                    listOf("System", "Light", "Dark").forEachIndexed { i, label ->
                        Row(modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)
                            .selectable(selected = themeMode == i, role = Role.RadioButton,
                                onClick = { onThemeChange(i) }),
                            verticalAlignment = Alignment.CenterVertically) {
                            RadioButton(selected = themeMode == i, onClick = null)
                            Spacer(Modifier.width(12.dp))
                            Text(label)
                        }
                    }
                    Spacer(Modifier.height(6.dp))
                    Text("Behaviour", fontWeight = FontWeight.SemiBold)
                    Row(verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)
                            .toggleable(value = keepAwake, role = Role.Switch, onValueChange = onKeepAwakeChange)) {
                        Text("Keep screen on while scanning", Modifier.weight(1f), fontSize = 14.sp)
                        Spacer(Modifier.width(12.dp))
                        Switch(checked = keepAwake, onCheckedChange = null)
                    }
                    Row(verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)
                            .toggleable(value = vibrate, role = Role.Switch, onValueChange = onVibrateChange)) {
                        Text("Vibrate when a run finishes", Modifier.weight(1f), fontSize = 14.sp)
                        Spacer(Modifier.width(12.dp))
                        Switch(checked = vibrate, onCheckedChange = null)
                    }
                    Spacer(Modifier.height(8.dp))
                    Text("About", fontWeight = FontWeight.SemiBold)
                    Text("Doc Unlocker  v${BuildConfig.VERSION_NAME}\n" +
                         "License: MIT (free to use, modify, sell)\n" +
                         "Author: Fallax Vision and contributors\n\n" +
                         "Office (.docx/.xlsx/.pptx) only on Android for now.",
                         fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        )
    }

    private fun keepScreenOn(on: Boolean) = runOnUiThread {
        if (on) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    }

    private fun doVibrate() {
        try {
            val vib = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                (getSystemService(VibratorManager::class.java)).defaultVibrator
            } else {
                @Suppress("DEPRECATION") getSystemService(Vibrator::class.java)
            }
            vib?.vibrate(VibrationEffect.createOneShot(220, VibrationEffect.DEFAULT_AMPLITUDE))
        } catch (e: Exception) { /* ignore */ }
    }

    private fun queryName(uri: Uri): String {
        var name = "document"
        contentResolver.query(uri, null, null, null, null)?.use { c ->
            val idx = c.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME)
            if (idx >= 0 && c.moveToFirst()) name = c.getString(idx)
        }
        return name.substringAfterLast('/').substringAfterLast('\\')
            .replace(Regex("[\\p{Cntrl}:*?\"<>|]"), "_").take(180).ifBlank { "document" }
    }

    private fun saveToDownloads(name: String, bytes: ByteArray): String {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                val values = ContentValues().apply {
                    put(MediaStore.Downloads.DISPLAY_NAME, name)
                    put(MediaStore.Downloads.MIME_TYPE, "application/octet-stream")
                    put(MediaStore.Downloads.IS_PENDING, 1)
                }
                val uri = contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
                    ?: error("Downloads is unavailable.")
                try {
                    contentResolver.openOutputStream(uri)?.use { it.write(bytes) }
                        ?: error("Could not write the unlocked copy.")
                    contentResolver.update(uri, ContentValues().apply {
                        put(MediaStore.Downloads.IS_PENDING, 0)
                    }, null, null)
                    "Downloads/$name"
                } catch (e: Exception) {
                    contentResolver.delete(uri, null, null)
                    throw e
                }
            } else {
                val dir = getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS)
                    ?: error("Downloads is unavailable.")
                dir.mkdirs()
                val f = File.createTempFile(name.substringBeforeLast('.').take(100) + "_", "." + name.substringAfterLast('.', "bin"), dir)
                try { f.writeBytes(bytes); f.absolutePath }
                catch (e: Exception) { f.delete(); throw e }
            }
    }
}
