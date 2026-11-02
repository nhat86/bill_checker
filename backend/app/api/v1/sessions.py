import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.db import get_db
from app.core.security import get_current_user
from app.models import AuditSession, BasketItem, Receipt, User
from app.schemas import AuditSessionDetailOut, AuditSessionOut, UploadResult
from app.services import get_storage

router = APIRouter(prefix="/sessions", tags=["sessions"])

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/heic": "heic",
}


def _owned_session(session_id: uuid.UUID, user: User, db: Session) -> AuditSession:
    """Load a session owned by the user — 404 (not 403) to avoid leaking existence."""
    session = db.get(AuditSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session introuvable")
    return session


async def _read_image(file: UploadFile) -> tuple[bytes, str]:
    """Validate content type + size, return (bytes, extension)."""
    ext = ALLOWED_IMAGE_TYPES.get(file.content_type or "")
    if ext is None:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Format non supporté — JPEG, PNG, WEBP ou HEIC",
        )
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"Fichier trop volumineux (max {settings.max_upload_mb} Mo)",
        )
    return data, ext


@router.post("", response_model=AuditSessionOut, status_code=status.HTTP_201_CREATED)
def create_session(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = AuditSession(user_id=user.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return AuditSessionOut.model_validate(session)


@router.get("", response_model=list[AuditSessionOut])
def list_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sessions = db.scalars(
        select(AuditSession)
        .where(AuditSession.user_id == user.id)
        .order_by(AuditSession.created_at.desc())
    ).all()
    return [AuditSessionOut.model_validate(s) for s in sessions]


@router.get("/{session_id}", response_model=AuditSessionDetailOut)
def get_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _owned_session(session_id, user, db)
    # eager-load children in 2 extra queries instead of 1+N (N+1 problem)
    stmt = (
        select(AuditSession)
        .where(AuditSession.id == session.id)
        .options(
            selectinload(AuditSession.basket_items),
            selectinload(AuditSession.receipts).selectinload(Receipt.items),
        )
    )
    return AuditSessionDetailOut.model_validate(db.scalar(stmt))


@router.post("/{session_id}/basket-photos", response_model=UploadResult, status_code=status.HTTP_201_CREATED)
async def upload_basket_photo(
    session_id: uuid.UUID,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _owned_session(session_id, user, db)
    data, ext = await _read_image(file)

    key = f"sessions/{session.id}/basket/{uuid.uuid4().hex}.{ext}"
    get_storage().put(key, data, content_type=file.content_type)

    item = BasketItem(session_id=session.id, image_ref=key)
    db.add(item)
    session.status = "PRODUCTS_CAPTURED"
    db.commit()
    return UploadResult(
        object_key=key, kind="basket_photo", session_id=session.id,
        size_bytes=len(data), content_type=file.content_type,
    )


@router.post("/{session_id}/receipt", response_model=UploadResult, status_code=status.HTTP_201_CREATED)
async def upload_receipt(
    session_id: uuid.UUID,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _owned_session(session_id, user, db)
    data, ext = await _read_image(file)

    key = f"sessions/{session.id}/receipts/{uuid.uuid4().hex}.{ext}"
    get_storage().put(key, data, content_type=file.content_type)

    receipt = Receipt(session_id=session.id, image_ref=key)
    db.add(receipt)
    session.status = "RECEIPT_UPLOADED"
    db.commit()
    return UploadResult(
        object_key=key, kind="receipt", session_id=session.id,
        size_bytes=len(data), content_type=file.content_type,
    )
