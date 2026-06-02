#!/usr/bin/env python3
"""
Doc Unlocker - Password Recovery
================================

A friendly desktop tool to recover the password of a Microsoft Office document
*you own* (e.g. you forgot your own password). It tries smart guesses on the
CPU and can offload a real brute-force attack to your GPU via Hashcat.

This is a legitimate password-RECOVERY tool for your own files. Please do not
use it on documents you are not authorised to access.

Project: https://github.com/Fallax-Vision/doc_unlocker
License: MIT

Note: currently focused on Word documents; future versions will add PDF, Excel,
PowerPoint and other document types.
"""

from __future__ import annotations

__version__ = "1.0.1"
__app_name__ = "Doc Unlocker"

import io
import os
import sys
import glob
import time
import queue
import base64
import shutil
import threading
import itertools
import subprocess
import datetime
import urllib.request
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog


# ---------------------------------------------------------------------------
# Dependency bootstrap: install + import the two libraries we rely on.
# ---------------------------------------------------------------------------
def _pip_install(package):
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--user", package]
    )


def ensure_dependencies():
    missing = []
    try:
        import msoffcrypto  # noqa: F401
    except ImportError:
        missing.append("msoffcrypto-tool")
    try:
        import olefile  # noqa: F401
    except ImportError:
        missing.append("olefile")
    try:
        import pypdf  # noqa: F401  (PDF support)
    except ImportError:
        missing.append("pypdf")
    if not missing:
        return True

    root = tk.Tk()
    root.withdraw()
    ok = messagebox.askyesno(
        f"{__app_name__} - one-time setup",
        "The following free libraries are required and not installed yet:\n\n"
        f"   {', '.join(missing)}\n\n"
        "Install them now? (needs an internet connection)",
    )
    root.destroy()
    if not ok:
        return False
    try:
        for pkg in missing:
            _pip_install(pkg)
        import msoffcrypto  # noqa: F401
        import olefile      # noqa: F401
        import pypdf        # noqa: F401
        return True
    except Exception as exc:  # pragma: no cover
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror(
            "Setup failed",
            "Could not install the dependencies automatically.\n\n"
            "Open a terminal and run:\n\n"
            f'    "{sys.executable}" -m pip install msoffcrypto-tool olefile pypdf\n\n'
            f"Details: {exc}",
        )
        r.destroy()
        return False


if not ensure_dependencies():
    sys.exit(1)

import olefile
import msoffcrypto
import pypdf


# ===========================================================================
#  PASSWORD CANDIDATE GENERATION
#  (Generic, common keywords only - no personal data.)
# ===========================================================================

# Phase 0: the most obvious guesses, tried verbatim (no mutation) first.
PRIORITY_GUESSES = [
    # trivial numerics / keyboard walks
    "123", "1234", "12345", "123456", "1234567", "12345678", "123456789",
    "1234567890", "0000", "00000", "000000", "1111", "111111", "121212",
    "112233", "123123", "654321", "666666", "abcabc", "qwerty", "azerty",
    "qwertyuiop", "azertyuiop", "asdfgh", "zxcvbn", "1q2w3e4r",
    # ubiquitous words
    "password", "Password", "Password1", "Password1!", "passw0rd", "P@ssw0rd",
    "motdepasse", "contraseña", "passwort", "secret", "admin", "administrator",
    "welcome", "Welcome1", "letmein", "login", "master", "root", "default",
    "changeme", "test", "test123", "guest", "user", "office", "document",
    "word", "iloveyou", "dragon", "monkey", "sunshine", "princess", "football",
    "superman", "batman", "shadow", "michael", "jordan", "hello", "freedom",
    "whatever", "trustno1", "starwars",
    # years on their own
    "2020", "2021", "2022", "2023", "2024", "2025", "2026",
]

# A large set of the world's most common passwords (verbatim, mutated too).
COMMON_PASSWORDS = [
    "password", "123456", "123456789", "12345678", "12345", "1234567",
    "1234567890", "qwerty", "azerty", "abc123", "111111", "123123", "000000",
    "iloveyou", "1234", "1q2w3e4r", "qwertyuiop", "123", "monkey", "dragon",
    "letmein", "welcome", "login", "admin", "princess", "solo", "passw0rd",
    "starwars", "master", "hello", "freedom", "whatever", "qazwsx", "trustno1",
    "654321", "superman", "1qaz2wsx", "7777777", "121212", "000000", "qwerty123",
    "1q2w3e", "zaq12wsx", "dragon", "sunshine", "letmein", "football", "iloveyou",
    "aa123456", "donald", "password1", "qwerty1", "123qwe", "123abc", "11111111",
    "michael", "shadow", "jennifer", "jordan", "hunter", "fuckyou", "2000",
    "test", "batman", "thomas", "tigger", "robert", "access", "love", "buster",
    "soccer", "hockey", "killer", "george", "sexy", "andrew", "charlie",
    "superman", "asshole", "fuckme", "dallas", "jessica", "panties", "pepper",
    "1111", "austin", "william", "daniel", "golfer", "summer", "heather",
    "hammer", "yankees", "joshua", "maggie", "biteme", "enter", "ashley",
    "thunder", "cowboy", "silver", "richard", "orange", "merlin", "michelle",
    "corvette", "bigdog", "cheese", "matthew", "121212", "patrick", "martin",
    "freedom", "ginger", "blowjob", "nicole", "sparky", "yellow", "camaro",
]

# Generic dictionary / name / place words used as mutation bases. Multilingual
# but NOT personal - just common globally-used words and popular names.
COMMON_WORDS = [
    # English / global common words
    "love", "money", "family", "freedom", "hello", "world", "happy", "sunshine",
    "flower", "summer", "winter", "spring", "autumn", "secret", "magic", "angel",
    "heaven", "dream", "star", "moon", "ocean", "river", "mountain", "forest",
    "coffee", "music", "guitar", "soccer", "football", "computer", "internet",
    "company", "office", "school", "student", "teacher", "doctor", "engineer",
    # French
    "bonjour", "amour", "soleil", "liberte", "famille", "maison", "fleur",
    "etoile", "lumiere", "paix", "victoire", "courage", "espoir", "merci",
    # Spanish
    "hola", "amor", "familia", "fuego", "estrella", "libertad", "corazon",
    "futbol", "verano", "flores", "manana",
    # Portuguese / Italian
    "amore", "famiglia", "sole", "amigo", "saudade", "felicidade",
    # popular international given names
    "alex", "maria", "john", "anna", "david", "sarah", "james", "laura",
    "daniel", "sofia", "lucas", "emma", "michael", "elena", "thomas", "julia",
    "peter", "marie", "paul", "lucia", "andre", "grace", "samuel", "rachel",
    "joseph", "esther", "isaac", "ruth", "moses", "naomi",
    # faith / hope words (very common in passwords worldwide)
    "jesus", "god", "amen", "faith", "grace", "blessing", "hope", "peace",
    # places / things
    "paris", "london", "tokyo", "africa", "europe", "america", "ferrari",
    "chelsea", "arsenal", "barcelona", "liverpool",
]

# Numbers / years / symbols appended during mutation.
MUTATION_SUFFIXES = [
    "", "1", "12", "123", "1234", "12345", "123456", "0", "00", "01", "07",
    "007", "777", "143", "69",
    "2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026",
    "2027",
    "!", "@", "#", "$", ".", "*", "?", "..", "!!", "_",
    "1!", "12!", "123!", "2023!", "2024!", "2025!", "2026!", "@123", "1234!",
    "2025@", "2026@", "#1",
]

# A few symbol/number PREFIXES (some people prefix instead of suffix).
MUTATION_PREFIXES = ["", "@", "#", "_", "1", "2025", "2026"]

# Light leetspeak substitutions, applied as extra base variants.
LEET_MAP = str.maketrans({"a": "@", "e": "3", "i": "1", "o": "0", "s": "5"})

