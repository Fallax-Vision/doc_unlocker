package com.fallaxvision.docunlocker

import android.content.ContentValues
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.provider.MediaStore
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
import androidx.compose.runtime.saveable.rememberSaveable
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

// Theme modes: 0 = System, 1 = Light, 2 = Dark
class MainActivity : ComponentActivity() {
    @Volatile private var stopFlag = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            var themeMode by rememberSaveable { mutableStateOf(0) }
            val dark = when (themeMode) {
                1 -> false
                2 -> true
                else -> isSystemInDarkTheme()
            }
            MaterialTheme(colorScheme = if (dark) darkScheme() else lightScheme()) {
                Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    AppScreen(themeMode) { themeMode = it }
                }
            }
        }
    }

    @Composable
    private fun AppScreen(themeMode: Int, onThemeChange: (Int) -> Unit) {
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

        val picker = rememberLauncherForActivityResult(
            ActivityResultContracts.OpenDocument()
        ) { uri: Uri? ->
            if (uri != null) {
                fileName = queryName(uri)
                fileBytes = contentResolver.openInputStream(uri)?.use { it.readBytes() }
            }
        }

        fun finishRun(msg: String) { running = false; status = msg }

        fun onResult(pw: String?, plain: ByteArray?) {
            if (pw != null && plain != null) {
                val out = "Unlocked_" + (fileName.ifBlank { "document" })
                val where = saveToDownloads(out, plain)
                finishRun("Found: $pw\nSaved: $where")
            }
        }

        fun start() {
            val data = fileBytes
            if (data == null) { status = "Pick a document first."; return }
            stopFlag = false; running = true; progress = 0f; tries = 0
            status = "Reading..."
            scope.launch {
                val res = withContext(Dispatchers.Default) {
                    if (!Cracker.isEncrypted(data)) return@withContext "notenc"
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
                    res == "notenc" -> finishRun("This file is not password-protected.")
                    res == "stopped" -> finishRun("Stopped.")
                    res == "nofound" -> finishRun("Not found. Try a longer PIN length.")
                    res.startsWith("ok:") -> {
                        val pw = res.removePrefix("ok:")
                        val plain = withContext(Dispatchers.Default) { Cracker.unlock(data, pw) }
                        progress = 1f
                        onResult(pw, plain)
                    }
                    else -> finishRun("Error.")
                }
            }
        }

        if (showSettings) {
            SettingsDialog(themeMode, onThemeChange) { showSettings = false }
        }

        val scroll = rememberScrollState()
        Column(
            Modifier
                .fillMaxSize()
                .windowInsetsPadding(WindowInsets.systemBars)   // stay clear of status/nav bars
                .verticalScroll(scroll)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            // Header: app icon + title on the left, theme + settings on the right.
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
                TextButton(onClick = { onThemeChange((themeMode + 1) % 3) }) {
                    Text(when (themeMode) { 1 -> "Light"; 2 -> "Dark"; else -> "System" })
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
                    onClick = { start() }, enabled = !running,
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
                    LinearProgressIndicator(
                        progress = { progress }, modifier = Modifier.fillMaxWidth())
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
    private fun SettingsDialog(themeMode: Int, onThemeChange: (Int) -> Unit, onClose: () -> Unit) {
        AlertDialog(
            onDismissRequest = onClose,
            confirmButton = { TextButton(onClick = onClose) { Text("Close") } },
            title = { Text("Settings") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("Theme", fontWeight = FontWeight.SemiBold)
                    listOf("System", "Light", "Dark").forEachIndexed { i, label ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            RadioButton(selected = themeMode == i,
                                onClick = { onThemeChange(i) })
                            Text(label)
                        }
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
                val uri = contentResolver.insert(
                    MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
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
