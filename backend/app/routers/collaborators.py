from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Collaborator
from app.schemas import CollaboratorCreate, CollaboratorOut, CollaboratorUpdate

router = APIRouter(prefix="/collaborators", tags=["collaborators"])


@router.get("", response_model=list[CollaboratorOut])
def list_collaborators(db: Session = Depends(get_db)) -> list[Collaborator]:
    return list(db.scalars(select(Collaborator).order_by(Collaborator.name)).all())


@router.post("", response_model=CollaboratorOut, status_code=201)
def create_collaborator(payload: CollaboratorCreate, db: Session = Depends(get_db)) -> Collaborator:
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
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Já existe um colaborador com este nome do Azure.")
    db.refresh(collaborator)
    return collaborator


@router.delete("/{collaborator_id}", status_code=204)
def delete_collaborator(collaborator_id: int, db: Session = Depends(get_db)) -> None:
    collaborator = db.get(Collaborator, collaborator_id)
    if not collaborator:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado.")
    db.delete(collaborator)
    db.commit()