# Suffixes appended to two-word combos (kept short to bound the explosion).
COMBO_SUFFIXES = ["", "1", "123", "2023", "2024", "2025", "2026", "!", "2025!"]

# Glue characters tried between two words.
COMBO_SEPARATORS = ["", ".", "_", "-"]

# Year range used by the date-pattern generator.
DATE_YEAR_START = 1960
DATE_YEAR_END = 2026

# Up to 8 base forms per word, each combined with suffixes + non-empty prefixes.
_MUTATION_FACTOR = 8 * (len(MUTATION_SUFFIXES) + len(MUTATION_PREFIXES) - 1)


def mutate(word):
    """Yield deduplicated case/number/symbol/leet variants of a base word."""
    seen = set()
    base_forms = {
        word, word.lower(), word.upper(), word.capitalize(),
        word.swapcase(), word.title(),
    }
    base_forms.add(word.lower().translate(LEET_MAP))
    base_forms.add(word.capitalize().translate(LEET_MAP))
    for base in base_forms:
        for suffix in MUTATION_SUFFIXES:
            cand = base + suffix
            if cand and cand not in seen:
                seen.add(cand)
                yield cand
        for prefix in MUTATION_PREFIXES:
            if not prefix:
                continue
            cand = prefix + base
            if cand not in seen:
                seen.add(cand)
                yield cand


def twoword_combos(words):
    """Yield Word+Word combinations (e.g. LoveMoney, Love.Money2024)."""
    seen = set()
    forms = [w.capitalize() for w in words]
    for a in forms:
        for b in forms:
            for sep in COMBO_SEPARATORS:
                stem = a + sep + b
                for suffix in COMBO_SUFFIXES:
                    cand = stem + suffix
                    if cand not in seen:
                        seen.add(cand)
                        yield cand


def date_combos(words):
    """Yield word+date patterns (e.g. Love1990, Love1990!, Love0101)."""
    seen = set()
    common_dm = ["0101", "3112", "0712", "2512", "1407"]
    for w in words:
        for base in {w.capitalize(), w.lower()}:
            for year in range(DATE_YEAR_START, DATE_YEAR_END + 1):
                for cand in (f"{base}{year}", f"{base}{year}!"):
                    if cand not in seen:
                        seen.add(cand)
                        yield cand
            for dm in common_dm:
                cand = f"{base}{dm}"
                if cand not in seen:
                    seen.add(cand)
                    yield cand


def _read_lines(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if line:
                yield line


def build_candidates(wordlist_path, digit_len, use_mutations, use_twoword,
                     use_dates):
    """
    Return (iterator_of_passwords, total_count_estimate).

    Order: Phase-0 obvious guesses -> common words/passwords (mutated) ->
    optional date patterns -> optional two-word combos -> user wordlist ->
    numeric PINs.
    """
    base_words = COMMON_WORDS
    if wordlist_path:
        user_count = sum(1 for _ in _read_lines(wordlist_path))
    else:
        user_count = 0
    word_sources_count = (
        len(base_words) + len(COMMON_PASSWORDS) + user_count
    )

    years = DATE_YEAR_END - DATE_YEAR_START + 1
    per_word_dates = 2 * years * 2 + 2 * 5

    total = len(PRIORITY_GUESSES)
    total += word_sources_count * (_MUTATION_FACTOR if use_mutations else 1)
    if use_dates:
        total += len(base_words) * per_word_dates
    if use_twoword:
        total += (len(base_words) ** 2) * len(COMBO_SEPARATORS) * len(COMBO_SUFFIXES)
    for n in range(1, digit_len + 1):
        total += 10 ** n

    def gen():
        def emit(word):
            if use_mutations:
                yield from mutate(word)
            else:
                yield word

        for pw in PRIORITY_GUESSES:
            yield pw
        for word in base_words:
            yield from emit(word)
        if use_dates:
            yield from date_combos(base_words)
        if use_twoword:
            yield from twoword_combos(base_words)
        if wordlist_path:
            for word in _read_lines(wordlist_path):
                yield from emit(word)
        for word in COMMON_PASSWORDS:
            yield from emit(word)
        for n in range(1, digit_len + 1):
            for combo in itertools.product("0123456789", repeat=n):
                yield "".join(combo)

    return gen(), total


# ===========================================================================
#  TESTED-LIST (resume) helpers
# ===========================================================================
def tested_path_for(doc_path):
    folder = os.path.dirname(doc_path)
    name = os.path.basename(doc_path)
    return os.path.join(folder, name + ".tested.txt")


def load_tested(doc_path):
    path = tested_path_for(doc_path)
    tried = set()
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.rstrip("\r\n")
                    if line:
                        tried.add(line)
        except Exception:
            pass
    return tried


def append_tested(doc_path, passwords):
    if not passwords:
        return tested_path_for(doc_path)
    path = tested_path_for(doc_path)
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(passwords) + "\n")
    except Exception:
        pass
    return path


