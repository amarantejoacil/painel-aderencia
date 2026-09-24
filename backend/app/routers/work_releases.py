from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import WorkReleaseCreate, WorkReleaseOut
from app.services.work_releases import apply_work_release

router = APIRouter(prefix="/work-releases", tags=["work-releases"])


@router.post("", response_model=WorkReleaseOut, status_code=201)
def create_work_release(payload: WorkReleaseCreate, db: Session = Depends(get_db)) -> WorkReleaseOut:
    return apply_work_release(db, payload)
