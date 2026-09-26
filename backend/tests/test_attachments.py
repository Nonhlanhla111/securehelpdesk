import os
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.models import SecurityEvent
from tests.conftest import new_ticket

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


def up(client, headers, tid, name, data, ctype="application/octet-stream"):
    return client.post(f"/api/tickets/{tid}/attachments", headers=headers, files={"file": (name, data, ctype)})


def test_upload_and_download_roundtrip(client, h):
    t = new_ticket(client, h["emp"])
    r = up(client, h["emp"], t["id"], "screenshot.png", PNG, "image/png")
    assert r.status_code == 201
    a = r.json()
    assert a["original_filename"] == "screenshot.png" and a["content_type"] == "image/png"
    d = client.get(f"/api/tickets/{t['id']}/attachments/{a['id']}", headers=h["emp"])
    assert d.status_code == 200 and d.content == PNG
    assert d.headers["content-disposition"].startswith("attachment")
    assert d.headers["x-content-type-options"] == "nosniff"
    assert len(client.get(f"/api/tickets/{t['id']}/attachments", headers=h["emp"]).json()) == 1


def test_dangerous_extensions_rejected_and_logged(client, h, db):
    t = new_ticket(client, h["emp"])
    for name in ("evil.exe", "shell.php", "page.html", "script.js", "noext", "archive.zip", "x.svg"):
        assert up(client, h["emp"], t["id"], name, b"MZ....").status_code == 415, name
    assert db.scalar(select(SecurityEvent).where(SecurityEvent.event_type == "SUSPICIOUS_UPLOAD"))


def test_extension_spoofing_rejected_by_magic_bytes(client, h):
    t = new_ticket(client, h["emp"])
    assert up(client, h["emp"], t["id"], "cute.png", b"<html><script>alert(1)</script></html>").status_code == 400
    assert up(client, h["emp"], t["id"], "report.pdf", b"MZ\x90\x00 not a pdf").status_code == 400
    assert up(client, h["emp"], t["id"], "notes.txt", b"\x00\x01\x02binary\xff").status_code == 400
    assert up(client, h["emp"], t["id"], "photo.jpg", JPG).status_code == 201
    assert up(client, h["emp"], t["id"], "notes.txt", "Unicode ok: Zoë".encode()).status_code == 201


def test_oversized_and_empty_files_rejected(client, h):
    t = new_ticket(client, h["emp"])
    big = b"%PDF-" + b"0" * (get_settings().max_upload_bytes + 10)
    assert up(client, h["emp"], t["id"], "big.pdf", big).status_code == 413
    assert up(client, h["emp"], t["id"], "empty.txt", b"").status_code == 400


def test_path_traversal_filename_is_neutralised(client, h):
    t = new_ticket(client, h["emp"])
    r = up(client, h["emp"], t["id"], "../../../etc/passwd.txt", b"hello")
    assert r.status_code == 201
    assert "/" not in r.json()["original_filename"] and ".." not in r.json()["original_filename"].replace("passwd", "")
    root = Path(get_settings().upload_dir).resolve()
    stored = [p for p in root.iterdir()]
    assert stored and all(len(p.name) == 32 and p.name.isalnum() for p in stored)  # random hex names only


def test_other_employee_cannot_download(client, h):
    t = new_ticket(client, h["emp"])
    a = up(client, h["emp"], t["id"], "secret.txt", b"private").json()
    assert client.get(f"/api/tickets/{t['id']}/attachments/{a['id']}", headers=h["emp2"]).status_code == 404
    assert up(client, h["emp2"], t["id"], "x.txt", b"nope").status_code == 404


def test_attachment_id_from_other_ticket_not_reachable(client, h):
    t1 = new_ticket(client, h["emp"])
    t2 = new_ticket(client, h["emp2"])
    a = up(client, h["emp2"], t2["id"], "theirs.txt", b"data").json()
    # emp can see t1, but must not fetch t2's attachment through t1's URL
    assert client.get(f"/api/tickets/{t1['id']}/attachments/{a['id']}", headers=h["emp"]).status_code == 404


def test_deleting_ticket_removes_files(client, h):
    t = new_ticket(client, h["emp"])
    up(client, h["emp"], t["id"], "a.txt", b"data")
    root = Path(get_settings().upload_dir)
    before = len(list(root.iterdir()))
    assert client.delete(f"/api/tickets/{t['id']}", headers=h["admin"]).status_code == 204
    assert len(list(root.iterdir())) == before - 1
