import io
import itertools
from pathlib import Path
import queue
import threading
import time

import pytest
import pypdf

import doc_unlocker as app
import maintenance


def encrypted_pdf():
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("test-password")
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


def test_pdf_password_and_output_preservation(tmp_path):
    data = encrypted_pdf()
    assert not app.test_password(data, "wrong", "pdf")
    assert app.test_password(data, "test-password", "pdf")
    source = tmp_path / "source.pdf"
    source.write_bytes(data)
    output = app.unlocked_path(str(source))
    app.decrypt_to(data, "test-password", output, "pdf")
    assert not pypdf.PdfReader(output).is_encrypted
    assert app.unlocked_path(str(source)) != output
    with pytest.raises(FileExistsError):
        app.decrypt_to(data, "test-password", output, "pdf")
    assert source.read_bytes() == data


def test_resume_migrates_plaintext_and_caps_history(tmp_path):
    document = str(tmp_path / "a.docx")
    path = Path(app.tested_path_for(document))
    path.write_text("old-secret\n", encoding="utf-8")
    assert app.attempt_digest("old-secret") in app.load_tested(document)
    app.append_tested(document, ["new-secret"])
    assert "old-secret" not in path.read_text()
    assert app.attempt_digest("new-secret") in app.load_tested(document)
    app.append_tested(document, map(str, range(51000)))
    assert len(path.read_text().splitlines()) == 50000
    assert app.attempt_digest("50999") in app.load_tested(document)


def test_logs_do_not_contain_password_and_rotate(tmp_path):
    log = tmp_path / "DocUnlocker_found.log"
    for _ in range(4):
        log.write_bytes(b"x" * 1048576)
        app.write_log(str(tmp_path), "a.docx", "private-secret", 10, "Unlocked_a.docx")
    assert "private-secret" not in log.read_text()
    assert {p.name for p in tmp_path.glob("*.log*")} == {
        "DocUnlocker_found.log", "DocUnlocker_found.log.1", "DocUnlocker_found.log.2"}


def test_input_limits(tmp_path, monkeypatch):
    source = tmp_path / "large.docx"
    source.write_bytes(b"x" * 11)
    monkeypatch.setattr(app, "MAX_DOCUMENT_BYTES", 10)
    with pytest.raises(ValueError, match="64 MiB"):
        app.read_document(source)
    wordlist = tmp_path / "words.txt"
    wordlist.write_text("x" * 1025)
    with pytest.raises(ValueError, match="1,024"):
        list(app._read_lines(wordlist))


def test_settings_reject_invalid_values_and_write_atomically(tmp_path, monkeypatch):
    settings = tmp_path / "settings.json"
    monkeypatch.setattr(app, "SETTINGS_PATH", str(settings))
    settings.write_text('{"theme":"invalid","corners":99,"fullscreen":"yes"}')
    assert app.load_settings() == app.DEFAULT_SETTINGS
    app.save_settings(dict(app.DEFAULT_SETTINGS, theme="Dark"))
    assert app.load_settings()["theme"] == "Dark"
    assert list(tmp_path.glob(".docunlocker-*")) == []


def test_legacy_office_load_key_contract(monkeypatch):
    class LegacyDocument:
        format = "doc97"
        def load_key(self, password=None):
            assert password == "secret"
        def decrypt(self, output):
            output.write(b"\xd0\xcf\x11\xe0legacy")
    monkeypatch.setattr(app.msoffcrypto, "OfficeFile", lambda *_: LegacyDocument())
    assert app._office_decrypt_bytes(b"fixture", "secret").endswith(b"legacy")


def _slow_password_worker(data, kind, requests, results):
    results.put(("ready", None))
    requests.get()
    time.sleep(30)


def test_stop_terminates_stalled_password_library(monkeypatch):
    monkeypatch.setattr(app, "_password_worker", _slow_password_worker)
    stop = threading.Event()
    with pytest.raises(app.RecoveryCancelled):
        with app.RecoverySession(b"fixture", "office", stop) as session:
            start = time.monotonic()
            timer = threading.Timer(0.15, stop.set)
            timer.start()
            try:
                session.attempt("secret")
            finally:
                timer.join()
    assert time.monotonic() - start < 3
    assert not session.process.is_alive()


def test_oversized_resume_and_legacy_log_migration(tmp_path):
    document = str(tmp_path / "document.docx")
    history = Path(app.tested_path_for(document))
    history.write_bytes(b"x" * (5 * 1024 * 1024) + b"\nrecent\n")
    assert app.load_tested(document) == {app.attempt_digest("recent")}
    log = tmp_path / "DocUnlocker_found.log"
    log.write_text("[old] file='a' password='legacy-secret' tries=5 unlocked='b'\n")
    app.write_log(str(tmp_path), "a", "new-secret", 1, "b")
    assert "secret" not in log.read_text()


def test_retention_preserves_latest_three_per_platform_and_user_files(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    for version, suffix in itertools.product(range(1, 6), ("exe", "apk")):
        (dist / f"DocUnlocker-v1.0.{version}.{suffix}").write_text("build")
    protected = dist / "my-important-backup.zip"
    protected.write_text("user")
    maintenance.clean(tmp_path, apply=True)
    assert len(list(dist.glob("*.exe"))) == 3
    assert (dist / "DocUnlocker-v1.0.5.apk").exists()
    assert protected.exists()


def test_cpu_worker_reports_result_and_hashed_resume(tmp_path, monkeypatch):
    source = tmp_path / "source.pdf"
    source.write_bytes(encrypted_pdf())
    instance = object.__new__(app.App)
    instance.q = queue.Queue()
    instance.stop_flag = threading.Event()
    monkeypatch.setattr(app, "build_candidates", lambda *args: (iter(["wrong", "test-password"]), 2))
    instance.run_crack(str(source), None, 1, False, False, False)
    messages = list(instance.q.queue)
    assert messages[-1][0] == "found"
    assert messages[-1][2] == "test-password"
    assert app.attempt_digest("wrong") in app.load_tested(str(source))


def test_known_password_work_is_dispatched_off_ui_thread(tmp_path, monkeypatch):
    source = tmp_path / "source.pdf"
    source.write_bytes(encrypted_pdf())
    root = app.ctk.CTk()
    root.withdraw()
    monkeypatch.setattr(app, "SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(app.App, "_ask_password", lambda *_: "test-password")
    monkeypatch.setattr(app.messagebox, "showinfo", lambda *args, **kw: None)
    instance = app.App(root)
    instance.settings["notify_done"] = False
    instance.doc_var.set(str(source))
    main_thread = threading.get_ident()
    actual = app.read_document
    called = []
    def slow_read(path):
        called.append(threading.get_ident())
        time.sleep(0.08)
        return actual(path)
    monkeypatch.setattr(app, "read_document", slow_read)
    instance.unlock_known()
    ticks = []
    root.after(5, lambda: ticks.append(True))
    deadline = time.monotonic() + 4
    try:
        while (instance._pump_active or instance._jobs_alive()) and time.monotonic() < deadline:
            root.update()
            time.sleep(0.005)
        assert called and called[0] != main_thread
        assert ticks and (tmp_path / "Unlocked_source.pdf").exists()
        assert instance.start_btn.cget("state") == "normal"
    finally:
        root.destroy()
