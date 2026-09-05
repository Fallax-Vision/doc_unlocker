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

Supports Microsoft Word, Excel and PowerPoint (.docx / .xlsx / .pptx, plus
legacy and macro-enabled variants) and PDF documents.
"""

from __future__ import annotations

__version__ = "1.0.6"
__app_name__ = "Doc Unlocker"

import io
import os
import sys
import glob
import json
import re
import time
import queue
import hashlib
import tempfile
import multiprocessing
from collections import deque
import base64
import shutil
import threading
import itertools
import subprocess
import datetime
import webbrowser
import urllib.request
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog


# ---------------------------------------------------------------------------
# Dependency bootstrap: install + import the libraries we rely on.
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
    try:
        import customtkinter  # noqa: F401  (modern UI)
    except ImportError:
        missing.append("customtkinter")
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
        import msoffcrypto    # noqa: F401
        import olefile        # noqa: F401
        import pypdf          # noqa: F401
        import customtkinter  # noqa: F401
        return True
    except Exception as exc:  # pragma: no cover
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror(
            "Setup failed",
            "Could not install the dependencies automatically.\n\n"
            "Open a terminal and run:\n\n"
            f'    "{sys.executable}" -m pip install msoffcrypto-tool olefile '
            "pypdf customtkinter\n\n"
            f"Details: {exc}",
        )
        r.destroy()
        return False


if __name__ == "__main__":
    if not ensure_dependencies():
        sys.exit(1)

import olefile
import msoffcrypto
import pypdf
import customtkinter as ctk


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
    if os.path.getsize(path) > 32 * 1024 * 1024:
        raise ValueError("Wordlists must be 32 MiB or smaller.")
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if len(line) > 1024:
                raise ValueError("Wordlist entries must be 1,024 characters or shorter.")
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
        for word in COMMON_PASSWORDS:
            yield from emit(word)
        if use_dates:
            yield from date_combos(base_words)
        if use_twoword:
            yield from twoword_combos(base_words)
        if wordlist_path:
            for word in _read_lines(wordlist_path):
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
            for line in history_lines(path):
                line = line.rstrip("\r\n")
                if line:
                    tried.add(line if re.fullmatch(r"sha256:[0-9a-f]{64}", line)
                              else attempt_digest(line))
        except Exception:
            pass
    return tried


def append_tested(doc_path, passwords):
    if not passwords:
        return tested_path_for(doc_path)
    path = tested_path_for(doc_path)
    try:
        previous = deque(maxlen=50000)
        if os.path.isfile(path):
            previous.extend(history_lines(path))
        history = deque((line if re.fullmatch(r"sha256:[0-9a-f]{64}", line)
                         else attempt_digest(line) for line in previous if line), maxlen=50000)
        history.extend(attempt_digest(password) for password in passwords)
        atomic_write(path, ("\n".join(history) + "\n").encode("utf-8"))
    except Exception:
        pass
    return path


def attempt_digest(password):
    return "sha256:" + hashlib.sha256(password.encode("utf-8")).hexdigest()


def history_lines(path):
    # Read at most 4 MiB even when migrating an old, very large resume file.
    with open(path, "rb") as stream:
        size = os.fstat(stream.fileno()).st_size
        if size > 4 * 1024 * 1024:
            stream.seek(size - 4 * 1024 * 1024)
            stream.readline(4096)
        data = stream.read(4 * 1024 * 1024)
    return [line for line in data.decode("utf-8", errors="ignore").splitlines()[-50000:]
            if 0 < len(line) <= 1024]


def atomic_write(path, data):
    """Replace only a complete app-owned file, with no accumulating temp copies."""
    fd, temp = tempfile.mkstemp(prefix=".docunlocker-", dir=os.path.dirname(os.path.abspath(path)))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


MAX_DOCUMENT_BYTES = 64 * 1024 * 1024


def read_document(path):
    with open(path, "rb") as stream:
        data = stream.read(MAX_DOCUMENT_BYTES + 1)
    if len(data) > MAX_DOCUMENT_BYTES:
        raise ValueError("Documents must be 64 MiB or smaller.")
    return data


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


SUPPORTED_EXTS = {
    ".docx", ".docm", ".doc", ".xlsx", ".xlsm", ".xls",
    ".pptx", ".pptm", ".ppt", ".pdf",
}


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
    validate_office_parameters(office)
    if getattr(office, "format", None) == "ooxml":
        office.load_key(password=password, verify_password=True)
    else:
        office.load_key(password=password)
    out = io.BytesIO()
    office.decrypt(out)
    return out.getvalue()


def validate_office_parameters(office):
    info = getattr(office, "info", {})
    if isinstance(info, dict) and "spinValue" in info:
        if not 0 <= info["spinValue"] <= 1000000:
            raise ValueError("Office encryption exceeds the supported iteration limit.")
        if info.get("keyDataBlockSize") != 16 or info.get("passwordKeyBits") not in (128, 192, 256):
            raise ValueError("Unsupported Office encryption sizes.")


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
    with open(out_path, "xb") as f:
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
    with open(out_path, "xb") as out:
        out.write(data)


def unlocked_path(doc_path):
    folder = os.path.dirname(doc_path)
    stem, suffix = os.path.splitext(os.path.basename(doc_path))
    for index in range(10000):
        extra = f" ({index})" if index else ""
        path = os.path.join(folder, f"Unlocked_{stem}{extra}{suffix}")
        if not os.path.lexists(path):
            return path
    raise ValueError("Too many unlocked copies in this folder; choose another folder.")


class RecoveryCancelled(Exception):
    pass


def _password_worker(data, kind, requests, results):
    """Isolated parser/KDF worker: the UI can terminate a stalled library call."""
    try:
        if kind == "office":
            validate_office_parameters(msoffcrypto.OfficeFile(io.BytesIO(data)))
        else:
            _pdf_reader(data)
        results.put(("ready", None))
        while True:
            password = requests.get()
            if password is None:
                return
            try:
                if kind == "office":
                    plain = _office_decrypt_bytes(data, password)
                    if not plain[:4].startswith(_OFFICE_MAGIC):
                        plain = None
                else:
                    reader = _pdf_reader(data)
                    plain = None
                    if not reader.is_encrypted or int(reader.decrypt(password)) != 0:
                        writer = pypdf.PdfWriter()
                        writer.append(reader)
                        output = io.BytesIO()
                        writer.write(output)
                        plain = output.getvalue()
                results.put(("result", plain))
            except Exception:
                results.put(("result", None))
    except Exception as exc:
        results.put(("error", str(exc)))


class RecoverySession:
    def __init__(self, data, kind, stop):
        context = multiprocessing.get_context("spawn")
        self.requests = context.Queue(maxsize=1)
        self.results = context.Queue(maxsize=1)
        self.stop = stop
        self.process = context.Process(target=_password_worker,
                                       args=(data, kind, self.requests, self.results), daemon=True)

    def __enter__(self):
        try:
            self.process.start()
            self.receive()
            return self
        except BaseException:
            self.close()
            raise

    def receive(self):
        while True:
            if self.stop.is_set():
                raise RecoveryCancelled("Stopped")
            try:
                kind, value = self.results.get(timeout=0.05)
                if kind == "error":
                    raise ValueError(value)
                return value
            except queue.Empty:
                if not self.process.is_alive():
                    raise RuntimeError("The document worker exited unexpectedly.")

    def attempt(self, password):
        self.requests.put(password)
        return self.receive()

    def close(self):
        if self.process.pid is not None:
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(timeout=2)
        for channel in (self.requests, self.results):
            channel.cancel_join_thread()
            channel.close()

    def __exit__(self, *_):
        self.close()


def write_log(folder, doc_path, password, tries, out_path):
    log_path = os.path.join(folder, "DocUnlocker_found.log")
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = (f"[{stamp}] file={os.path.basename(doc_path)!r} "
            f"tries={tries} unlocked={out_path!r}\n")
    try:
        # Migrate only this application's known log files; discard old secret fields.
        for existing in (log_path, log_path + ".1", log_path + ".2"):
            if os.path.isfile(existing):
                with open(existing, "rb") as stream:
                    oversized = os.path.getsize(existing) > 1024 * 1024
                    if oversized:
                        stream.seek(-1024 * 1024, os.SEEK_END)
                        stream.readline()
                    old = stream.read().decode("utf-8", errors="replace")
                if oversized or " password=" in old:
                    cleaned = []
                    for record in old.splitlines():
                        if " password=" in record:
                            left, _, right = record.partition(" password=")
                            marker = right.rfind(" tries=")
                            if marker < 0:
                                continue
                            record = left + right[marker:]
                        cleaned.append(record)
                    atomic_write(existing, ("\n".join(cleaned) + "\n").encode("utf-8"))
        if os.path.exists(log_path) and os.path.getsize(log_path) >= 1024 * 1024:
            for index in (2, 1):
                source = log_path if index == 1 else f"{log_path}.{index - 1}"
                if os.path.isfile(source):
                    os.replace(source, f"{log_path}.{index}")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        return "Log unavailable (unlocked copy was saved)."
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
    # A private temporary download prevents partial archives from being reused.
    with tempfile.TemporaryDirectory(prefix=".docunlocker-download-", dir=dest_dir) as scratch:
        archive = os.path.join(scratch, "hashcat.7z")
        with urllib.request.urlopen(HASHCAT_URL, timeout=15) as response, open(archive, "wb") as output:
            total = int(response.headers.get("Content-Length", 0))
            done = 0
            updated = 0.0
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                done += len(chunk)
                if done > 64 * 1024 * 1024:
                    raise ValueError("Hashcat download exceeds the 64 MiB limit.")
                output.write(chunk)
                if progress_cb and time.monotonic() - updated >= 0.1:
                    progress_cb(done, total)
                    updated = time.monotonic()
            if total and done != total:
                raise ValueError("Incomplete Hashcat download; please retry.")
        if progress_cb:
            progress_cb(done, total)
        extract_7z(archive, dest_dir)
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
#  SETTINGS
# ===========================================================================
SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".doc_unlocker.json")

DEFAULT_SETTINGS = {
    "theme": "System",          # System / Light / Dark
    "corners": "Rounded",       # Rounded / Sharp
    "fullscreen": False,        # launch maximised
    "notify_done": True,        # bring window forward when a run finishes
    "sound_done": True,         # play a sound when a run finishes
    "confirm_close": True,      # confirm quitting while a run is active
    "auto_hashcat": False,      # auto-download Hashcat when needed
}


def load_settings():
    s = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            values = json.load(f)
            if isinstance(values, dict):
                s.update({key: value for key, value in values.items()
                          if key in s and type(value) is type(s[key])})
    except Exception:
        pass
    if s["theme"] not in ("System", "Light", "Dark"):
        s["theme"] = "System"
    if s["corners"] not in ("Rounded", "Sharp"):
        s["corners"] = "Rounded"
    return s


def save_settings(s):
    atomic_write(SETTINGS_PATH, json.dumps(s, indent=2).encode("utf-8"))


# Accent colours as (light, dark) tuples for CustomTkinter.
APP_BG = ("#f8fafc", "#07111c")
CARD_FG = ("#ffffff", "#0b1622")
FIELD_FG = ("#ffffff", "#08131e")
STATUS_FG = ("#f8fafc", "#091522")
TEXT = ("#111827", "#f8fafc")
MUTED_TEXT = ("#5b6472", "#a8b0bd")
BLUE = ("#2563eb", "#1d6eff")
BLUE_HOVER = ("#1d4ed8", "#2f7dff")
BLUE_SOFT = ("#eff6ff", "#122744")
BLUE_BORDER = ("#d7e7ff", "#2a5d9d")
PURPLE = ("#8b5cf6", "#6d28d9")
PURPLE_HOVER = ("#7c3aed", "#7c3aed")
PURPLE_BORDER = ("#c9b8ff", "#5e36a8")
GHOST_HOVER = ("#f8fafc", "#101a26")
GHOST_BORDER = ("#e6ebf1", "#202b39")
PROGRESS_BG = ("#e5e7eb", "#202b36")
WARNING = ("#b45309", "#f59e0b")

# Windows built-in icon glyphs from Segoe MDL2 Assets.
ICO_BROWSE = "\ue8b7"
ICO_EXPORT = "\ue898"
ICO_DOWNLOAD = "\ue896"
ICO_GPU = "\ue7f4"
ICO_RUN = "\ue768"
ICO_LOCK = "\ue72e"
ICO_MORE = "\ue712"
ICO_START = "\ue768"
ICO_STOP = "\ue71a"
ICO_SETTINGS = "\ue713"
ICO_THEME = "\ue706"


# ===========================================================================
#  GUI  (CustomTkinter)
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
        self._ptotal = 1
        self._round = []                 # widgets whose corner_radius can change
        self._settings_window = None
        self.settings_thread = None
        self.update_thread = None
        self._settings_dirty = False
        self.settings = load_settings()

        ctk.set_appearance_mode(self.settings.get("theme", "System"))
        ctk.set_default_color_theme("blue")

        root.title(f"{__app_name__} - Password Recovery  v{__version__}")
        root.configure(fg_color=APP_BG)
        self._center(920, 620)
        root.minsize(820, 580)
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.bind("<Control-comma>", lambda _event: self.open_settings())
        self._set_window_icon(root)

        self.R = 14 if self.settings.get("corners") == "Rounded" else 0

        self.doc_var = tk.StringVar()
        self.wl_var = tk.StringVar()
        self.digits_var = tk.StringVar(value="6")
        self.mut_var = tk.BooleanVar(value=True)
        self.dates_var = tk.BooleanVar(value=True)
        self.two_var = tk.BooleanVar(value=False)

        self._build_ui()

        if self.settings.get("fullscreen"):
            self.root.after(60, lambda: self._safe_zoom())

    # ---- small helpers ------------------------------------------------
    def _center(self, w, h):
        self.root.geometry(self._window_geometry(w, h))

    def _safe_zoom(self):
        try:
            self.root.state("zoomed")
        except Exception:
            try:
                self.root.attributes("-zoomed", True)
            except Exception:
                pass

    def _set_window_icon(self, root):
        ico = resource_path("assets", "icon.ico")
        if os.path.isfile(ico):
            def _apply():
                try:
                    root.iconbitmap(ico)
                except Exception:
                    pass
            _apply()
            root.after(250, _apply)   # CTk sometimes needs a delayed re-apply

    def _window_geometry(self, w, h, divisor=3):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w = min(w, sw - 48)
        h = min(h, sh - 80)
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // divisor)
        return f"{w}x{h}+{x}+{y}"

    def _card(self, parent, **kw):
        kw.setdefault("fg_color", CARD_FG)
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", GHOST_BORDER)
        f = ctk.CTkFrame(parent, corner_radius=self.R, **kw)
        self._round.append(f)
        return f

    def _section_title(self, parent, text):
        return ctk.CTkLabel(parent, text=text, anchor="w", text_color=TEXT,
                            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"))

    def _entry(self, parent, textvariable, placeholder=""):
        e = ctk.CTkEntry(parent, textvariable=textvariable, corner_radius=self.R,
                         height=36, placeholder_text=placeholder, fg_color=FIELD_FG,
                         border_width=1, border_color=GHOST_BORDER,
                         text_color=TEXT, placeholder_text_color=MUTED_TEXT,
                         font=ctk.CTkFont(family="Segoe UI", size=13))
        self._round.append(e)
        return e

    def _ghost_button(self, parent, text, command):
        b = ctk.CTkButton(parent, text=text, command=command, corner_radius=self.R,
                          height=40, anchor="w", fg_color="transparent",
                          border_width=1, border_color=GHOST_BORDER,
                          text_color=TEXT, hover_color=GHOST_HOVER,
                          font=ctk.CTkFont(family="Segoe UI", size=13))
        self._round.append(b)
        return b

    def _set_status(self, text):
        self.status.configure(text=f"Status: {text}")

    # ---- UI construction ---------------------------------------------
    def _build_ui(self):
        container = ctk.CTkFrame(self.root, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=14, pady=10)
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(1, weight=1)

        # Header (transparent -> same background as the body, also in dark mode)
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ctk.CTkLabel(header, text=__app_name__,
                     text_color=TEXT,
                     font=ctk.CTkFont(family="Segoe UI", size=19, weight="bold")
                     ).pack(side="left")
        ctk.CTkLabel(header, text=f"  Password Recovery  ·  v{__version__}",
                     text_color=("#5b6472", "#a8b0bd"),
                     font=ctk.CTkFont(family="Segoe UI", size=12)).pack(
            side="left", pady=(6, 0))
        self.settings_btn = ctk.CTkButton(
            header, text=f"{ICO_SETTINGS}  Settings", width=112, height=36,
            corner_radius=self.R, command=self.open_settings,
            fg_color="transparent", border_width=1, border_color=GHOST_BORDER,
            text_color=TEXT, hover_color=GHOST_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=12))
        self.settings_btn.pack(side="right")
        self._round.append(self.settings_btn)
        self.theme_btn = ctk.CTkButton(
            header, text="Theme", width=78, height=36, corner_radius=self.R,
            command=self.toggle_theme, fg_color="transparent", border_width=1,
            border_color=GHOST_BORDER, text_color=TEXT, hover_color=GHOST_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=12))
        self.theme_btn.pack(side="right", padx=(0, 8))
        self._round.append(self.theme_btn)
        self._refresh_theme_button()

        # Body: left column (inputs/options) + right column (actions)
        body = ctk.CTkFrame(container, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=0)
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew")
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="ns", padx=(14, 0))

        self._build_inputs_card(left)
        self._build_options_card(left)
        self._build_utilities_card(right)
        self._build_status_card(container)

    def _build_inputs_card(self, parent):
        card = self._card(parent)
        card.pack(fill="x", pady=(0, 8))
        pad = {"padx": 16}

        ctk.CTkLabel(card, text="Locked document (full path)", anchor="w",
                     text_color=TEXT,
                     font=ctk.CTkFont(family="Segoe UI", size=13)).pack(
            fill="x", pady=(12, 3), **pad)
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", **pad)
        self._entry(row, self.doc_var, "Select a locked Word / Excel / "
                    "PowerPoint / PDF document...").pack(
            side="left", fill="x", expand=True)
        b = ctk.CTkButton(row, text=f"{ICO_BROWSE}  Browse", width=104, height=36,
                          corner_radius=self.R, command=self.pick_doc,
                          fg_color="transparent", border_width=1,
                          border_color=GHOST_BORDER, text_color=TEXT,
                          hover_color=GHOST_HOVER,
                          font=ctk.CTkFont(family="Segoe UI", size=13))
        b.pack(side="left", padx=(8, 0))
        self._round.append(b)

        ctk.CTkLabel(card, text="Wordlist (optional - leave empty for built-in)",
                     anchor="w", text_color=TEXT,
                     font=ctk.CTkFont(family="Segoe UI", size=13)).pack(
            fill="x", pady=(8, 3), **pad)
        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", **pad)
        self._entry(row2, self.wl_var, "Select wordlist file (optional)...").pack(
            side="left", fill="x", expand=True)
        b2 = ctk.CTkButton(row2, text=f"{ICO_BROWSE}  Browse", width=104, height=36,
                           corner_radius=self.R, command=self.pick_wl,
                           fg_color="transparent", border_width=1,
                           border_color=GHOST_BORDER, text_color=TEXT,
                           hover_color=GHOST_HOVER,
                           font=ctk.CTkFont(family="Segoe UI", size=13))
        b2.pack(side="left", padx=(8, 0))
        self._round.append(b2)

        row3 = ctk.CTkFrame(card, fg_color="transparent")
        row3.pack(fill="x", pady=(10, 12), **pad)
        ctk.CTkLabel(row3, text="Maximum numeric PIN length:"
                     , text_color=TEXT,
                     font=ctk.CTkFont(family="Segoe UI", size=13)).pack(side="left")
        self.digits_menu = ctk.CTkOptionMenu(
            row3, width=80, height=36, corner_radius=self.R, variable=self.digits_var,
            values=[str(i) for i in range(1, 13)], fg_color=FIELD_FG,
            button_color=BLUE, button_hover_color=BLUE_HOVER,
            text_color=TEXT, dropdown_fg_color=CARD_FG,
            dropdown_hover_color=GHOST_HOVER, dropdown_text_color=TEXT,
            font=ctk.CTkFont(family="Segoe UI", size=13))
        self.digits_menu.pack(side="left", padx=10)
        self._round.append(self.digits_menu)

    def _build_options_card(self, parent):
        card = self._card(parent)
        card.pack(fill="x", pady=(0, 8))
        self._section_title(card, "Options").pack(
            fill="x", padx=16, pady=(10, 2))
        for var, text in [
            (self.mut_var, "Variants (caps, numbers, years, symbols, leet)"),
            (self.dates_var, f"Word + date patterns ({DATE_YEAR_START}-{DATE_YEAR_END})"),
            (self.two_var, "Two-word combinations (large - slower)"),
        ]:
            ctk.CTkCheckBox(card, text=text, variable=var, height=30,
                            corner_radius=5, border_width=1,
                            fg_color=BLUE, hover_color=BLUE_HOVER,
                            border_color=("#b8c2d0", "#4b5563"),
                            checkmark_color=("#ffffff", "#ffffff"),
                            text_color=TEXT,
                            font=ctk.CTkFont(family="Segoe UI", size=13)).pack(
                fill="x", padx=18, pady=3)
        ctk.CTkFrame(card, height=12, fg_color="transparent").pack(fill="x")

    def _build_utilities_card(self, parent):
        card = self._card(parent)
        card.pack(fill="both", expand=True)
        title_row = ctk.CTkFrame(card, fg_color="transparent")
        title_row.pack(fill="x", padx=16, pady=(14, 8))
        self._section_title(title_row, "Actions").pack(side="left", fill="x", expand=True)
        self.more_actions = {
            f"{ICO_DOWNLOAD}  Get Hashcat": self.get_hashcat,
            f"{ICO_GPU}  Test GPU": self.test_gpu,
            f"{ICO_RUN}  Run Hashcat now": self.run_hashcat,
        }
        self.more_actions_menu = ctk.CTkOptionMenu(
            title_row, width=100, height=36, corner_radius=self.R,
            values=list(self.more_actions.keys()), command=self._run_more_action,
            fg_color=FIELD_FG, button_color=FIELD_FG,
            button_hover_color=GHOST_HOVER, text_color=TEXT,
            dropdown_fg_color=CARD_FG, dropdown_hover_color=GHOST_HOVER,
            dropdown_text_color=TEXT,
            dropdown_font=ctk.CTkFont(family="Segoe UI", size=14),
            font=ctk.CTkFont(family="Segoe UI", size=12))
        self.more_actions_menu.set(f"{ICO_MORE}  More")
        self.more_actions_menu.pack(side="right")
        self._round.append(self.more_actions_menu)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", padx=14, pady=(0, 14))
        W = 232

        self.start_btn = ctk.CTkButton(
            inner, text=f"{ICO_START}  Start Unlocking", width=W, height=42,
            corner_radius=self.R, command=self.start,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=BLUE, hover_color=BLUE_HOVER,
            border_width=1, border_color=BLUE_BORDER)
        self.start_btn.pack(fill="x", pady=4)
        self._round.append(self.start_btn)
        self.unlock_btn = self._ghost_button(
            inner, f"{ICO_LOCK}  Unlock with known password", self.unlock_known)
        self.unlock_btn.configure(width=W); self.unlock_btn.pack(fill="x", pady=4)
        self.stop_btn = ctk.CTkButton(
            inner, text=f"{ICO_STOP}  Stop", width=W, height=42, corner_radius=self.R,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), command=self.stop,
            state="disabled", fg_color="transparent", border_width=1,
            border_color=GHOST_BORDER, text_color=TEXT,
            hover_color=GHOST_HOVER)
        self.stop_btn.pack(fill="x", pady=4)
        self._round.append(self.stop_btn)

        sep = ctk.CTkFrame(inner, height=1, fg_color=GHOST_BORDER)
        sep.pack(fill="x", pady=(12, 10))

        self.gpu_btn = self._ghost_button(inner, f"{ICO_EXPORT}  Export for GPU (Hashcat)",
                                          self.export_gpu)
        self.gpu_btn.configure(width=W, fg_color=BLUE_SOFT, border_color=BLUE_BORDER,
                               text_color=("#0f56a6", "#7ab8ff"))
        self.gpu_btn.pack(fill="x", pady=4)
        self.bf_btn = ctk.CTkButton(
            inner, text=f"{ICO_GPU}  GPU brute-force (all combos)", width=W, height=40,
            corner_radius=self.R, anchor="w", command=self.run_gpu_bruteforce,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="transparent", hover_color=GHOST_HOVER, text_color=TEXT,
            border_width=1, border_color=GHOST_BORDER)
        self.bf_btn.pack(fill="x", pady=4)
        self._round.append(self.bf_btn)

    def _run_more_action(self, choice):
        command = self.more_actions.get(choice)
        self.more_actions_menu.set(f"{ICO_MORE}  More")
        if command:
            command()

    def _build_status_card(self, parent):
        card = self._card(parent, height=155)
        card.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        card.pack_propagate(False)
        self._section_title(card, "Progress & Status").pack(
            fill="x", padx=16, pady=(10, 6))
        prow = ctk.CTkFrame(card, fg_color="transparent")
        prow.pack(fill="x", padx=16, pady=(0, 10))
        self.progress = ctk.CTkProgressBar(
            prow, height=12, corner_radius=self.R, fg_color=PROGRESS_BG,
            progress_color=BLUE)
        self.progress.set(0)
        self.progress.pack(side="left", fill="x", expand=True)
        self._round.append(self.progress)
        self.progress_pct = ctk.CTkLabel(
            prow, text="0%", width=42, text_color=("#4b5563", "#e5e7eb"),
            font=ctk.CTkFont(family="Segoe UI", size=13))
        self.progress_pct.pack(side="left", padx=(14, 0))

        row = ctk.CTkFrame(card, height=34, fg_color=STATUS_FG, corner_radius=self.R,
                           border_width=1, border_color=GHOST_BORDER)
        row.pack(fill="x", padx=16, pady=(0, 12))
        row.pack_propagate(False)
        self._round.append(row)

        self.status = ctk.CTkLabel(card, text="Status: Idle",
                                   text_color=("#0f56a6", "#7ab8ff"), anchor="w",
                                   font=ctk.CTkFont(family="Segoe UI", size=12))
        self.status.pack(fill="x", padx=16, pady=(0, 4), before=row)
        self.status.bind("<Configure>", lambda e: self.status.configure(wraplength=max(100, e.width - 12)))
        self.tries_lbl = ctk.CTkLabel(row, text="Tries: 0",
                                      text_color=TEXT, anchor="w",
                                      font=ctk.CTkFont(family="Segoe UI", size=12))
        ctk.CTkFrame(row, width=1, fg_color=GHOST_BORDER).pack(
            side="left", fill="y", pady=8)
        self.tries_lbl.pack(side="left", fill="x", expand=True, padx=(14, 10))
        self.speed_lbl = ctk.CTkLabel(row, text="Speed: -", text_color=TEXT,
                                      anchor="w",
                                      font=ctk.CTkFont(family="Segoe UI", size=12))
        ctk.CTkFrame(row, width=1, fg_color=GHOST_BORDER).pack(
            side="left", fill="y", pady=8)
        self.speed_lbl.pack(side="left", fill="x", expand=True, padx=(14, 10))
        self.eta_lbl = ctk.CTkLabel(row, text="Est. time left: -", text_color=TEXT,
                                    anchor="w",
                                    font=ctk.CTkFont(family="Segoe UI", size=12))
        ctk.CTkFrame(row, width=1, fg_color=GHOST_BORDER).pack(
            side="left", fill="y", pady=8)
        self.eta_lbl.pack(side="left", fill="x", expand=True, padx=(14, 10))

    # ---- settings dialog ---------------------------------------------
    def open_settings(self):
        if self._settings_window is not None and self._settings_window.winfo_exists():
            self._settings_window.lift()
            return
        win = ctk.CTkToplevel(self.root)
        self._settings_window = win
        win.title("Settings")
        win.configure(fg_color=APP_BG)
        win.transient(self.root)
        win.geometry(self._window_geometry(500, 650, divisor=2))
        win.bind("<Escape>", lambda _event: win.destroy())
        win.after(200, lambda: win.winfo_exists() and win.grab_set())
        win.after(260, lambda: self._set_window_icon(win))

        ctk.CTkLabel(win, text="Settings", text_color=TEXT,
                     font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold")).pack(
            anchor="w", padx=22, pady=(22, 8))
        ctk.CTkButton(win, text="Done", height=38, command=win.destroy,
                      corner_radius=self.R, fg_color=BLUE, hover_color=BLUE_HOVER).pack(
            side="bottom", fill="x", padx=22, pady=14)
        content = ctk.CTkScrollableFrame(win, fg_color="transparent")
        content.pack(fill="both", expand=True)

        # Appearance
        sec1 = ctk.CTkFrame(content, corner_radius=self.R, fg_color=CARD_FG,
                            border_width=1, border_color=GHOST_BORDER)
        sec1.pack(fill="x", padx=22, pady=8)
        self._round.append(sec1)
        ctk.CTkLabel(sec1, text="Appearance", text_color=TEXT,
                     font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold")).pack(
            anchor="w", padx=18, pady=(16, 8))

        trow = ctk.CTkFrame(sec1, fg_color="transparent")
        trow.pack(fill="x", padx=18, pady=6)
        ctk.CTkLabel(trow, text="Theme", text_color=TEXT,
                     font=ctk.CTkFont(family="Segoe UI", size=14)).pack(side="left")
        theme_menu = ctk.CTkOptionMenu(
            trow, values=["System", "Light", "Dark"], width=150, height=38,
            corner_radius=self.R, command=self._on_theme, fg_color=FIELD_FG,
            button_color=FIELD_FG, button_hover_color=GHOST_HOVER,
            text_color=TEXT, dropdown_fg_color=CARD_FG,
            dropdown_hover_color=GHOST_HOVER, dropdown_text_color=TEXT,
            font=ctk.CTkFont(family="Segoe UI", size=14))
        theme_menu.set(self.settings.get("theme", "System"))
        theme_menu.pack(side="right")
        self._round.append(theme_menu)

        crow = ctk.CTkFrame(sec1, fg_color="transparent")
        crow.pack(fill="x", padx=18, pady=(6, 18))
        ctk.CTkLabel(crow, text="UI corners", text_color=TEXT,
                     font=ctk.CTkFont(family="Segoe UI", size=14)).pack(side="left")
        corner_seg = ctk.CTkSegmentedButton(
            crow, values=["Rounded", "Sharp"], command=self._on_corners,
            corner_radius=self.R, selected_color=BLUE,
            selected_hover_color=BLUE_HOVER, unselected_color=FIELD_FG,
            unselected_hover_color=GHOST_HOVER, text_color=TEXT,
            font=ctk.CTkFont(family="Segoe UI", size=14))
        corner_seg.set(self.settings.get("corners", "Rounded"))
        corner_seg.pack(side="right")
        self._round.append(corner_seg)

        # Behaviour
        sec2 = ctk.CTkFrame(content, corner_radius=self.R, fg_color=CARD_FG,
                            border_width=1, border_color=GHOST_BORDER)
        sec2.pack(fill="x", padx=22, pady=8)
        self._round.append(sec2)
        ctk.CTkLabel(sec2, text="Behaviour", text_color=TEXT,
                     font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold")).pack(
            anchor="w", padx=18, pady=(16, 8))
        self._switch(sec2, "Launch maximised (full screen)", "fullscreen")
        self._switch(sec2, "Notify when a run is done", "notify_done")
        self._switch(sec2, "Play a sound when done", "sound_done")
        self._switch(sec2, "Confirm before closing during a run", "confirm_close")
        self._switch(sec2, "Auto-download Hashcat when needed", "auto_hashcat")
        ctk.CTkLabel(sec2, text="").pack(pady=5)

        # Updates + about
        update_btn = ctk.CTkButton(
            content, text="Check for updates", height=38, corner_radius=self.R,
            command=self._check_updates, fg_color=FIELD_FG, hover_color=GHOST_HOVER,
            text_color=TEXT, border_width=1, border_color=GHOST_BORDER,
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"))
        update_btn.pack(fill="x", padx=22, pady=(8, 4))
        self._round.append(update_btn)

        about = ctk.CTkFrame(content, corner_radius=self.R, fg_color=CARD_FG,
                             border_width=1, border_color=GHOST_BORDER)
        about.pack(fill="x", padx=22, pady=8)
        self._round.append(about)
        ctk.CTkLabel(about, text="About", text_color=TEXT,
                     font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold")).pack(
            anchor="w", padx=18, pady=(16, 6))
        ctk.CTkLabel(about, justify="left", anchor="w", text_color=MUTED_TEXT,
                     font=ctk.CTkFont(family="Segoe UI", size=13),
                     text=(f"{__app_name__}  v{__version__}\n"
                           "License: MIT (free to use, modify, sell)\n"
                           "Author: Fallax Vision and contributors")).pack(
            anchor="w", padx=18, pady=(0, 10))
        github_btn = ctk.CTkButton(about, text="Open project on GitHub", height=42,
                      corner_radius=self.R,
                      fg_color="transparent", border_width=1, border_color=GHOST_BORDER,
                      text_color=TEXT, hover_color=GHOST_HOVER,
                      font=ctk.CTkFont(family="Segoe UI", size=14),
                      command=lambda: webbrowser.open(
                          "https://github.com/Fallax-Vision/doc_unlocker"))
        github_btn.pack(fill="x", padx=18, pady=(0, 16))
        self._round.append(github_btn)

    def _switch(self, parent, text, key):
        var = tk.BooleanVar(value=bool(self.settings.get(key)))

        def _toggle():
            self.settings[key] = bool(var.get())
            self._save_settings()

        sw = ctk.CTkSwitch(parent, text=text, variable=var, command=_toggle, height=36,
                           fg_color=("#d1d5db", "#374151"), progress_color=BLUE,
                           button_color=("#ffffff", "#f8fafc"),
                           button_hover_color=("#f8fafc", "#e5e7eb"),
                           text_color=TEXT,
                           font=ctk.CTkFont(family="Segoe UI", size=14))
        sw.pack(anchor="w", padx=18, pady=6)
        return sw

    def _on_theme(self, value):
        self.settings["theme"] = value
        self._save_settings()
        ctk.set_appearance_mode(value)
        self._refresh_theme_button()

    def toggle_theme(self):
        current = self.settings.get("theme", "System")
        if current == "Dark":
            new_theme = "Light"
        elif current == "Light":
            new_theme = "Dark"
        else:
            new_theme = "Dark" if ctk.get_appearance_mode() == "Light" else "Light"
        self._on_theme(new_theme)

    def _refresh_theme_button(self):
        try:
            mode = self.settings.get("theme", "System")
            if mode == "System":
                mode = ctk.get_appearance_mode()
            self.theme_btn.configure(text="Dark" if mode == "Light" else "Light")
        except Exception:
            pass

    def _on_corners(self, value):
        self.settings["corners"] = value
        self._save_settings()
        self._round = [widget for widget in self._round if widget.winfo_exists()]
        self.R = 14 if value == "Rounded" else 0
        for w in self._round:
            try:
                w.configure(corner_radius=self.R)
            except Exception:
                pass
        try:
            self.settings_btn.configure(corner_radius=self.R)
            self.theme_btn.configure(corner_radius=self.R)
        except Exception:
            pass

    def _check_updates(self):
        if self.update_thread is not None and self.update_thread.is_alive():
            return
        self._set_status("Checking for updates...")
        def work():
            try:
                req = urllib.request.Request(
                    "https://api.github.com/repos/Fallax-Vision/doc_unlocker/"
                    "releases/latest", headers={"User-Agent": "DocUnlocker"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    data = json.loads(r.read().decode("utf-8"))
                latest = (data.get("tag_name") or "").lstrip("v")
                if not latest:
                    msg = "No published releases were found yet."
                elif tuple(int(n) for n in latest.split(".")) > tuple(int(n) for n in __version__.split(".")):
                    msg = (f"A newer version is available: v{latest}\n"
                           f"You have v{__version__}.\n\n"
                           "Download it from the GitHub Releases page.")
                else:
                    msg = f"You're up to date (v{__version__})."
            except Exception as exc:
                msg = f"Update check failed:\n{exc}"
            self.q.put(("update_result", msg))

        self.update_thread = threading.Thread(target=work, daemon=True)
        self.update_thread.start()
        self.ensure_pump()

    def _save_settings(self):
        self._settings_dirty = True
        self.ensure_pump()

    def _flush_settings(self):
        if not self._settings_dirty or (self.settings_thread and self.settings_thread.is_alive()):
            return
        self._settings_dirty = False
        snapshot = dict(self.settings)
        def work():
            try:
                save_settings(snapshot)
            except Exception as exc:
                self.q.put(("settings_error", str(exc)))
        self.settings_thread = threading.Thread(target=work, daemon=True)
        self.settings_thread.start()

    # ---- notifications / close ---------------------------------------
    def _notify(self):
        if not self.settings.get("notify_done", True):
            return
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        except Exception:
            pass
        if self.settings.get("sound_done", True) and sys.platform == "win32":
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_OK)
            except Exception:
                pass

    def _on_close(self):
        if self.settings.get("confirm_close", True) and self._jobs_alive():
            if not messagebox.askyesno("Quit", "A run is in progress. Quit anyway?"):
                return
        self.stop_flag.set()
        if self.hc_proc is not None:
            try:
                self.hc_proc.terminate()
            except Exception:
                pass
        self._flush_settings()
        def close_when_saved():
            self._flush_settings()
            if self.settings_thread and self.settings_thread.is_alive():
                self.root.after(50, close_when_saved)
            else:
                self.root.destroy()
        close_when_saved()

    # ---- file pickers -------------------------------------------------
    def pick_doc(self):
        path = filedialog.askopenfilename(
            title="Select the locked document",
            filetypes=[
                ("All supported documents",
                 "*.docx *.docm *.xlsx *.xlsm *.pptx *.pptm "
                 "*.doc *.xls *.ppt *.pdf"),
                ("Word documents", "*.docx *.docm *.doc"),
                ("Excel workbooks", "*.xlsx *.xlsm *.xls"),
                ("PowerPoint presentations", "*.pptx *.pptm *.ppt"),
                ("PDF files", "*.pdf"),
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
        if self._jobs_alive():
            return
        doc = self.doc_var.get().strip().strip('"')
        if not doc or not os.path.isfile(doc):
            messagebox.showerror("Error", "Please choose a valid document path.")
            return
        wl = self.wl_var.get().strip().strip('"')
        if wl and not os.path.isfile(wl):
            messagebox.showerror("Error", "The wordlist path is not a valid file.")
            return
        options = (doc, wl or None, int(self.digits_var.get()), self.mut_var.get(),
                   self.two_var.get(), self.dates_var.get())
        self._set_busy()
        self.stop_flag.clear()
        self._set_status("Checking document...")
        def work():
            try:
                data = read_document(doc)
                protected = is_protected(data, detect_kind(doc))
                hc = find_hashcat()
                self.q.put(("precheck", options, protected, hc))
            except Exception as exc:
                self.q.put(("error", str(exc)))
        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()
        self.ensure_pump()

    def _start_checked(self, options, protected, hc):
        doc, wl, digits, mutations, two, dates = options
        if self.stop_flag.is_set():
            self.finish()
            self._set_status("Stopped.")
            return
        unsupported = os.path.splitext(doc)[1].lower() not in SUPPORTED_EXTS
        forced = unsupported or not protected
        if forced and not self._confirm_unencrypted(detect_kind(doc), unsupported):
            self.finish()
            self._set_status("Cancelled.")
            return
        if not forced and hc and detect_kind(doc) != "pdf":
            self._begin_gpu_run()
            self._set_status("GPU available. Starting Hashcat...")
            self.hc_run_thread = threading.Thread(
                target=self._run_hashcat_worker,
                args=(doc, wl, mutations, two, dates, hc), daemon=True)
            self.hc_run_thread.start()
            self.ensure_pump()
            return
        self.stop_flag.clear()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self._set_status("Reading file...")
        self.progress.set(0)
        self._update_progress_label(0)
        self.speed_lbl.configure(text="Speed: measuring...")
        self.eta_lbl.configure(text="Est. time left: -")
        self.worker = threading.Thread(
            target=self.run_crack,
            args=(doc, wl, digits, mutations, two, dates, forced), daemon=True)
        self.worker.start()
        self.ensure_pump()

    def _confirm_unencrypted(self, kind, unsupported=False):
        """Modal warning with 'OK, Cancel' and 'Continue'. Returns True to go on."""
        if unsupported:
            msg = ("Unsupported file type. Doc Unlocker handles Word, Excel, "
                   "PowerPoint and PDF. Open it in an app built for this format "
                   "first.\n\nContinue with the password guess anyway?")
        elif kind == "pdf":
            msg = ("This PDF doesn't look encrypted. Try opening it first in "
                   "Acrobat Reader, your web browser (Chrome/Edge), or "
                   "SumatraPDF – it may open with no password.\n\n"
                   "Continue with the password guess anyway?")
        else:
            msg = ("This file doesn't look encrypted. Try opening it first in "
                   "Word / Excel / PowerPoint, LibreOffice, Google Docs, or WPS "
                   "Office – it may open with no password.\n\n"
                   "Continue with the password guess anyway?")
        win = ctk.CTkToplevel(self.root)
        win.title("Heads up")
        win.transient(self.root)
        win.configure(fg_color=APP_BG)
        win.geometry(self._window_geometry(480, 290, divisor=2))
        win.after(150, lambda: win.winfo_exists() and win.grab_set())
        result = {"v": False}
        ctk.CTkLabel(win, text=msg, wraplength=430, justify="left").pack(
            padx=20, pady=(22, 16), anchor="w")
        row = ctk.CTkFrame(win, fg_color="transparent")
        row.pack(pady=6)

        def cancel():
            result["v"] = False
            win.destroy()

        def cont():
            result["v"] = True
            win.destroy()

        ctk.CTkButton(row, text="Cancel", command=cancel, width=150, height=38).pack(
            side="left", padx=8)
        ctk.CTkButton(row, text="Continue", command=cont, width=150, height=38,
                      fg_color="#b45309", hover_color="#92400e").pack(
            side="left", padx=8)
        win.protocol("WM_DELETE_WINDOW", cancel)
        win.bind("<Escape>", lambda _event: cancel())
        self.root.wait_window(win)
        return result["v"]

    def stop(self):
        self.stop_flag.set()
        self._set_status("Stopping...")
        if self.hc_proc is not None:
            try:
                self.hc_proc.terminate()
            except Exception:
                pass

    def run_crack(self, doc_path, wordlist, digit_len, use_mutations,
                  use_twoword, use_dates, force=False):
        session = None
        tries = 0
        new_tested = deque(maxlen=50000)
        try:
            file_bytes = read_document(doc_path)
            doc_kind = detect_kind(doc_path)
            if not force and not is_protected(file_bytes, doc_kind):
                self.q.put(("error", "This file is not password-protected."))
                return
            candidates, total = build_candidates(
                wordlist, digit_len, use_mutations, use_twoword, use_dates)
            self.q.put(("total", total))
            already = load_tested(doc_path)
            seen, new_tested = set(), deque(maxlen=50000)
            tries = skipped = 0
            found = None
            stopped = False
            session = RecoverySession(file_bytes, doc_kind, self.stop_flag)
            session.__enter__()
            plain = None
            if doc_kind == "pdf":
                plain = session.attempt("")
                if plain is not None:
                    found = ""
            start_t = time.time()
            last_update = start_t
            for pw in candidates:
                if found is not None:
                    break
                if self.stop_flag.is_set():
                    stopped = True
                    break
                if pw in seen:
                    continue
                if len(seen) >= 50000:
                    seen.clear()
                seen.add(pw)
                if attempt_digest(pw) in already:
                    skipped += 1
                    continue
                tries += 1
                if tries == 1 or time.time() - last_update >= 0.2:
                    last_update = time.time()
                    elapsed = time.time() - start_t
                    rate = tries / elapsed if elapsed > 0 else 0.0
                    remaining = max(0, total - tries - skipped)
                    eta = remaining / rate if rate > 0 else None
                    self.q.put(("progress", tries, pw, skipped, rate, eta, total))
                plain = session.attempt(pw)
                if plain is not None:
                    if self.stop_flag.is_set():
                        stopped = True
                        break
                    found = pw
                    break
                new_tested.append(pw)
            tested_file = append_tested(doc_path, new_tested)
            if found is None:
                msg_kind = "stopped" if stopped else "nofound"
                self.q.put((msg_kind, tries, len(new_tested), tested_file))
                return
            folder = os.path.dirname(doc_path)
            out_path = unlocked_path(doc_path)
            with open(out_path, "xb") as output:
                output.write(plain)
            log_path = write_log(folder, doc_path, found, tries, out_path)
            self.q.put(("found", tries, found, out_path, log_path))
        except RecoveryCancelled:
            tested_file = append_tested(doc_path, new_tested)
            self.q.put(("stopped", tries, len(new_tested), tested_file))
        except Exception as exc:
            self.q.put(("error", str(exc)))
        finally:
            if session is not None:
                session.close()

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
                if self.stop_flag.is_set():
                    raise RuntimeError("Export stopped.")
                if pw in seen or attempt_digest(pw) in already:
                    continue
                if len(seen) >= 50000:
                    seen.clear()
                seen.add(pw)
                if f.tell() + len(pw.encode("utf-8")) + 2 > 32 * 1024 * 1024:
                    raise ValueError("GPU wordlist exceeds the 32 MiB limit; use a smaller wordlist.")
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
        if detect_kind(doc) == "pdf":
            messagebox.showinfo(
                "Office only",
                "GPU acceleration (Hashcat) currently supports Microsoft Office "
                "files only (.docx / .xlsx / .pptx).\n\nFor PDFs, use "
                "'Start Unlocking' (CPU) or 'Unlock with known password'.")
            return True
        return False

    def _need_hashcat(self):
        """Return a hashcat path, or kick off auto-download / show a hint."""
        hc = find_hashcat()
        if hc:
            return hc
        if self.settings.get("auto_hashcat"):
            self.get_hashcat()
        else:
            messagebox.showwarning("Hashcat needed", "Click 'Get Hashcat' first.")
        return None

    def export_gpu(self):
        if self._jobs_alive():
            return
        doc = self.doc_var.get().strip().strip('"')
        if not doc or not os.path.isfile(doc):
            messagebox.showerror("Error", "Please choose a valid document path.")
            return
        if self._gpu_office_only(doc):
            return
        wl = self.wl_var.get().strip().strip('"')
        self.stop_flag.clear()
        self._set_busy()
        self._set_status("Building GPU package...")
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
            # Percent expansion is active even inside quoted cmd.exe arguments.
            hc, hash_ref, wl_ref = (value.replace("%", "%%") for value in (hc, hash_ref, wl_path))
            bat_path = os.path.join(folder, "run_hashcat.bat")
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(
                    "@echo off\r\nsetlocal DisableDelayedExpansion\r\n"
                    "REM Auto-generated by Doc Unlocker - GPU crack (-m 9600)\r\n\r\n"
                    'echo === Dictionary attack ===\r\n'
                    f'"{hc}" -m 9600 -a 0 "{hash_ref}" "{wl_ref}" -O -w 3 '
                    '--potfile-disable --restore-disable --logfile-disable\r\n\r\n'
                    "REM === Optional brute-force of 6-digit PINs ===\r\n"
                    f'REM "{hc}" -m 9600 -a 3 "{hash_ref}" ?d?d?d?d?d?d -O -w 3 '
                    '--potfile-disable --restore-disable --logfile-disable\r\n\r\n'
                    'echo Results are shown above; passwords are not saved.\r\n'
                    "pause\r\n")
            self.q.put(("gpu_done", count, wl_path, hash_path, bat_path,
                        hc if hc != "hashcat" else None, hash_note))
        except Exception as exc:
            self.q.put(("gpu_error", str(exc)))

    # ---- download Hashcat --------------------------------------------
    def get_hashcat(self):
        if self._jobs_alive():
            return
        if find_hashcat():
            messagebox.showinfo("Hashcat", f"Hashcat is already available:\n{find_hashcat()}")
            return
        if not messagebox.askyesno(
                "Download Hashcat",
                f"Hashcat {HASHCAT_VERSION} (the GPU cracker) is not installed.\n\n"
                "Download it now (~20 MB) and unpack it next to this tool?"):
            return
        self.stop_flag.clear()
        self._set_busy()
        self._set_status("Downloading Hashcat...")
        self.hc_thread = threading.Thread(target=self._get_hashcat_worker, daemon=True)
        self.hc_thread.start()
        self.ensure_pump()

    def _get_hashcat_worker(self):
        try:
            def progress(done, total):
                if self.stop_flag.is_set():
                    raise RecoveryCancelled("Download stopped.")
                if total > 0:
                    self.q.put(("hc_progress", done, total))
            exe = download_hashcat(progress_cb=progress)
            self.q.put(("hc_done", exe))
        except Exception as exc:
            self.q.put(("hc_error", str(exc)))

    # ---- test GPU -----------------------------------------------------
    def test_gpu(self):
        if self._jobs_alive():
            return
        hc = find_hashcat()
        if not hc:
            messagebox.showwarning("Hashcat needed",
                                   "Click 'Get Hashcat' first, then 'Test GPU'.")
            return
        self._set_status("Querying GPU devices...")
        self._set_busy()
        self.stop_flag.clear()
        self.hc_run_thread = threading.Thread(target=self._test_gpu_worker,
                                              args=(hc,), daemon=True)
        self.hc_run_thread.start()
        self.ensure_pump()

    def _test_gpu_worker(self, hc):
        try:
            proc = subprocess.Popen([hc, "-I"], cwd=os.path.dirname(hc) or None,
                                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, creationflags=_no_window())
            self.hc_proc = proc
            deadline = time.monotonic() + 120
            while True:
                if self.stop_flag.is_set() or time.monotonic() > deadline:
                    proc.kill()
                    proc.communicate()
                    raise RuntimeError("GPU test stopped or timed out.")
                try:
                    out, _ = proc.communicate(timeout=0.1)
                    break
                except subprocess.TimeoutExpired:
                    continue
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
        finally:
            self.hc_proc = None

    # ---- run Hashcat (dictionary) ------------------------------------
    def run_hashcat(self):
        if self._jobs_alive():
            return
        doc = self.doc_var.get().strip().strip('"')
        if not doc or not os.path.isfile(doc):
            messagebox.showerror("Error", "Please choose a valid document path.")
            return
        if self._gpu_office_only(doc):
            return
        hc = self._need_hashcat()
        if not hc:
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
        if self._jobs_alive():
            return
        doc = self.doc_var.get().strip().strip('"')
        if not doc or not os.path.isfile(doc):
            messagebox.showerror("Error", "Please choose a valid document path.")
            return
        if self._gpu_office_only(doc):
            return
        hc = self._need_hashcat()
        if not hc:
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

    def _queue_hashcat_metric(self, line):
        if ":" not in line:
            return
        label, value = line.split(":", 1)
        value = value.strip()
        if label.startswith("Progress"):
            m = re.search(r"([\d,]+)\s*/\s*([\d,]+)(?:\s+\(([\d.]+)%\))?", value)
            if m:
                done = int(m.group(1).replace(",", ""))
                total = int(m.group(2).replace(",", ""))
                pct = float(m.group(3)) / 100.0 if m.group(3) else done / max(1, total)
                self.q.put(("hcrun_progress", done, total, pct))
        elif label.startswith("Speed"):
            speed = re.sub(r"\s+", " ", value.split("(", 1)[0]).strip()
            if speed:
                self.q.put(("hcrun_speed", speed))
        elif label.startswith("Time.Estimated") and value:
            self.q.put(("hcrun_eta", value))
        elif label.startswith("Status") and value:
            self.q.put(("hcrun_status", "Hashcat: " + value))

    def _execute_hashcat(self, hc, hash_path, doc_path, attack_args, count):
        if self.stop_flag.is_set():
            self.q.put(("hcrun_stopped",))
            return
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
        cmd = [hc, "-m", "9600", "-O", "-w", "3", "--potfile-disable",
               "--restore-disable", "--logfile-disable",
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
                self._queue_hashcat_metric(line)
                self.q.put(("hcrun_status", "Hashcat: " + line[:80]))
        proc.wait()
        self.hc_proc = None
        joined = "\n".join(tail).lower()
        if "token length exception" in joined or "no hashes loaded" in joined:
            self.q.put(("hcrun_error",
                        "Hashcat could not load the hash.\n\n" + "\n".join(tail[-8:])))
            return
        try:
            pwd = read_cracked_password(hash_str, cracked, pot)
        finally:
            for path in (cracked, pot):
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass
        if not pwd:
            self.q.put(("hcrun_stopped",) if self.stop_flag.is_set()
                       else ("hcrun_nofound", count))
            return
        file_bytes = read_document(doc_path)
        with RecoverySession(file_bytes, detect_kind(doc_path), self.stop_flag) as session:
            plain = session.attempt(pwd)
        if plain is None:
            self.q.put(("hcrun_error",
                        f"Hashcat reported {pwd!r}, but it did not open the file."))
            return
        out_path = unlocked_path(doc_path)
        with open(out_path, "xb") as output:
            output.write(plain)
        log_path = write_log(folder, doc_path, pwd, count, out_path)
        self.q.put(("hcrun_found", pwd, out_path, log_path))

    def _ask_mask_params(self):
        win = ctk.CTkToplevel(self.root)
        win.title("GPU brute-force - all combinations")
        win.configure(fg_color=APP_BG)
        win.transient(self.root)
        win.geometry(self._window_geometry(460, 470, divisor=2))
        win.bind("<Escape>", lambda _event: win.destroy())
        win.after(200, lambda: win.winfo_exists() and win.grab_set())

        card = ctk.CTkFrame(win, corner_radius=self.R, fg_color=CARD_FG,
                            border_width=1, border_color=GHOST_BORDER)
        card.pack(fill="both", expand=True, padx=22, pady=22)
        self._round.append(card)

        ctk.CTkLabel(card, text="Try every combination of:",
                     text_color=TEXT,
                     font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold")
                     ).pack(anchor="w", padx=18, pady=(18, 8))
        cs_var = tk.IntVar(value=0)
        for i, (label, _ph, _c, _sz) in enumerate(self.MASK_CHARSETS):
            ctk.CTkRadioButton(card, text=label, variable=cs_var, value=i,
                               command=lambda: _update(), fg_color=BLUE,
                               hover_color=BLUE_HOVER, border_color=GHOST_BORDER,
                               text_color=TEXT,
                               font=ctk.CTkFont(family="Segoe UI", size=14)).pack(
                anchor="w", padx=22, pady=4)

        lrow = ctk.CTkFrame(card, fg_color="transparent")
        lrow.pack(fill="x", padx=18, pady=(12, 4))
        ctk.CTkLabel(lrow, text="Maximum length:", text_color=TEXT,
                     font=ctk.CTkFont(family="Segoe UI", size=14)).pack(side="left")
        len_var = tk.StringVar(value="6")
        length_menu = ctk.CTkOptionMenu(
            lrow, width=78, height=38, variable=len_var, corner_radius=self.R,
            values=[str(i) for i in range(1, 13)], fg_color=FIELD_FG,
            button_color=FIELD_FG, button_hover_color=GHOST_HOVER,
            text_color=TEXT, dropdown_fg_color=CARD_FG,
            dropdown_hover_color=GHOST_HOVER, dropdown_text_color=TEXT,
            font=ctk.CTkFont(family="Segoe UI", size=14),
            command=lambda *_: _update())
        length_menu.pack(side="left", padx=12)
        self._round.append(length_menu)

        info = ctk.CTkLabel(card, text="", justify="left", anchor="w",
                            text_color=WARNING, wraplength=390,
                            font=ctk.CTkFont(family="Segoe UI", size=13))
        info.pack(anchor="w", padx=18, pady=(8, 4))
        result = {"val": None}

        def _update(*_):
            size = self.MASK_CHARSETS[cs_var.get()][3]
            n = int(len_var.get() or 1)
            ks = sum(size ** i for i in range(1, n + 1))
            info.configure(text=(f"Combinations to try: {ks:,}\n"
                                 f"Worst-case at ~3,000 guesses/sec: "
                                 f"{format_duration(ks / 3000.0)}.\n"
                                 "Tip: digits or lowercase up to ~7 is realistic."))

        def _ok():
            _label, ph, custom, _sz = self.MASK_CHARSETS[cs_var.get()]
            result["val"] = (custom, ph * int(len_var.get() or 1))
            win.destroy()

        brow = ctk.CTkFrame(card, fg_color="transparent")
        brow.pack(fill="x", padx=18, pady=(10, 18))
        start = ctk.CTkButton(brow, text="Start brute-force", height=42,
                              corner_radius=self.R, command=_ok,
                              fg_color=PURPLE, hover_color=PURPLE_HOVER,
                              border_width=1, border_color=PURPLE_BORDER,
                              font=ctk.CTkFont(family="Segoe UI", size=14,
                                               weight="bold"))
        start.pack(side="left")
        self._round.append(start)
        cancel = ctk.CTkButton(brow, text="Cancel", height=42,
                      corner_radius=self.R, command=win.destroy,
                      fg_color="transparent", border_width=1, border_color=GHOST_BORDER,
                      text_color=TEXT, hover_color=GHOST_HOVER,
                      font=ctk.CTkFont(family="Segoe UI", size=14))
        cancel.pack(side="left", padx=10)
        self._round.append(cancel)
        _update()
        self.root.wait_window(win)
        return result["val"]

    # ---- unlock with a known password --------------------------------
    def _ask_password(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Unlock with known password")
        win.configure(fg_color=APP_BG)
        win.transient(self.root)
        win.geometry(self._window_geometry(460, 230, divisor=2))
        win.resizable(False, False)
        result = {"password": None}
        ctk.CTkLabel(win, text="Unlock with known password", text_color=TEXT,
                     font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=22, pady=(20, 8))
        ctk.CTkLabel(win, text="Enter the document password. The original file is preserved.",
                     text_color=MUTED_TEXT, wraplength=410, justify="left").pack(anchor="w", padx=22)
        entry = ctk.CTkEntry(win, show="*", height=38, corner_radius=self.R,
                             fg_color=FIELD_FG, border_color=GHOST_BORDER, text_color=TEXT)
        entry.pack(fill="x", padx=22, pady=12)
        def accept():
            result["password"] = entry.get()
            win.destroy()
        row = ctk.CTkFrame(win, fg_color="transparent")
        row.pack(fill="x", padx=22, pady=(0, 16))
        ctk.CTkButton(row, text="Unlock", height=38, corner_radius=self.R,
                      fg_color=BLUE, hover_color=BLUE_HOVER, command=accept).pack(side="right")
        ctk.CTkButton(row, text="Cancel", height=38, corner_radius=self.R,
                      fg_color="transparent", border_width=1, border_color=GHOST_BORDER,
                      text_color=TEXT, hover_color=GHOST_HOVER, command=win.destroy).pack(side="right", padx=(0, 10))
        win.bind("<Return>", lambda _event: accept())
        win.bind("<Escape>", lambda _event: win.destroy())
        def focus():
            if win.winfo_exists():
                win.grab_set()
                entry.focus_set()
        win.after(150, focus)
        self.root.wait_window(win)
        return result["password"]

    def unlock_known(self):
        if self._jobs_alive():
            return
        doc = self.doc_var.get().strip().strip('"')
        if not doc or not os.path.isfile(doc):
            messagebox.showerror("Error", "Please choose a valid document path.")
            return
        pw = self._ask_password()
        if pw is None:
            return
        self._set_busy()
        self.stop_flag.clear()
        self._set_status("Unlocking document...")
        self.worker = threading.Thread(target=self._unlock_known_worker, args=(doc, pw), daemon=True)
        self.worker.start()
        self.ensure_pump()

    def _unlock_known_worker(self, doc, pw):
        try:
            file_bytes = read_document(doc)
            kind = detect_kind(doc)
            with RecoverySession(file_bytes, kind, self.stop_flag) as session:
                plain = session.attempt(pw)
            if plain is None:
                self.q.put(("error", "That password did not work."))
                return
            if self.stop_flag.is_set():
                self.q.put(("error", "Unlock stopped."))
                return
            folder = os.path.dirname(doc)
            out_path = unlocked_path(doc)
            with open(out_path, "xb") as output:
                output.write(plain)
            log_path = write_log(folder, doc, pw, 0, out_path)
            self.q.put(("found", 1, pw, out_path, log_path))
        except RecoveryCancelled:
            self.q.put(("error", "Unlock stopped."))
        except Exception as exc:
            self.q.put(("error", str(exc)))

    # ---- run-state helpers -------------------------------------------
    def _begin_gpu_run(self):
        self.stop_flag.clear()
        self._set_busy()
        self._set_status("Preparing GPU run...")

    def finish(self):
        self._set_busy(False)

    def _set_busy(self, busy=True):
        for widget in (self.start_btn, self.unlock_btn, self.gpu_btn, self.bf_btn, self.more_actions_menu):
            widget.configure(state="disabled" if busy else "normal")
        self.stop_btn.configure(state="normal" if busy else "disabled")

    def _finish_hc(self):
        self.finish()

    def _jobs_alive(self):
        return any(t is not None and t.is_alive() for t in
                   (self.worker, self.gpu_thread, self.hc_thread, self.hc_run_thread))

    def ensure_pump(self):
        if not self._pump_active:
            self._pump_active = True
            self.root.after(100, self.pump)

    def _set_progress(self, value, total=None):
        if total is not None:
            self._ptotal = max(1, total)
        self._set_progress_fraction(value / self._ptotal)

    def _set_progress_fraction(self, pct):
        pct = min(1.0, max(0.0, pct))
        self.progress.set(pct)
        self._update_progress_label(pct)

    def _update_progress_label(self, pct):
        try:
            self.progress_pct.configure(text=f"{round(pct * 100):d}%")
        except Exception:
            pass

    # ---- UI pump (main thread) ---------------------------------------
    def pump(self):
        self._flush_settings()
        try:
            for _ in range(100):
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "precheck":
                    self._start_checked(*msg[1:])
                elif kind == "update_result":
                    if not self._jobs_alive():
                        self._set_status("Update check complete.")
                    messagebox.showinfo("Check for updates", msg[1])
                elif kind == "settings_error":
                    messagebox.showerror("Settings not saved", msg[1])
                elif kind == "total":
                    self._ptotal = max(1, msg[1])
                    self._set_progress_fraction(0)
                    self._set_status(f"Trying up to {msg[1]:,} passwords...")
                elif kind == "progress":
                    _, tries, pw, skipped, rate, eta, total = msg
                    self._set_progress(tries, total)
                    extra = f"   (skipped {skipped:,})" if skipped else ""
                    self.tries_lbl.configure(text=f"Tries: {tries:,}{extra}")
                    self.speed_lbl.configure(text=f"Speed: {rate:,.0f} pw/s")
                    self.eta_lbl.configure(text=f"Est. time left: {format_duration(eta)}")
                elif kind == "found":
                    _, tries, pw, out_path, log_path = msg
                    self._set_progress_fraction(1.0)
                    self.tries_lbl.configure(text=f"Tries: {tries:,}")
                    self.finish()
                    self._set_status("Unlocked copy saved.")
                    self._notify()
                    messagebox.showinfo("Password found!",
                                        f"Success!\n\nTries: {tries:,}\n"
                                        f"Password: {pw}\n\nUnlocked copy:\n{out_path}\n\n"
                                        f"Logged to:\n{log_path}")
                    break
                elif kind == "nofound":
                    _, tries, saved, tested_file = msg
                    self.finish()
                    self._set_status("Not found.")
                    self._notify()
                    messagebox.showwarning("Not found",
                                           f"Tried {tries:,} passwords.\nSaved "
                                           f"{saved:,} to:\n{tested_file}\n(skipped "
                                           "next time). Try the GPU options.")
                    break
                elif kind == "stopped":
                    _, tries, saved, tested_file = msg
                    self.finish()
                    self._set_status("Stopped.")
                    messagebox.showinfo("Stopped",
                                        f"Stopped after {tries:,} new tries.\n"
                                        f"Saved {saved:,} to:\n{tested_file}")
                    break
                elif kind == "error":
                    self.finish()
                    self._set_status("Error.")
                    messagebox.showerror("Error", msg[1])
                    break
                elif kind == "gpu_done":
                    _, count, wl_path, hash_path, bat_path, hc, note = msg
                    self.gpu_btn.configure(state="normal")
                    self._set_status("GPU package ready.")
                    extra = (f"Hashcat found:\n{hc}\n\nDouble-click:\n{bat_path}"
                             if hc else "Hashcat not installed - click 'Get Hashcat'.")
                    messagebox.showinfo("GPU package ready",
                                        f"Wrote {count:,} candidates to:\n{wl_path}\n\n"
                                        f"Hash:\n{hash_path or '(failed)'}\n\n"
                                        + extra + note)
                    break
                elif kind == "gpu_error":
                    self.gpu_btn.configure(state="normal")
                    self._set_status("GPU export failed.")
                    messagebox.showerror("GPU export failed", msg[1])
                    break
                elif kind == "hc_progress":
                    _, done, total = msg
                    self._set_progress_fraction(done / max(1, total))
                    self._set_status(
                        f"Downloading Hashcat... "
                        f"{done/1048576:.1f}/{total/1048576:.1f} MB")
                elif kind == "hc_done":
                    self.gpu_btn.configure(state="normal")
                    self.more_actions_menu.configure(state="normal")
                    self._set_status("Hashcat installed.")
                    messagebox.showinfo("Hashcat ready",
                                        f"Installed at:\n{msg[1]}\n\nNow use "
                                        "'Run Hashcat now' or 'GPU brute-force'.")
                    break
                elif kind == "hc_error":
                    self.gpu_btn.configure(state="normal")
                    self.more_actions_menu.configure(state="normal")
                    self._set_status("Hashcat download failed.")
                    messagebox.showerror("Hashcat download failed",
                                         msg[1] + "\n\nManual: https://hashcat.net/"
                                         "hashcat/ unzip into:\n" + app_dir())
                    break
                elif kind == "gpu_test":
                    self._set_status(msg[1])
                    messagebox.showinfo("Test GPU", msg[1] + "\n\n" + msg[2])
                    break
                elif kind == "gpu_test_error":
                    self._set_status("GPU test failed.")
                    messagebox.showerror("Test GPU failed", msg[1])
                    break
                elif kind == "hcrun_status":
                    self._set_status(msg[1])
                elif kind == "hcrun_progress":
                    _, done, total, pct = msg
                    self._ptotal = max(1, total)
                    self._set_progress_fraction(pct)
                    self.tries_lbl.configure(text=f"Tries: {done:,}")
                elif kind == "hcrun_speed":
                    self.speed_lbl.configure(text=f"Speed: {msg[1]}")
                elif kind == "hcrun_eta":
                    self.eta_lbl.configure(text=f"Est. time left: {msg[1]}")
                elif kind == "hcrun_found":
                    _, pw, out_path, log_path = msg
                    self._finish_hc()
                    self._set_status("GPU recovery complete. Unlocked copy saved.")
                    self._notify()
                    messagebox.showinfo("Password found (GPU)!",
                                        f"Hashcat cracked it!\n\nPassword: {pw}\n\n"
                                        f"Unlocked copy:\n{out_path}\n\nLogged to:\n{log_path}")
                    break
                elif kind == "hcrun_nofound":
                    self._finish_hc()
                    self._set_status("Not in wordlist.")
                    self._notify()
                    messagebox.showwarning("Not found (GPU)",
                                           "Hashcat finished the wordlist without "
                                           "finding the password. Try more options "
                                           "or GPU brute-force.")
                    break
                elif kind == "hcrun_stopped":
                    self._finish_hc()
                    self._set_status("GPU crack stopped.")
                    messagebox.showinfo("Stopped", "Hashcat was stopped.")
                    break
                elif kind == "hcrun_error":
                    self._finish_hc()
                    self._set_status("GPU crack failed.")
                    self._notify()
                    messagebox.showerror("Hashcat run failed", msg[1])
                    break
        except queue.Empty:
            pass
        background = any(t and t.is_alive() for t in (self.update_thread, self.settings_thread))
        if self._jobs_alive() or background or self._settings_dirty or not self.q.empty():
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
    root = ctk.CTk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
