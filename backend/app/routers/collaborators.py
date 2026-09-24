from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Collaborator
from app.schemas import CollaboratorCreate, CollaboratorDismissal, CollaboratorOut, CollaboratorUpdate


def _validate_employment_dates(start_date, end_date) -> None:
    if end_date is not None and end_date < start_date:
        raise HTTPException(
            status_code=422,
            detail="A data de saída não pode ser anterior à data de entrada.",
        )

router = APIRouter(prefix="/collaborators", tags=["collaborators"])


@router.get("", response_model=list[CollaboratorOut])
def list_collaborators(db: Session = Depends(get_db)) -> list[Collaborator]:
    return list(db.scalars(select(Collaborator).order_by(Collaborator.name)).all())


@router.post("", response_model=CollaboratorOut, status_code=201)
def create_collaborator(payload: CollaboratorCreate, db: Session = Depends(get_db)) -> Collaborator:
    _validate_employment_dates(payload.start_date, payload.end_date)
    collaborator = Collaborator(**payload.model_dump())
    db.add(collaborator)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Já existe um colaborador com este nome do Azure.")
    db.refresh(collaborator)
    return collaborator


@router.get("/{collaborator_id}", response_model=CollaboratorOut)
def get_collaborator(collaborator_id: int, db: Session = Depends(get_db)) -> Collaborator:
    collaborator = db.get(Collaborator, collaborator_id)
    if not collaborator:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado.")
    return collaborator


@router.patch("/{collaborator_id}", response_model=CollaboratorOut)
def update_collaborator(
    collaborator_id: int, payload: CollaboratorUpdate, db: Session = Depends(get_db)
) -> Collaborator:
    collaborator = db.get(Collaborator, collaborator_id)
    if not collaborator:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado.")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(collaborator, key, value)
    if collaborator.end_date is not None:
        collaborator.active = False
    _validate_employment_dates(collaborator.start_date, collaborator.end_date)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Já existe um colaborador com este nome do Azure.")
    db.refresh(collaborator)
    return collaborator


@router.post("/{collaborator_id}/dismissal", response_model=CollaboratorOut)
def register_dismissal(
    collaborator_id: int,
    payload: CollaboratorDismissal,
    db: Session = Depends(get_db),
) -> Collaborator:
    collaborator = db.get(Collaborator, collaborator_id)
    if not collaborator:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado.")
    if payload.end_date < collaborator.start_date:
        raise HTTPException(
            status_code=422,
            detail="A data de desligamento não pode ser anterior à data de entrada.",
        )
    collaborator.end_date = payload.end_date
    collaborator.active = False
    db.commit()
    db.refresh(collaborator)
    return collaborator


@router.delete("/{collaborator_id}", status_code=204)
def delete_collaborator(collaborator_id: int, db: Session = Depends(get_db)) -> None:
    collaborator = db.get(Collaborator, collaborator_id)
    if not collaborator:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado.")
    db.delete(collaborator)
    db.commit()
