import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_id
from app.db import get_db
from app.models import Job, JobNote
from app.schemas import JobNoteOut, NoteUpdate

router = APIRouter(prefix="/notes", tags=["notes"])


async def _get_owned_note_or_404(
    db: AsyncSession, note_id: uuid.UUID, user_id: uuid.UUID
) -> JobNote:
    stmt = select(JobNote).join(Job, Job.id == JobNote.job_id).where(
        JobNote.id == note_id, Job.user_id == user_id
    )
    note = (await db.execute(stmt)).scalar_one_or_none()
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.patch("/{note_id}", response_model=JobNoteOut)
async def update_note(
    note_id: uuid.UUID,
    body: NoteUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> JobNote:
    note = await _get_owned_note_or_404(db, note_id, user_id)
    note.body = body.body
    await db.commit()
    await db.refresh(note)
    return note


@router.delete("/{note_id}", status_code=204)
async def delete_note(
    note_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> None:
    note = await _get_owned_note_or_404(db, note_id, user_id)
    await db.delete(note)
    await db.commit()
