from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Collaborator, CollaboratorAbsence
from app.schemas import CollaboratorAbsenceCreate, CollaboratorAbsenceOut

router = APIRouter(prefix="/collaborators/{collaborator_id}/absences", tags=["collaborator-absences"])


def _get_collaborator(db: Session, collaborator_id: int) -> Collaborator:
    collaborator = db.get(Collaborator, collaborator_id)
    if not collaborator:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado.")
    return collaborator


@router.get("", response_model=list[CollaboratorAbsenceOut])
def list_absences(collaborator_id: int, db: Session = Depends(get_db)) -> list[CollaboratorAbsence]:
    _get_collaborator(db, collaborator_id)
    return list(
        db.scalars(
            select(CollaboratorAbsence)
            .where(CollaboratorAbsence.collaborator_id == collaborator_id)
            .order_by(CollaboratorAbsence.start_date.desc())
        ).all()
    )


@router.post("", response_model=CollaboratorAbsenceOut, status_code=201)
def create_absence(
    collaborator_id: int,
    payload: CollaboratorAbsenceCreate,
    db: Session = Depends(get_db),
) -> CollaboratorAbsence:
    _get_collaborator(db, collaborator_id)
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=422, detail="A data final deve ser igual ou posterior à data inicial.")
    absence = CollaboratorAbsence(collaborator_id=collaborator_id, **payload.model_dump())
    db.add(absence)
    db.commit()
    db.refresh(absence)
    return absence


@router.delete("/{absence_id}", status_code=204)
def delete_absence(collaborator_id: int, absence_id: int, db: Session = Depends(get_db)) -> None:
    _get_collaborator(db, collaborator_id)
    absence = db.get(CollaboratorAbsence, absence_id)
    if not absence or absence.collaborator_id != collaborator_id:
        raise HTTPException(status_code=404, detail="Ausência não encontrada.")
    db.delete(absence)
    db.commit()
