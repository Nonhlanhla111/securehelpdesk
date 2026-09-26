"""File upload/download for tickets, with strict validation.

Defences: extension allow-list, size cap, magic-byte check (the file must really be
what its extension claims), random server-side filename (no path traversal / overwrite),
served as a download with nosniff so a browser never executes it.
"""
import os
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import audit, client_ip, security_event
from app.config import get_settings
from app.constants import StatusName
from app.database import get_db
from app.deps import get_current_user
from app.models import Attachment, User, utcnow
from app.schemas import AttachmentOut
from app.services import add_history, get_visible_ticket

settings = get_settings()
router = APIRouter(prefix="/api/tickets/{ticket_id}/attachments", tags=["Attachments"])

ALLOWED = {
    ".png": ("image/png", lambda b: b.startswith(b"\x89PNG\r\n\x1a\n")),
    ".jpg": ("image/jpeg", lambda b: b.startswith(b"\xff\xd8\xff")),
    ".jpeg": ("image/jpeg", lambda b: b.startswith(b"\xff\xd8\xff")),
    ".pdf": ("application/pdf", lambda b: b.startswith(b"%PDF-")),
    ".txt": ("text/plain", None),
    ".log": ("text/plain", None),
}
_UNSAFE = re.compile(r"[^\w.\- ]", re.UNICODE)


def _upload_root() -> Path:
    p = Path(settings.upload_dir).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _safe_display_name(name: str) -> str:
    name = os.path.basename((name or "file").replace("\\", "/"))
    return _UNSAFE.sub("_", name)[:200] or "file"


def _looks_like_text(data: bytes) -> bool:
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def delete_files_for_ticket(stored_names: list[str]) -> None:
    root = _upload_root()
    for n in stored_names:
        try:
            (root / n).unlink(missing_ok=True)
        except OSError:
            pass


@router.post("", response_model=AttachmentOut, status_code=201)
async def upload_attachment(ticket_id: int, file: UploadFile, request: Request,
                            user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ticket = get_visible_ticket(db, user, ticket_id, request)
    if ticket.status.name == StatusName.CLOSED.value:
        raise HTTPException(status_code=409, detail="Closed tickets cannot receive new attachments")

    display = _safe_display_name(file.filename or "")
    ext = os.path.splitext(display)[1].lower()
    ip = client_ip(request)

    def reject(reason: str, status: int = 400):
        audit(db, "UPLOAD_REJECTED", user_id=user.id, entity_type="Ticket", entity_id=ticket.id, ip=ip,
              details=f"{display}: {reason}")
        security_event(db, "SUSPICIOUS_UPLOAD", "Low", f"{user.email} upload rejected ({reason}): {display}",
                       user_id=user.id, ip=ip)
        db.commit()
        raise HTTPException(status_code=status, detail=reason)

    if ext not in ALLOWED:
        reject(f"File type not allowed. Allowed: {', '.join(sorted(ALLOWED))}", 415)

    data = await file.read(settings.max_upload_bytes + 1)  # never read more than the limit
    if len(data) > settings.max_upload_bytes:
        reject(f"File too large (limit {settings.max_upload_bytes // (1024 * 1024)} MB)", 413)
    if len(data) == 0:
        reject("File is empty")

    content_type, magic_ok = ALLOWED[ext]
    valid = magic_ok(data) if magic_ok else _looks_like_text(data)
    if not valid:
        reject("File contents do not match its extension")

    stored = uuid.uuid4().hex
    (_upload_root() / stored).write_bytes(data)
    att = Attachment(ticket_id=ticket.id, uploaded_by_id=user.id, original_filename=display,
                     stored_filename=stored, content_type=content_type, size_bytes=len(data))
    db.add(att)
    ticket.updated_at = utcnow()
    db.flush()
    add_history(db, ticket, user, "attachment", None, display)
    audit(db, "ATTACHMENT_UPLOADED", user_id=user.id, entity_type="Ticket", entity_id=ticket.id, ip=ip,
          details=f"{display} ({len(data)} bytes)")
    db.commit()
    db.refresh(att)
    return att


@router.get("", response_model=list[AttachmentOut])
def list_attachments(ticket_id: int, request: Request, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    ticket = get_visible_ticket(db, user, ticket_id, request)
    return ticket.attachments


@router.get("/{attachment_id}")
def download_attachment(ticket_id: int, attachment_id: int, request: Request,
                        user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ticket = get_visible_ticket(db, user, ticket_id, request)
    att = db.scalar(select(Attachment).where(Attachment.id == attachment_id,
                                             Attachment.ticket_id == ticket.id))
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")
    path = _upload_root() / att.stored_filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File missing from storage")
    audit(db, "ATTACHMENT_DOWNLOADED", user_id=user.id, entity_type="Attachment", entity_id=att.id,
          ip=client_ip(request))
    db.commit()
    return FileResponse(path, media_type=att.content_type, filename=att.original_filename,
                        content_disposition_type="attachment")
