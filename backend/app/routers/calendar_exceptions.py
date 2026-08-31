from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CalendarException
from app.schemas import CalendarExceptionCreate, CalendarExceptionOut

router = APIRouter(prefix="/calendar-exceptions", tags=["calendar"])


@router.get("", response_model=list[CalendarExceptionOut])
def list_exceptions(db: Session = Depends(get_db)) -> list[CalendarException]:
    return list(db.scalars(select(CalendarException).order_by(CalendarException.date)).all())


@router.post("", response_model=CalendarExceptionOut, status_code=201)
def create_exception(payload: CalendarExceptionCreate, db: Session = Depends(get_db)) -> CalendarException:
    item = CalendarException(**payload.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Já existe uma exceção cadastrada nesta data.")
    db.refresh(item)
    return item


@router.delete("/{exception_id}", status_code=204)
def delete_exception(exception_id: int, db: Session = Depends(get_db)) -> None:
    item = db.get(CalendarException, exception_id)
    if not item:
        raise HTTPException(status_code=404, detail="Exceção não encontrada.")
    db.delete(item)
    db.commit()
