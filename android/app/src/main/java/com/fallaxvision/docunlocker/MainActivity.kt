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
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
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
            var themeMode by remember { mutableIntStateOf(prefs.getInt("theme", 0)) }
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
        var progress by remember { mutableStateOf(0f) }
        var status by remember { mutableStateOf("Idle") }
        var tries by remember { mutableStateOf(0L) }
        var showSettings by remember { mutableStateOf(false) }
        var warnKind by remember { mutableStateOf<String?>(null) }   // "office"/"pdf"/"unsupported"

        val picker = rememberLauncherForActivityResult(
            ActivityResultContracts.OpenDocument()
        ) { uri: Uri? ->
            if (uri != null) {
                fileName = queryName(uri)
                fileBytes = contentResolver.openInputStream(uri)?.use { it.readBytes() }
            }
        }

        fun finishRun(msg: String) {
            running = false; status = msg
            keepScreenOn(false)
            if (vibrate) doVibrate()
        }

        fun beginCrack(force: Boolean) {
            val data = fileBytes ?: return
            stopFlag = false; running = true; progress = 0f; tries = 0
            status = "Reading..."
            keepScreenOn(keepAwake)
            scope.launch {
                val res = withContext(Dispatchers.Default) {
                    if (knownPw.isNotEmpty() && Cracker.unlock(data, knownPw) != null)
                        return@withContext "ok:$knownPw"
                    val total = Cracker.estimate(maxDigits).coerceAtLeast(1)
                    var n = 0L
                    for (cand in Cracker.candidates(maxDigits)) {
                        if (stopFlag) return@withContext "stopped"
                        n++
                        if (n % 25L == 0L) {
                            tries = n; progress = (n.toFloat() / total).coerceIn(0f, 1f)
                        }
                        if (Cracker.test(data, cand)) return@withContext "ok:$cand"
                    }
                    "nofound"
                }
                when {
                    res == "stopped" -> finishRun("Stopped.")
                    res == "nofound" -> finishRun("Not found. Try a longer PIN length.")
                    res.startsWith("ok:") -> {
                        val pw = res.removePrefix("ok:")
                        val plain = withContext(Dispatchers.Default) { Cracker.unlock(data, pw) }
                        if (plain != null) {
                            progress = 1f
                            val out = "Unlocked_" + fileName.ifBlank { "document" }
                            val where = saveToDownloads(out, plain)
                            finishRun("Found: $pw\nSaved: $where")
                        } else finishRun("Not found.")
                    }
                    else -> finishRun("Error.")
                }
            }
        }

        fun onStart() {
            val data = fileBytes
            if (data == null) { status = "Pick a document first."; return }
            val lower = fileName.lowercase()
            val office = OFFICE_EXTS.any { lower.endsWith(it) }
            if (!office) { warnKind = if (lower.endsWith(".pdf")) "pdf" else "unsupported"; return }
            if (!Cracker.isEncrypted(data)) { warnKind = "office"; return }
            beginCrack(false)
        }

        // ---- dialogs ----
        if (showSettings) {
            SettingsDialog(themeMode, keepAwake, vibrate,
                onThemeChange, onKeepAwakeChange, onVibrateChange) { showSettings = false }
        }
        warnKind?.let { kind ->
            val msg = when (kind) {
                "pdf" -> "PDFs aren't supported on Android yet — use the desktop app. " +
                    "(To check it, open the PDF in Acrobat Reader or your browser.) Continue anyway?"
                "unsupported" -> "Unsupported file type. The Android app handles Word, Excel and " +
                    "PowerPoint. Open it in an app built for that format first. Continue anyway?"
                else -> "This file doesn't look encrypted. Try opening it first in Word / Excel / " +
                    "PowerPoint, Google Docs, or WPS Office — it may open with no password. " +
                    "Continue anyway?"
            }
            AlertDialog(
                onDismissRequest = { warnKind = null },
                title = { Text("Heads up") },
                text = { Text(msg, fontSize = 14.sp) },
                confirmButton = {
                    TextButton(onClick = { warnKind = null; beginCrack(true) }) {
                        Text("Continue anyway", color = MaterialTheme.colorScheme.error)
                    }
                },
                dismissButton = {
                    TextButton(onClick = { warnKind = null }) { Text("Cancel") }
                }
            )
        }

        val scroll = rememberScrollState()
        Column(
            Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.systemBars)
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

            Card(shape = MaterialTheme.shapes.large) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("Locked document", fontWeight = FontWeight.SemiBold)
                    Text(if (fileName.isBlank()) "No file selected" else fileName,
                        color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 13.sp)
                    Button(
                        onClick = {
                            picker.launch(arrayOf(
                                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                "application/octet-stream", "application/*", "*/*"))
                        },
                        enabled = !running, shape = MaterialTheme.shapes.large
                    ) { Text("📁  Choose document") }
                }
            }

            Card(shape = MaterialTheme.shapes.large) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("Options", fontWeight = FontWeight.SemiBold)
                    OutlinedTextField(
                        value = knownPw, onValueChange = { knownPw = it },
                        label = { Text("Known password (optional)") },
                        singleLine = true, enabled = !running,
                        visualTransformation = PasswordVisualTransformation(),
                        modifier = Modifier.fillMaxWidth(), shape = MaterialTheme.shapes.large
                    )
                    Text("Try numeric PINs up to: $maxDigits digits", fontSize = 13.sp)
                    Slider(
                        value = maxDigits.toFloat(), onValueChange = { maxDigits = it.toInt() },
                        valueRange = 1f..8f, steps = 6, enabled = !running
                    )
                }
            }

            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Button(
                    onClick = { onStart() }, enabled = !running,
                    modifier = Modifier.weight(1f).height(50.dp), shape = MaterialTheme.shapes.large
                ) { Text("▶  Start Unlocking", fontWeight = FontWeight.Bold) }
                OutlinedButton(
                    onClick = { stopFlag = true }, enabled = running,
                    modifier = Modifier.height(50.dp), shape = MaterialTheme.shapes.large
                ) { Text("■ Stop") }
            }

            Card(shape = MaterialTheme.shapes.large) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("Progress & Status", fontWeight = FontWeight.SemiBold)
                    LinearProgressIndicator(progress = { progress }, modifier = Modifier.fillMaxWidth())
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
                    Modifier.verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    Text("Theme", fontWeight = FontWeight.SemiBold)
                    listOf("System", "Light", "Dark").forEachIndexed { i, label ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            RadioButton(selected = themeMode == i, onClick = { onThemeChange(i) })
                            Text(label)
                        }
                    }
                    Spacer(Modifier.height(6.dp))
                    Text("Behaviour", fontWeight = FontWeight.SemiBold)
                    Row(verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.fillMaxWidth()) {
                        Text("Keep screen on while scanning", Modifier.weight(1f), fontSize = 14.sp)
                        Switch(checked = keepAwake, onCheckedChange = onKeepAwakeChange)
                    }
                    Row(verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.fillMaxWidth()) {
                        Text("Vibrate when a run finishes", Modifier.weight(1f), fontSize = 14.sp)
                        Switch(checked = vibrate, onCheckedChange = onVibrateChange)
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
        return name
    }

    private fun saveToDownloads(name: String, bytes: ByteArray): String {
        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                val values = ContentValues().apply {
                    put(MediaStore.Downloads.DISPLAY_NAME, name)
                    put(MediaStore.Downloads.MIME_TYPE, "application/octet-stream")
                }
                val uri = contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
                contentResolver.openOutputStream(uri!!)!!.use { it.write(bytes) }
                "Downloads/$name"
            } else {
                val dir = getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS)
                val f = File(dir, name); f.writeBytes(bytes); f.absolutePath
            }
        } catch (e: Exception) {
            val f = File(getExternalFilesDir(null), name); f.writeBytes(bytes); f.absolutePath
        }
    }
}
