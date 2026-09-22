import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_auth
from app.db import get_db
from app.models import JobNote
from app.schemas import JobNoteOut, NoteUpdate

router = APIRouter(prefix="/notes", tags=["notes"], dependencies=[Depends(require_auth)])


async def _get_note_or_404(db: AsyncSession, note_id: uuid.UUID) -> JobNote:
    note = await db.get(JobNote, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.patch("/{note_id}", response_model=JobNoteOut)
async def update_note(
    note_id: uuid.UUID, body: NoteUpdate, db: AsyncSession = Depends(get_db)
) -> JobNote:
    note = await _get_note_or_404(db, note_id)
    note.body = body.body
    await db.commit()
    await db.refresh(note)
    return note


@router.delete("/{note_id}", status_code=204)
async def delete_note(note_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    note = await _get_note_or_404(db, note_id)
    await db.delete(note)
    await db.commit()
