import os
import re
import shutil
import uuid
from datetime import date
from pathlib import Path
from typing import Annotated

import structlog
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.models import User
from app.db.session import get_db
from app.schemas.field_event import (
    EventType,
    FieldEventCreate,
    FieldEventResponse,
    FieldEventUpdate,
)
from app.services import field_event as event_service

router = APIRouter(prefix="/events", tags=["events"])
log = structlog.get_logger()

ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ALLOWED_PHOTO_MIME = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}


def _events_dir(event_id: int) -> Path:
    settings = get_settings()
    base = Path(settings.UPLOAD_DIR) / "events" / str(event_id)
    return base


def _photo_url(event_id: int, filename: str) -> str:
    return f"/uploads/events/{event_id}/{filename}"


def _safe_filename(name: str) -> str:
    # strip path components, allow only safe chars
    base = os.path.basename(name)
    return re.sub(r"[^A-Za-z0-9._-]", "_", base)[:120] or "file"


@router.get(
    "",
    response_model=list[FieldEventResponse],
    summary="List field events with filters",
)
async def list_events(
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    location_id: Annotated[int | None, Query(ge=1)] = None,
    event_type: Annotated[EventType | None, Query()] = None,
    crop_id: Annotated[int | None, Query(ge=1)] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
):
    items = await event_service.list_events(
        session,
        location_id=location_id,
        event_type=event_type,
        crop_id=crop_id,
        date_from=date_from,
        date_to=date_to,
    )
    return list(items)


@router.post(
    "",
    response_model=FieldEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create field event",
)
async def create_event(
    body: FieldEventCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
):
    obj = await event_service.create_event(session, body)
    log.info(
        "event.created",
        id=obj.id,
        location_id=obj.location_id,
        type=obj.event_type,
    )
    return obj


@router.get(
    "/{event_id}",
    response_model=FieldEventResponse,
    summary="Get field event by ID",
)
async def get_event(
    event_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
):
    obj = await event_service.get_event(session, event_id)
    if not obj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    return obj


@router.put(
    "/{event_id}",
    response_model=FieldEventResponse,
    summary="Partial update of field event",
)
async def update_event(
    event_id: int,
    body: FieldEventUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
):
    obj = await event_service.update_event(session, event_id, body)
    if not obj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    log.info("event.updated", id=event_id)
    return obj


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete field event (and its photos)",
)
async def delete_event(
    event_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> None:
    obj = await event_service.delete_event(session, event_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    # best-effort cleanup of files
    folder = _events_dir(event_id)
    if folder.exists():
        shutil.rmtree(folder, ignore_errors=True)
    log.info("event.deleted", id=event_id)


@router.post(
    "/{event_id}/photos",
    response_model=FieldEventResponse,
    summary="Upload photos for an event (multipart, up to MAX_PHOTOS_PER_EVENT)",
)
async def upload_photos(
    event_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    files: Annotated[list[UploadFile], File(description="Image files")],
):
    settings = get_settings()
    obj = await event_service.get_event(session, event_id)
    if not obj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")

    if not files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No files provided")

    max_photos = settings.MAX_PHOTOS_PER_EVENT
    existing = len(obj.photos)
    if existing + len(files) > max_photos:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Photo limit exceeded: max {max_photos}, already {existing}, "
            f"adding {len(files)}",
        )

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    folder = _events_dir(event_id)
    folder.mkdir(parents=True, exist_ok=True)

    saved_paths: list[Path] = []
    saved_urls: list[str] = []
    try:
        for upload in files:
            ext = Path(_safe_filename(upload.filename or "")).suffix.lower()
            if ext not in ALLOWED_PHOTO_EXTENSIONS:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"Unsupported file extension: {ext or '(none)'}",
                )
            if (
                upload.content_type
                and upload.content_type not in ALLOWED_PHOTO_MIME
            ):
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"Unsupported content-type: {upload.content_type}",
                )
            filename = f"{uuid.uuid4().hex}{ext}"
            target = folder / filename

            written = 0
            with target.open("wb") as out:
                while True:
                    chunk = await upload.read(1024 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > max_bytes:
                        raise HTTPException(
                            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            f"File exceeds {settings.MAX_UPLOAD_SIZE_MB} MB limit",
                        )
                    out.write(chunk)

            saved_paths.append(target)
            saved_urls.append(_photo_url(event_id, filename))
    except HTTPException:
        for p in saved_paths:
            p.unlink(missing_ok=True)
        raise
    except Exception:
        for p in saved_paths:
            p.unlink(missing_ok=True)
        raise

    obj = await event_service.add_photos(session, obj, saved_urls)
    log.info(
        "event.photos.added",
        id=event_id,
        added=len(saved_urls),
        total=len(obj.photos),
    )
    return obj


@router.delete(
    "/{event_id}/photos/{filename}",
    response_model=FieldEventResponse,
    summary="Delete a single photo from an event",
)
async def delete_photo(
    event_id: int,
    filename: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
):
    obj = await event_service.get_event(session, event_id)
    if not obj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")

    safe = _safe_filename(filename)
    if safe != filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid filename")

    url = _photo_url(event_id, safe)
    if url not in obj.photos:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo not found")

    target = _events_dir(event_id) / safe
    target.unlink(missing_ok=True)
    obj = await event_service.remove_photo(session, obj, url)
    log.info("event.photo.deleted", id=event_id, file=safe)
    return obj