# ===========================================================================
#  OFFICE HASH EXTRACTION + VERIFICATION
# ===========================================================================
def app_dir():
    if getattr(sys, "frozen", False):           # running as PyInstaller exe
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(*parts):
    """Locate a bundled resource (works in dev and inside the PyInstaller exe)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


_AGILE_NS = {
    "d": "http://schemas.microsoft.com/office/2006/encryption",
    "p": "http://schemas.microsoft.com/office/2006/keyEncryptor/password",
}


def _office_hash_from_encryptioninfo(data):
    """Build the Hashcat -m 9600 hash from EncryptionInfo bytes (2013 agile)."""
    if len(data) < 8:
        raise RuntimeError("EncryptionInfo stream is too short.")
    v_major = int.from_bytes(data[0:2], "little")
    v_minor = int.from_bytes(data[2:4], "little")
    if (v_major, v_minor) != (4, 4):
        raise RuntimeError(
            f"This file uses older/standard encryption (version {v_major}."
            f"{v_minor}), not 2013+ agile (AES/SHA-512). Use John the Ripper."
        )
    xml = data[8:].decode("utf-8", errors="ignore")
    root = ET.fromstring(xml)
    enc = root.find("d:keyEncryptors/d:keyEncryptor/p:encryptedKey", _AGILE_NS)
    if enc is None:
        raise RuntimeError("No password key-encryptor found in EncryptionInfo.")
    spin = enc.get("spinCount")
    key_bits = enc.get("keyBits")
    salt_size = enc.get("saltSize")
    salt = base64.b64decode(enc.get("saltValue")).hex()
    verifier_in = base64.b64decode(enc.get("encryptedVerifierHashInput")).hex()
    # Hashcat -m 9600 expects only the first 32 bytes (64 hex) of the value.
    verifier_val = base64.b64decode(enc.get("encryptedVerifierHashValue"))[:32].hex()
    return (
        f"$office$*2013*{spin}*{key_bits}*{salt_size}*"
        f"{salt}*{verifier_in}*{verifier_val}"
    )


def extract_office_hash(doc_path):
    """Return the Hashcat $office$ hash for a password-protected OOXML file."""
    if not olefile.isOleFile(doc_path):
        raise RuntimeError(
            "This is not an encrypted Office file (no OLE container). "
            "Only password-protected .docx/.xlsx/.pptx are supported."
        )
    ole = olefile.OleFileIO(doc_path)
    try:
        if not ole.exists("EncryptionInfo"):
            raise RuntimeError("No 'EncryptionInfo' stream - file is not encrypted.")
        data = ole.openstream("EncryptionInfo").read()
    finally:
        ole.close()
    return _office_hash_from_encryptioninfo(data)


# Magic bytes of a successfully decrypted Office document.
_OFFICE_MAGIC = (b"PK\x03\x04", b"\xd0\xcf\x11\xe0")


def detect_kind(path):
    """Return 'pdf' or 'office' based on the file extension."""
    return "pdf" if os.path.splitext(path)[1].lower() == ".pdf" else "office"


def is_protected(file_bytes, kind):
    """True if the document is password/encryption protected."""
    try:
        if kind == "pdf":
            return pypdf.PdfReader(io.BytesIO(file_bytes)).is_encrypted
        return msoffcrypto.OfficeFile(io.BytesIO(file_bytes)).is_encrypted()
    except Exception:
        return False


# --- Office ---------------------------------------------------------------
def _office_decrypt_bytes(file_bytes, password):
    office = msoffcrypto.OfficeFile(io.BytesIO(file_bytes))
    office.load_key(password=password)
    out = io.BytesIO()
    office.decrypt(out)
    return out.getvalue()


# --- PDF ------------------------------------------------------------------
def _pdf_reader(file_bytes):
    return pypdf.PdfReader(io.BytesIO(file_bytes))


def _pdf_test(file_bytes, password):
    reader = _pdf_reader(file_bytes)
    if not reader.is_encrypted:
        return True
    # decrypt() returns 0/NOT_DECRYPTED on failure, non-zero on success.
    return int(reader.decrypt(password)) != 0


def _pdf_decrypt_to(file_bytes, password, out_path):
    reader = _pdf_reader(file_bytes)
    if reader.is_encrypted and int(reader.decrypt(password)) == 0:
        raise RuntimeError("Wrong password for this PDF.")
    writer = pypdf.PdfWriter()
    writer.append(reader)
    with open(out_path, "wb") as f:
        writer.write(f)


# --- unified dispatch -----------------------------------------------------
def test_password(file_bytes, password, kind="office"):
    """True if `password` opens the document (Office or PDF)."""
    try:
        if kind == "pdf":
            return _pdf_test(file_bytes, password)
        head = _office_decrypt_bytes(file_bytes, password)[:4]
        return head.startswith(_OFFICE_MAGIC)
    except Exception:
        return False


def decrypt_to(file_bytes, password, out_path, kind="office"):
    if kind == "pdf":
        _pdf_decrypt_to(file_bytes, password, out_path)
        return
    data = _office_decrypt_bytes(file_bytes, password)
    if not data[:4].startswith(_OFFICE_MAGIC):
        raise RuntimeError("Decryption produced invalid output (wrong password).")
    with open(out_path, "wb") as out:
        out.write(data)


def write_log(folder, doc_path, password, tries, out_path):
    log_path = os.path.join(folder, "DocUnlocker_found.log")
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = (f"[{stamp}] file={doc_path!r} password={password!r} "
            f"tries={tries} unlocked={out_path!r}\n")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        log_path = os.path.join(os.environ.get("TEMP", folder),
                                "DocUnlocker_found.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
    return log_path


# ===========================================================================
#  HASHCAT INTEGRATION
# ===========================================================================
def _no_window():
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def find_hashcat():
    found = shutil.which("hashcat") or shutil.which("hashcat.exe")
    if found:
        return found
    for cand in glob.glob(os.path.join(app_dir(), "hashcat*", "hashcat.exe")):
        return cand
    for base in (r"C:\hashcat", r"C:\Tools\hashcat", r"C:\Program Files\hashcat"):
        cand = os.path.join(base, "hashcat.exe")
        if os.path.isfile(cand):
            return cand
    return None


HASHCAT_VERSION = "6.2.6"
HASHCAT_URL = f"https://hashcat.net/files/hashcat-{HASHCAT_VERSION}.7z"


def extract_7z(archive, dest_dir):
    """Extract a .7z using bsdtar (built into Windows), 7-Zip, or py7zr."""
    errors = []
    tar = shutil.which("tar")
    if tar:
        r = subprocess.run([tar, "-xf", archive, "-C", dest_dir],
                           capture_output=True, text=True,
                           creationflags=_no_window())
        if r.returncode == 0:
            return
        errors.append("tar: " + (r.stderr or "").strip()[:200])
    sevenzip = (shutil.which("7z") or shutil.which("7za") or next(
        (p for p in (r"C:\Program Files\7-Zip\7z.exe",
                     r"C:\Program Files (x86)\7-Zip\7z.exe")
         if os.path.isfile(p)), None))
    if sevenzip:
        r = subprocess.run([sevenzip, "x", "-y", f"-o{dest_dir}", archive],
                           capture_output=True, text=True,
                           creationflags=_no_window())
        if r.returncode == 0:
            return
        errors.append("7zip: " + (r.stderr or "").strip()[:200])
    try:
        import py7zr
        with py7zr.SevenZipFile(archive, "r") as z:
            z.extractall(dest_dir)
        return
    except ImportError:
        errors.append("py7zr: not installed")
    except Exception as exc:
        errors.append("py7zr: " + str(exc)[:200])
    raise RuntimeError("Could not extract the .7z archive.\n" + "\n".join(errors))


def download_hashcat(progress_cb=None):
    existing = find_hashcat()
    if existing:
        return existing
    dest_dir = app_dir()
    archive = os.path.join(dest_dir, f"hashcat-{HASHCAT_VERSION}.7z")
    if not (os.path.isfile(archive) and os.path.getsize(archive) > 5_000_000):
        def _hook(block_num, block_size, total_size):
            if progress_cb:
                progress_cb(block_num * block_size, total_size)
        urllib.request.urlretrieve(HASHCAT_URL, archive, _hook)
    extract_7z(archive, dest_dir)
    try:
        os.remove(archive)
    except OSError:
        pass
    exe = find_hashcat()
    if not exe:
        raise RuntimeError("Extracted Hashcat but could not find hashcat.exe.")
    return exe


def decode_hashcat_plain(s):
    if s.startswith("$HEX[") and s.endswith("]"):
        raw = bytes.fromhex(s[5:-1])
        for enc in ("utf-8", "latin-1"):
            try:
                return raw.decode(enc)
            except Exception:
                continue
    return s


def read_cracked_password(hash_str, cracked_file, potfile):
    if cracked_file and os.path.isfile(cracked_file):
        with open(cracked_file, encoding="utf-8", errors="ignore") as f:
            line = f.readline().rstrip("\r\n")
        if line:
            return decode_hashcat_plain(line)
    if potfile and os.path.isfile(potfile):
        with open(potfile, encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.rstrip("\r\n")
                if line.startswith(hash_str + ":"):
                    return decode_hashcat_plain(line[len(hash_str) + 1:])
    return None


def format_duration(seconds):
    if seconds is None or seconds != seconds or seconds < 0:
        return "?"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m}m {s:02d}s"
    h, m = divmod(m, 60)
    if h < 24:
        return f"{h}h {m:02d}m"
    d, h = divmod(h, 24)
    return f"{d}d {h}h"


# ===========================================================================
#  THEMING
# ===========================================================================
THEMES = {
    "light": {
        "bg": "#eef1f7", "card": "#ffffff", "card_border": "#e2e6ef",
        "text": "#1f2430", "muted": "#6b7280", "title": "#111827",
        "entry_bg": "#f4f6fb", "entry_fg": "#1f2430", "entry_border": "#d7dce8",
        "accent": "#2f6df6", "accent_fg": "#ffffff",
        "purple": "#7c3aed", "purple_fg": "#ffffff",
        "ghost_bg": "#ffffff", "ghost_fg": "#1f2430", "ghost_border": "#dfe3ec",
        "track": "#e5e9f2", "bar": "#2f6df6",
    },
    "dark": {
        "bg": "#0b0f17", "card": "#121826", "card_border": "#1f2937",
        "text": "#e6edf3", "muted": "#9aa4b2", "title": "#f3f6fb",
        "entry_bg": "#0e1422", "entry_fg": "#e6edf3", "entry_border": "#283143",
        "accent": "#3b82f6", "accent_fg": "#ffffff",
        "purple": "#8b5cf6", "purple_fg": "#ffffff",
        "ghost_bg": "#121826", "ghost_fg": "#e6edf3", "ghost_border": "#283143",
        "track": "#1b2333", "bar": "#3b82f6",
    },
}


def system_theme():
    """Return 'light' or 'dark' from the Windows app theme (default light)."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return "light" if val == 1 else "dark"
    except Exception:
        return "light"


