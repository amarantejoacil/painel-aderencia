from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Collaborator
from app.services.activities_export import (
    build_activities_workbook,
    build_export_filename,
    fetch_activities,
)

router = APIRouter(prefix="/activities", tags=["activities"])


@router.get("/export")
def export_activities_excel(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    collaborator_id: int | None = None,
    db: Session = Depends(get_db),
) -> Response:
    collaborator: Collaborator | None = None
    if collaborator_id is not None:
        collaborator = db.get(Collaborator, collaborator_id)
        if not collaborator:
            raise HTTPException(status_code=404, detail="Colaborador não encontrado.")

    activities = fetch_activities(db, year, month, collaborator_id)
    workbook = build_activities_workbook(activities)
    filename = build_export_filename(year, month, collaborator)

    return Response(
        content=workbook.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