# ===========================================================================
#  GUI
# ===========================================================================
class App:
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.stop_flag = threading.Event()
        self.worker = None
        self.gpu_thread = None
        self.hc_thread = None
        self.hc_run_thread = None
        self.hc_proc = None
        self._pump_active = False
        self.theme_mode = tk.StringVar(value="system")
        self._widgets = []          # (widget, role) for re-theming
        self._cards = []

        root.title(f"{__app_name__} - Password Recovery  v{__version__}")
        root.geometry("960x660")
        root.minsize(880, 620)
        self._set_window_icon(root)

        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        self._build_ui()
        self.apply_theme()

    # ---- widget registration (for theming) ---------------------------
    def _reg(self, widget, role):
        self._widgets.append((widget, role))
        return widget

    def _set_window_icon(self, root):
        """
        Set the window/taskbar icon. On Windows the taskbar uses the .ico via
        iconbitmap(default=...) once an explicit AppUserModelID is set (done in
        main() before the window is created). A .png is used as a cross-platform
        fallback. A reference to the PhotoImage is kept so it is not GC'd.
        """
        ico = resource_path("assets", "icon.ico")
        if os.path.isfile(ico):
            try:
                # default=... applies to this window and every future toplevel.
                root.iconbitmap(default=ico)
            except Exception:
                pass
        png = resource_path("assets", "icon.png")
        if os.path.isfile(png):
            try:
                self._icon_img = tk.PhotoImage(file=png)
                root.iconphoto(True, self._icon_img)
            except Exception:
                pass

    # ---- UI construction ---------------------------------------------
    def _build_ui(self):
        self.outer = tk.Frame(self.root)
        self.outer.pack(fill="both", expand=True)
        self._reg(self.outer, "bg")

        # Header ---------------------------------------------------------
        header = tk.Frame(self.outer)
        header.pack(fill="x", padx=18, pady=(14, 6))
        self._reg(header, "bg")
        self.title_lbl = tk.Label(header, text=f"🔑  {__app_name__}",
                                  font=("Segoe UI Semibold", 16))
        self.title_lbl.pack(side="left")
        self._reg(self.title_lbl, "title")
        self.sub_lbl = tk.Label(header, text=f"Password Recovery  ·  v{__version__}",
                                font=("Segoe UI", 10))
        self.sub_lbl.pack(side="left", padx=(10, 0), pady=(4, 0))
        self._reg(self.sub_lbl, "muted")

        theme_box = tk.Frame(header)
        theme_box.pack(side="right")
        self._reg(theme_box, "bg")
        tl = tk.Label(theme_box, text="Theme:", font=("Segoe UI", 10))
        tl.pack(side="left", padx=(0, 6))
        self._reg(tl, "muted")
        self.theme_menu = ttk.Combobox(
            theme_box, width=9, state="readonly", textvariable=self.theme_mode,
            values=["system", "light", "dark"])
        self.theme_menu.pack(side="left")
        self.theme_menu.bind("<<ComboboxSelected>>", lambda e: self.apply_theme())

        # Body: left main column + right utilities column ---------------
        body = tk.Frame(self.outer)
        body.pack(fill="both", expand=True, padx=18, pady=6)
        self._reg(body, "bg")

        left = tk.Frame(body)
        left.pack(side="left", fill="both", expand=True)
        self._reg(left, "bg")

        right = tk.Frame(body)
        right.pack(side="right", fill="y", padx=(14, 0))
        self._reg(right, "bg")

        self._build_inputs_card(left)
        self._build_options_card(left)
        self._build_action_card(left)
        self._build_utilities_card(right)
        self._build_status_card(self.outer)

    def _card(self, parent, title=None, icon=""):
        card = tk.Frame(parent, highlightthickness=1, bd=0)
        self._reg(card, "card")
        self._cards.append(card)
        if title:
            head = tk.Label(card, text=f"{icon}  {title}".strip(),
                            font=("Segoe UI Semibold", 11), anchor="w")
            head.pack(fill="x", padx=16, pady=(12, 2))
            self._reg(head, "title")
        return card

    def _entry(self, parent):
        e = tk.Entry(parent, font=("Segoe UI", 10), relief="flat",
                     highlightthickness=1, insertwidth=1)
        self._reg(e, "entry")
        return e

    def _ghost_button(self, parent, text, command, icon=""):
        b = tk.Button(parent, text=f"{icon}  {text}".strip(), command=command,
                      font=("Segoe UI", 10), relief="flat", bd=0, cursor="hand2",
                      anchor="w", padx=14, pady=9)
        self._reg(b, "ghost")
        return b

    def _build_inputs_card(self, parent):
        card = self._card(parent)
        card.pack(fill="x", pady=(0, 12))

        lbl = tk.Label(card, text="Locked document (full path)",
                       font=("Segoe UI", 10), anchor="w")
        lbl.pack(fill="x", padx=16, pady=(14, 4)); self._reg(lbl, "text")
        row = tk.Frame(card); row.pack(fill="x", padx=16); self._reg(row, "card")
        self.doc_var = tk.StringVar()
        e = self._entry(row); e.config(textvariable=self.doc_var)
        e.pack(side="left", fill="x", expand=True, ipady=6)
        self._ghost_button(row, "Browse", self.pick_doc, "📁").pack(
            side="left", padx=(8, 0))

        lbl2 = tk.Label(card, text="Wordlist (optional - leave empty for built-in)",
                        font=("Segoe UI", 10), anchor="w")
        lbl2.pack(fill="x", padx=16, pady=(12, 4)); self._reg(lbl2, "text")
        row2 = tk.Frame(card); row2.pack(fill="x", padx=16); self._reg(row2, "card")
        self.wl_var = tk.StringVar()
        e2 = self._entry(row2); e2.config(textvariable=self.wl_var)
        e2.pack(side="left", fill="x", expand=True, ipady=6)
        self._ghost_button(row2, "Browse", self.pick_wl, "📁").pack(
            side="left", padx=(8, 0))

        row3 = tk.Frame(card); row3.pack(fill="x", padx=16, pady=(12, 16))
        self._reg(row3, "card")
        l3 = tk.Label(row3, text="If no wordlist, try PINs up to this many digits:",
                      font=("Segoe UI", 10))
        l3.pack(side="left"); self._reg(l3, "text")
        self.digits_var = tk.IntVar(value=6)
        ttk.Spinbox(row3, from_=1, to=12, width=5,
                    textvariable=self.digits_var).pack(side="left", padx=8)

    def _build_options_card(self, parent):
        card = self._card(parent, "Options", "⚙")
        card.pack(fill="x", pady=(0, 12))
        self.mut_var = tk.BooleanVar(value=True)
        self.dates_var = tk.BooleanVar(value=True)
        self.two_var = tk.BooleanVar(value=False)
        for var, text in [
            (self.mut_var, "Variants (caps, numbers, years, symbols, leet)"),
            (self.dates_var, f"Word + date patterns ({DATE_YEAR_START}-{DATE_YEAR_END})"),
            (self.two_var, "Two-word combinations (large - slower)"),
        ]:
            cb = tk.Checkbutton(card, text=text, variable=var,
                                font=("Segoe UI", 10), anchor="w",
                                relief="flat", bd=0, highlightthickness=0,
                                cursor="hand2")
            cb.pack(fill="x", padx=16, pady=2)
            self._reg(cb, "check")
        tk.Frame(card, height=8).pack()

    def _build_action_card(self, parent):
        card = self._card(parent)
        card.pack(fill="x")
        row = tk.Frame(card); row.pack(fill="x", padx=16, pady=16)
        self._reg(row, "card")
        self.start_btn = tk.Button(row, text="▶  Start Unlocking",
                                   command=self.start, font=("Segoe UI Semibold", 11),
                                   relief="flat", bd=0, cursor="hand2", padx=18, pady=11)
        self.start_btn.pack(side="left", fill="x", expand=True)
        self._reg(self.start_btn, "primary")
        self.stop_btn = tk.Button(row, text="⬛  Stop", command=self.stop,
                                  font=("Segoe UI Semibold", 11), relief="flat",
                                  bd=0, cursor="hand2", padx=18, pady=11,
                                  state="disabled")
        self.stop_btn.pack(side="left", padx=(10, 0))
        self._reg(self.stop_btn, "ghost")

    def _build_utilities_card(self, parent):
        card = self._card(parent, "Utilities", "🔧")
        card.pack(fill="y")
        inner = tk.Frame(card); inner.pack(fill="both", padx=12, pady=(4, 14))
        self._reg(inner, "card")

        self.gpu_btn = self._ghost_button(inner, "Export for GPU (Hashcat)",
                                          self.export_gpu, "⬆")
        self.gpu_btn.pack(fill="x", pady=3)
        self.hc_btn = self._ghost_button(inner, "Get Hashcat", self.get_hashcat, "⬇")
        self.hc_btn.pack(fill="x", pady=3)
        self.test_btn = self._ghost_button(inner, "Test GPU", self.test_gpu, "🖥")
        self.test_btn.pack(fill="x", pady=3)

        self.run_btn = tk.Button(inner, text="▶   Run Hashcat now",
                                 command=self.run_hashcat, font=("Segoe UI Semibold", 10),
                                 relief="flat", bd=0, cursor="hand2", anchor="w",
                                 padx=14, pady=10)
        self.run_btn.pack(fill="x", pady=3); self._reg(self.run_btn, "purple")
        self.bf_btn = tk.Button(inner, text="⚡   GPU brute-force (all combos)",
                                command=self.run_gpu_bruteforce,
                                font=("Segoe UI Semibold", 10), relief="flat",
                                bd=0, cursor="hand2", anchor="w", padx=14, pady=10)
        self.bf_btn.pack(fill="x", pady=3); self._reg(self.bf_btn, "purple")

        self.unlock_btn = self._ghost_button(inner, "Unlock with known password",
                                             self.unlock_known, "🔒")
        self.unlock_btn.pack(fill="x", pady=3)

    def _build_status_card(self, parent):
        card = self._card(parent, "Progress & Status", "📈")
        card.pack(fill="x", padx=18, pady=(6, 16))
        self.progress = ttk.Progressbar(card, mode="determinate",
                                        style="WU.Horizontal.TProgressbar")
        self.progress.pack(fill="x", padx=16, pady=(8, 8))
        row = tk.Frame(card); row.pack(fill="x", padx=16, pady=(0, 14))
        self._reg(row, "card")
        self.status = tk.Label(row, text="● Idle", font=("Segoe UI", 10))
        self.status.pack(side="left"); self._reg(self.status, "text")
        self.tries_lbl = tk.Label(row, text="Tries: 0", font=("Segoe UI", 10))
        self.tries_lbl.pack(side="left", padx=24); self._reg(self.tries_lbl, "muted")
        self.eta_lbl = tk.Label(row, text="Speed: -    Est. time left: -",
                                font=("Segoe UI", 10))
        self.eta_lbl.pack(side="left"); self._reg(self.eta_lbl, "muted")

    # ---- theming ------------------------------------------------------
    def apply_theme(self):
        mode = self.theme_mode.get()
        key = system_theme() if mode == "system" else mode
        c = THEMES.get(key, THEMES["light"])
        self.root.configure(bg=c["bg"])
        for w, role in self._widgets:
            try:
                self._style_widget(w, role, c)
            except tk.TclError:
                pass
        for card in self._cards:
            card.configure(bg=c["card"], highlightbackground=c["card_border"],
                           highlightcolor=c["card_border"])
        self.style.configure("WU.Horizontal.TProgressbar",
                             troughcolor=c["track"], background=c["bar"],
                             bordercolor=c["track"], lightcolor=c["bar"],
                             darkcolor=c["bar"], thickness=10)
        self.style.configure("TCombobox", fieldbackground=c["entry_bg"],
                             background=c["entry_bg"], foreground=c["entry_fg"])
        self.style.configure("TSpinbox", fieldbackground=c["entry_bg"],
                             foreground=c["entry_fg"], arrowcolor=c["text"])

    def _style_widget(self, w, role, c):
        if role == "bg":
            w.configure(bg=c["bg"])
        elif role == "card":
            w.configure(bg=c["card"])
        elif role == "title":
            w.configure(bg=c["card"] if w.master in self._cards else c["bg"],
                        fg=c["title"])
        elif role == "text":
            w.configure(bg=w.master.cget("bg"), fg=c["text"])
        elif role == "muted":
            w.configure(bg=w.master.cget("bg"), fg=c["muted"])
        elif role == "entry":
            w.configure(bg=c["entry_bg"], fg=c["entry_fg"],
                        insertbackground=c["text"],
                        highlightbackground=c["entry_border"],
                        highlightcolor=c["accent"], disabledbackground=c["entry_bg"])
        elif role == "check":
            w.configure(bg=c["card"], fg=c["text"], activebackground=c["card"],
                        activeforeground=c["text"], selectcolor=c["entry_bg"])
        elif role == "primary":
            w.configure(bg=c["accent"], fg=c["accent_fg"],
                        activebackground=c["accent"], activeforeground=c["accent_fg"])
        elif role == "purple":
            w.configure(bg=c["purple"], fg=c["purple_fg"],
                        activebackground=c["purple"], activeforeground=c["purple_fg"])
        elif role == "ghost":
            w.configure(bg=c["ghost_bg"], fg=c["ghost_fg"],
                        activebackground=c["entry_bg"], activeforeground=c["ghost_fg"],
                        highlightbackground=c["ghost_border"], highlightthickness=1)

    # ---- file pickers -------------------------------------------------
    def pick_doc(self):
        path = filedialog.askopenfilename(
            title="Select the locked document",
            filetypes=[("Documents", "*.docx *.xlsx *.pptx *.doc *.xls *.ppt *.pdf"),
                       ("PDF files", "*.pdf"),
                       ("Office documents", "*.docx *.xlsx *.pptx *.doc *.xls *.ppt"),
                       ("All files", "*.*")])
        if path:
            self.doc_var.set(path)

    def pick_wl(self):
        path = filedialog.askopenfilename(
            title="Select a wordlist (one password per line)",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            self.wl_var.set(path)

    # ---- CPU dictionary attack ---------------------------------------
    def start(self):
        doc = self.doc_var.get().strip().strip('"')
        if not doc or not os.path.isfile(doc):
            messagebox.showerror("Error", "Please choose a valid document path.")
            return
        wl = self.wl_var.get().strip().strip('"')
        if wl and not os.path.isfile(wl):
            messagebox.showerror("Error", "The wordlist path is not a valid file.")
            return
        self.stop_flag.clear()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status.config(text="● Reading file...")
        self.progress.config(value=0)
        self.eta_lbl.config(text="Speed: measuring...    Est. time left: -")
        self.worker = threading.Thread(
            target=self.run_crack,
            args=(doc, wl or None, int(self.digits_var.get()), self.mut_var.get(),
                  self.two_var.get(), self.dates_var.get()), daemon=True)
        self.worker.start()
        self.ensure_pump()

    def stop(self):
        self.stop_flag.set()
        self.status.config(text="● Stopping...")
        if self.hc_proc is not None:
            try:
                self.hc_proc.terminate()
            except Exception:
                pass

    def run_crack(self, doc_path, wordlist, digit_len, use_mutations,
                  use_twoword, use_dates):
        try:
            with open(doc_path, "rb") as f:
                file_bytes = f.read()
            doc_kind = detect_kind(doc_path)
            if not is_protected(file_bytes, doc_kind):
                self.q.put(("error", "This file is not password-protected."))
                return
            candidates, total = build_candidates(
                wordlist, digit_len, use_mutations, use_twoword, use_dates)
            self.q.put(("total", total))
            already = load_tested(doc_path)
            seen, new_tested = set(), []
            tries = skipped = 0
            found = None
            stopped = False
            # A PDF with only an owner/permissions password opens with "".
            if doc_kind == "pdf" and test_password(file_bytes, "", doc_kind):
                found = ""
            start_t = time.time()
            for pw in candidates:
                if found is not None:
                    break
                if self.stop_flag.is_set():
                    stopped = True
                    break
                if pw in seen:
                    continue
                seen.add(pw)
                if pw in already:
                    skipped += 1
                    continue
                tries += 1
                if tries % 250 == 0 or tries == 1:
                    elapsed = time.time() - start_t
                    rate = tries / elapsed if elapsed > 0 else 0.0
                    remaining = max(0, total - tries - skipped)
                    eta = remaining / rate if rate > 0 else None
                    self.q.put(("progress", tries, pw, skipped, rate, eta, total))
                if test_password(file_bytes, pw, doc_kind):
                    found = pw
                    break
                new_tested.append(pw)
            tested_file = append_tested(doc_path, new_tested)
            if found is None:
                msg_kind = "stopped" if stopped else "nofound"
                self.q.put((msg_kind, tries, len(new_tested), tested_file))
                return
            folder = os.path.dirname(doc_path)
            out_path = os.path.join(folder, "Unlocked_" + os.path.basename(doc_path))
            decrypt_to(file_bytes, found, out_path, doc_kind)
            log_path = write_log(folder, doc_path, found, tries, out_path)
            self.q.put(("found", tries, found, out_path, log_path))
        except Exception as exc:
            self.q.put(("error", str(exc)))

    # ---- GPU export ---------------------------------------------------
    def _build_gpu_files(self, doc_path, wordlist, mut, two, dates):
        folder = os.path.dirname(doc_path)
        base = os.path.basename(doc_path)
        candidates, _ = build_candidates(wordlist, 0, mut, two, dates)
        already = load_tested(doc_path)
        wl_path = os.path.join(folder, base + ".smart_wordlist.txt")
        seen = set()
        count = 0
        with open(wl_path, "w", encoding="utf-8") as f:
            for pw in candidates:
                if pw in seen or pw in already:
                    continue
                seen.add(pw)
                f.write(pw + "\n")
                count += 1
        hash_note = ""
        hash_path = os.path.join(folder, base + ".hash")
        try:
            with open(hash_path, "w", encoding="utf-8") as f:
                f.write(extract_office_hash(doc_path) + "\n")
        except Exception as exc:
            hash_path = None
            hash_note = f"\n\nNOTE: hash extraction failed: {exc}"
        return wl_path, hash_path, count, hash_note

    def _gpu_office_only(self, doc):
        """GPU/Hashcat path supports Office only. Returns True if blocked (PDF)."""
        if detect_kind(doc) == "pdf":
            messagebox.showinfo(
                "Office only",
                "GPU acceleration (Hashcat) currently supports Microsoft Office "
                "files only (.docx / .xlsx / .pptx).\n\nFor PDFs, use "
                "'Start Unlocking' (CPU) or 'Unlock with known password'.")
            return True
        return False

    def export_gpu(self):
        doc = self.doc_var.get().strip().strip('"')
        if not doc or not os.path.isfile(doc):
            messagebox.showerror("Error", "Please choose a valid document path.")
            return
        if self._gpu_office_only(doc):
            return
        wl = self.wl_var.get().strip().strip('"')
        self.gpu_btn.config(state="disabled")
        self.status.config(text="● Building GPU package...")
        self.gpu_thread = threading.Thread(
            target=self._export_gpu_worker,
            args=(doc, wl or None, self.mut_var.get(), self.two_var.get(),
                  self.dates_var.get()), daemon=True)
        self.gpu_thread.start()
        self.ensure_pump()

    def _export_gpu_worker(self, doc_path, wordlist, mut, two, dates):
        try:
            folder = os.path.dirname(doc_path)
            base = os.path.basename(doc_path)
            wl_path, hash_path, count, hash_note = self._build_gpu_files(
                doc_path, wordlist, mut, two, dates)
            hc = find_hashcat() or "hashcat"
            hash_ref = hash_path or os.path.join(folder, base + ".hash")
            bat_path = os.path.join(folder, "run_hashcat.bat")
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(
                    "@echo off\r\n"
                    "REM Auto-generated by Doc Unlocker - GPU crack (-m 9600)\r\n\r\n"
                    'echo === Dictionary attack ===\r\n'
                    f'"{hc}" -m 9600 -a 0 "{hash_ref}" "{wl_path}" -O -w 3\r\n\r\n'
                    "REM === Optional brute-force of 6-digit PINs ===\r\n"
                    f'REM "{hc}" -m 9600 -a 3 "{hash_ref}" ?d?d?d?d?d?d -O -w 3\r\n\r\n'
                    'echo === Show cracked password ===\r\n'
                    f'"{hc}" -m 9600 "{hash_ref}" --show\r\n'
                    "pause\r\n")
            self.q.put(("gpu_done", count, wl_path, hash_path, bat_path,
                        hc if hc != "hashcat" else None, hash_note))
        except Exception as exc:
            self.q.put(("gpu_error", str(exc)))

    # ---- download Hashcat --------------------------------------------
    def get_hashcat(self):
        if find_hashcat():
            messagebox.showinfo("Hashcat", f"Hashcat is already available:\n{find_hashcat()}")
            return
        if not messagebox.askyesno(
                "Download Hashcat",
                f"Hashcat {HASHCAT_VERSION} (the GPU cracker) is not installed.\n\n"
                "Download it now (~20 MB) and unpack it next to this tool?"):
            return
        self.gpu_btn.config(state="disabled")
        self.hc_btn.config(state="disabled")
        self.status.config(text="● Downloading Hashcat...")
        self.hc_thread = threading.Thread(target=self._get_hashcat_worker, daemon=True)
        self.hc_thread.start()
        self.ensure_pump()

    def _get_hashcat_worker(self):
        try:
            exe = download_hashcat(
                progress_cb=lambda d, t: t > 0 and self.q.put(("hc_progress", d, t)))
            self.q.put(("hc_done", exe))
        except Exception as exc:
            self.q.put(("hc_error", str(exc)))

    # ---- test GPU -----------------------------------------------------
    def test_gpu(self):
        hc = find_hashcat()
        if not hc:
            messagebox.showwarning("Hashcat needed",
                                   "Click 'Get Hashcat' first, then 'Test GPU'.")
            return
        self.status.config(text="● Querying GPU devices...")
        self.hc_run_thread = threading.Thread(target=self._test_gpu_worker,
                                              args=(hc,), daemon=True)
        self.hc_run_thread.start()
        self.ensure_pump()

    def _test_gpu_worker(self, hc):
        try:
            r = subprocess.run([hc, "-I"], cwd=os.path.dirname(hc) or None,
                               stdin=subprocess.DEVNULL, capture_output=True,
                               text=True, creationflags=_no_window(), timeout=120)
            out = (r.stdout or "") + (r.stderr or "")
            low = out.lower()
            if "nvidia" in low or "rtx" in low or "geforce" in low:
                verdict = "GPU DETECTED. You're ready to crack."
            elif "no devices found" in low or "no backend" in low:
                verdict = "NO GPU DETECTED. Update your GPU driver."
            else:
                verdict = "Devices listed below - check for your GPU."
            text = (out.strip() or "(no output)")[:2500]
            self.q.put(("gpu_test", verdict, text))
        except subprocess.TimeoutExpired:
            self.q.put(("gpu_test_error", "hashcat -I timed out."))
        except Exception as exc:
            self.q.put(("gpu_test_error", str(exc)))

    # ---- run Hashcat (dictionary) ------------------------------------
    def run_hashcat(self):
        doc = self.doc_var.get().strip().strip('"')
        if not doc or not os.path.isfile(doc):
            messagebox.showerror("Error", "Please choose a valid document path.")
            return
        if self._gpu_office_only(doc):
            return
        hc = find_hashcat()
        if not hc:
            messagebox.showwarning("Hashcat needed", "Click 'Get Hashcat' first.")
            return
        wl = self.wl_var.get().strip().strip('"')
        self._begin_gpu_run()
        self.hc_run_thread = threading.Thread(
            target=self._run_hashcat_worker,
            args=(doc, wl or None, self.mut_var.get(), self.two_var.get(),
                  self.dates_var.get(), hc), daemon=True)
        self.hc_run_thread.start()
        self.ensure_pump()

    def _run_hashcat_worker(self, doc_path, wordlist, mut, two, dates, hc):
        try:
            self.q.put(("hcrun_status", "Building wordlist + hash..."))
            wl_path, hash_path, count, _ = self._build_gpu_files(
                doc_path, wordlist, mut, two, dates)
            if not hash_path:
                self.q.put(("hcrun_error", "Could not extract the hash."))
                return
            self._execute_hashcat(hc, hash_path, doc_path,
                                  ["-a", "0", hash_path, wl_path], count)
        except Exception as exc:
            self.hc_proc = None
            self.q.put(("hcrun_error", str(exc)))

    # ---- GPU brute-force (mask) --------------------------------------
    MASK_CHARSETS = [
        ("Digits 0-9", "?d", None, 10),
        ("Lowercase a-z", "?l", None, 26),
        ("Lowercase + digits", "?1", "?l?d", 36),
        ("Letters + digits", "?1", "?l?u?d", 62),
        ("All printable (?a)", "?a", None, 95),
    ]

    def run_gpu_bruteforce(self):
        doc = self.doc_var.get().strip().strip('"')
        if not doc or not os.path.isfile(doc):
            messagebox.showerror("Error", "Please choose a valid document path.")
            return
        if self._gpu_office_only(doc):
            return
        hc = find_hashcat()
        if not hc:
            messagebox.showwarning("Hashcat needed", "Click 'Get Hashcat' first.")
            return
        params = self._ask_mask_params()
        if not params:
            return
        custom_charset, mask = params
        self._begin_gpu_run()
        self.hc_run_thread = threading.Thread(
            target=self._run_mask_worker,
            args=(doc, hc, custom_charset, mask), daemon=True)
        self.hc_run_thread.start()
        self.ensure_pump()

    def _run_mask_worker(self, doc_path, hc, custom_charset, mask):
        try:
            folder = os.path.dirname(doc_path)
            base = os.path.basename(doc_path)
            self.q.put(("hcrun_status", "Extracting hash..."))
            hash_path = os.path.join(folder, base + ".hash")
            try:
                with open(hash_path, "w", encoding="utf-8") as f:
                    f.write(extract_office_hash(doc_path) + "\n")
            except Exception as exc:
                self.q.put(("hcrun_error", f"Hash extraction failed: {exc}"))
                return
            attack = ["-a", "3", "-i"]
            if custom_charset:
                attack += ["-1", custom_charset]
            attack += [hash_path, mask]
            self._execute_hashcat(hc, hash_path, doc_path, attack, 0)
        except Exception as exc:
            self.hc_proc = None
            self.q.put(("hcrun_error", str(exc)))

    def _execute_hashcat(self, hc, hash_path, doc_path, attack_args, count):
        folder = os.path.dirname(doc_path)
        base = os.path.basename(doc_path)
        with open(hash_path, encoding="utf-8") as f:
            hash_str = f.readline().rstrip("\r\n")
        pot = os.path.join(folder, base + ".pot")
        cracked = os.path.join(folder, base + ".cracked.txt")
        for p in (cracked, pot):
            try:
                os.remove(p)
            except OSError:
                pass
        hc_dir = os.path.dirname(hc) or None
        cmd = [hc, "-m", "9600", "-O", "-w", "3", "--potfile-path", pot,
               "--outfile-format", "2", "--outfile", cracked,
               "--status", "--status-timer", "10"] + attack_args
        self.q.put(("hcrun_status", "Launching Hashcat on the GPU..."))
        proc = subprocess.Popen(cmd, cwd=hc_dir, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, creationflags=_no_window())
        self.hc_proc = proc
        keys = ("Progress", "Speed", "Recovered", "Time.Estimated", "Status")
        tail = []
        for line in proc.stdout:
            line = line.strip()
            tail.append(line)
            if len(tail) > 30:
                tail.pop(0)
            if self.stop_flag.is_set():
                proc.terminate()
                break
            if any(k in line for k in keys):
                self.q.put(("hcrun_status", "Hashcat: " + line[:80]))
        proc.wait()
        self.hc_proc = None
        joined = "\n".join(tail).lower()
        if "token length exception" in joined or "no hashes loaded" in joined:
            self.q.put(("hcrun_error",
                        "Hashcat could not load the hash.\n\n" + "\n".join(tail[-8:])))
            return
        pwd = read_cracked_password(hash_str, cracked, pot)
        if not pwd:
            self.q.put(("hcrun_stopped",) if self.stop_flag.is_set()
                       else ("hcrun_nofound", count))
            return
        with open(doc_path, "rb") as f:
            file_bytes = f.read()
        if not test_password(file_bytes, pwd):
            self.q.put(("hcrun_error",
                        f"Hashcat reported {pwd!r}, but it did not open the file."))
            return
        out_path = os.path.join(folder, "Unlocked_" + base)
        decrypt_to(file_bytes, pwd, out_path)
        log_path = write_log(folder, doc_path, pwd, count, out_path)
        self.q.put(("hcrun_found", pwd, out_path, log_path))

    def _ask_mask_params(self):
        win = tk.Toplevel(self.root)
        win.title("GPU brute-force - all combinations")
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)
        tk.Label(win, text="Character set to try every combination of:",
                 anchor="w").grid(row=0, column=0, columnspan=2, sticky="w",
                                  padx=10, pady=(10, 2))
        cs_var = tk.IntVar(value=0)
        for i, (label, _ph, _c, _sz) in enumerate(self.MASK_CHARSETS):
            tk.Radiobutton(win, text=label, variable=cs_var, value=i,
                           command=lambda: _update()).grid(
                row=1 + i, column=0, columnspan=2, sticky="w", padx=20)
        row = 1 + len(self.MASK_CHARSETS)
        tk.Label(win, text="Maximum length:").grid(row=row, column=0, sticky="w",
                                                   padx=10, pady=6)
        len_var = tk.IntVar(value=6)
        ttk.Spinbox(win, from_=1, to=12, width=5, textvariable=len_var,
                    command=lambda: _update()).grid(row=row, column=1, sticky="w")
        info = tk.Label(win, text="", fg="#a33", justify="left", anchor="w",
                        wraplength=380)
        info.grid(row=row + 1, column=0, columnspan=2, sticky="w", padx=10, pady=6)
        result = {"val": None}

        def _update(*_):
            size = self.MASK_CHARSETS[cs_var.get()][3]
            n = int(len_var.get() or 1)
            ks = sum(size ** i for i in range(1, n + 1))
            info.config(text=(f"Combinations to try: {ks:,}\n"
                              f"Worst-case at ~3,000 guesses/sec: "
                              f"{format_duration(ks / 3000.0)}.\n"
                              "Tip: digits or lowercase up to ~7 is realistic."))

        def _ok():
            _label, ph, custom, _sz = self.MASK_CHARSETS[cs_var.get()]
            result["val"] = (custom, ph * int(len_var.get() or 1))
            win.destroy()

        btns = tk.Frame(win)
        btns.grid(row=row + 2, column=0, columnspan=2, pady=10)
        tk.Button(btns, text="Start brute-force", command=_ok, width=16).pack(
            side="left", padx=6)
        tk.Button(btns, text="Cancel", command=win.destroy, width=10).pack(side="left")
        _update()
        self.root.wait_window(win)
        return result["val"]

    # ---- unlock with a known password --------------------------------
    def unlock_known(self):
        doc = self.doc_var.get().strip().strip('"')
        if not doc or not os.path.isfile(doc):
            messagebox.showerror("Error", "Please choose a valid document path.")
            return
        pw = simpledialog.askstring("Unlock with known password",
                                    "Enter the password:", parent=self.root)
        if not pw:
            return
        try:
            with open(doc, "rb") as f:
                file_bytes = f.read()
            kind = detect_kind(doc)
            if not test_password(file_bytes, pw, kind):
                messagebox.showerror("Wrong password", "That password did not work.")
                return
            folder = os.path.dirname(doc)
            out_path = os.path.join(folder, "Unlocked_" + os.path.basename(doc))
            decrypt_to(file_bytes, pw, out_path, kind)
            log_path = write_log(folder, doc, pw, 0, out_path)
            messagebox.showinfo("Unlocked",
                                f"Password accepted.\n\nSaved to:\n{out_path}\n\n"
                                f"Logged to:\n{log_path}")
            self.status.config(text=f"● Unlocked with: {pw}")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    # ---- run-state helpers -------------------------------------------
    def _begin_gpu_run(self):
        self.stop_flag.clear()
        for b in (self.gpu_btn, self.hc_btn, self.run_btn, self.bf_btn):
            b.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status.config(text="● Preparing GPU run...")

    def finish(self):
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    def _finish_hc(self):
        for b in (self.gpu_btn, self.hc_btn, self.run_btn, self.bf_btn):
            b.config(state="normal")
        self.stop_btn.config(state="disabled")

    def _jobs_alive(self):
        return any(t is not None and t.is_alive() for t in
                   (self.worker, self.gpu_thread, self.hc_thread, self.hc_run_thread))

    def ensure_pump(self):
        if not self._pump_active:
            self._pump_active = True
            self.root.after(100, self.pump)

    # ---- UI pump (main thread) ---------------------------------------
    def pump(self):
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "total":
                    self.progress.config(maximum=max(1, msg[1]), value=0)
                    self.status.config(text=f"● Trying up to {msg[1]:,} passwords...")
                elif kind == "progress":
                    _, tries, pw, skipped, rate, eta, total = msg
                    self.progress.config(value=tries)
                    extra = f"   (skipped {skipped:,})" if skipped else ""
                    self.tries_lbl.config(text=f"Tries: {tries:,}{extra}")
                    self.eta_lbl.config(
                        text=f"Speed: {rate:,.0f} pw/s    "
                             f"Est. time left: {format_duration(eta)}")
                elif kind == "found":
                    _, tries, pw, out_path, log_path = msg
                    self.progress.config(value=self.progress["maximum"])
                    self.tries_lbl.config(text=f"Tries: {tries:,}")
                    self.finish()
                    self.status.config(text=f"● Done. Password: {pw}")
                    messagebox.showinfo("Password found!",
                                        f"Success!\n\nTries: {tries:,}\n"
                                        f"Password: {pw}\n\nUnlocked copy:\n{out_path}\n\n"
                                        f"Logged to:\n{log_path}")
                    break
                elif kind == "nofound":
                    _, tries, saved, tested_file = msg
                    self.finish()
                    self.status.config(text="● Not found.")
                    messagebox.showwarning("Not found",
                                           f"Tried {tries:,} passwords.\nSaved "
                                           f"{saved:,} to:\n{tested_file}\n(skipped "
                                           "next time). Try the GPU options.")
                    break
                elif kind == "stopped":
                    _, tries, saved, tested_file = msg
                    self.finish()
                    self.status.config(text="● Stopped.")
                    messagebox.showinfo("Stopped",
                                        f"Stopped after {tries:,} new tries.\n"
                                        f"Saved {saved:,} to:\n{tested_file}")
                    break
                elif kind == "error":
                    self.finish()
                    self.status.config(text="● Error.")
                    messagebox.showerror("Error", msg[1])
                    break
                elif kind == "gpu_done":
                    _, count, wl_path, hash_path, bat_path, hc, note = msg
                    self.gpu_btn.config(state="normal")
                    self.status.config(text="● GPU package ready.")
                    extra = (f"Hashcat found:\n{hc}\n\nDouble-click:\n{bat_path}"
                             if hc else "Hashcat not installed - click 'Get Hashcat'.")
                    messagebox.showinfo("GPU package ready",
                                        f"Wrote {count:,} candidates to:\n{wl_path}\n\n"
                                        f"Hash:\n{hash_path or '(failed)'}\n\n"
                                        + extra + note)
                    break
                elif kind == "gpu_error":
                    self.gpu_btn.config(state="normal")
                    self.status.config(text="● GPU export failed.")
                    messagebox.showerror("GPU export failed", msg[1])
                    break
                elif kind == "hc_progress":
                    _, done, total = msg
                    self.progress.config(maximum=max(1, total), value=done)
                    self.status.config(text=f"● Downloading Hashcat... "
                                            f"{done/1048576:.1f}/{total/1048576:.1f} MB")
                elif kind == "hc_done":
                    self.gpu_btn.config(state="normal")
                    self.hc_btn.config(state="normal")
                    self.status.config(text="● Hashcat installed.")
                    messagebox.showinfo("Hashcat ready",
                                        f"Installed at:\n{msg[1]}\n\nNow use "
                                        "'Run Hashcat now' or 'GPU brute-force'.")
                    break
                elif kind == "hc_error":
                    self.gpu_btn.config(state="normal")
                    self.hc_btn.config(state="normal")
                    self.status.config(text="● Hashcat download failed.")
                    messagebox.showerror("Hashcat download failed",
                                         msg[1] + "\n\nManual: https://hashcat.net/"
                                         "hashcat/ unzip into:\n" + app_dir())
                    break
                elif kind == "gpu_test":
                    self.status.config(text="● " + msg[1])
                    messagebox.showinfo("Test GPU", msg[1] + "\n\n" + msg[2])
                    break
                elif kind == "gpu_test_error":
                    self.status.config(text="● GPU test failed.")
                    messagebox.showerror("Test GPU failed", msg[1])
                    break
                elif kind == "hcrun_status":
                    self.status.config(text="● " + msg[1])
                elif kind == "hcrun_found":
                    _, pw, out_path, log_path = msg
                    self._finish_hc()
                    self.status.config(text=f"● GPU crack done. Password: {pw}")
                    messagebox.showinfo("Password found (GPU)!",
                                        f"Hashcat cracked it!\n\nPassword: {pw}\n\n"
                                        f"Unlocked copy:\n{out_path}\n\nLogged to:\n{log_path}")
                    break
                elif kind == "hcrun_nofound":
                    self._finish_hc()
                    self.status.config(text="● Not in wordlist.")
                    messagebox.showwarning("Not found (GPU)",
                                           "Hashcat finished the wordlist without "
                                           "finding the password. Try more options "
                                           "or GPU brute-force.")
                    break
                elif kind == "hcrun_stopped":
                    self._finish_hc()
                    self.status.config(text="● GPU crack stopped.")
                    messagebox.showinfo("Stopped", "Hashcat was stopped.")
                    break
                elif kind == "hcrun_error":
                    self._finish_hc()
                    self.status.config(text="● GPU crack failed.")
                    messagebox.showerror("Hashcat run failed", msg[1])
                    break
        except queue.Empty:
            pass
        if self._jobs_alive() or not self.q.empty():
            self.root.after(100, self.pump)
        else:
            self._pump_active = False
            self.finish()


def _set_app_user_model_id():
    """
    Give the process an explicit AppUserModelID so Windows shows OUR window
    icon in the taskbar (instead of grouping the app under the generic
    python/Tk icon). Must be called before the first window is created.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "FallaxVision.DocUnlocker")
        except Exception:
            pass


def main():
    _set_app_user_model_id()
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
