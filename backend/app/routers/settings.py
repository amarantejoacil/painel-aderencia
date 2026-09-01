from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import AzureDevOpsSettingsOut, AzureDevOpsSettingsUpdate, AzureDevOpsTestOut
from app.services.azure_devops_config import (
    build_service,
    get_config_view,
    is_configured,
    record_test_result,
    save_settings,
)
from app.services.azure_devops_errors import (
    AzureDevOpsAuthError,
    AzureDevOpsConfigError,
    AzureDevOpsConnectionError,
    AzureDevOpsError,
)

router = APIRouter(prefix="/settings", tags=["settings"])

GENERIC_CONNECTION_MESSAGE = "Não foi possível conectar ao Azure DevOps."


def _friendly_error(exc: AzureDevOpsError) -> str:
    if isinstance(exc, AzureDevOpsAuthError):
        return "PAT inválido ou expirado."
    if isinstance(exc, AzureDevOpsConnectionError):
        message = str(exc)
        if "Projeto" in message or "não encontrado" in message:
            return "Projeto não encontrado."
        if "indisponível" in message:
            return "Azure DevOps indisponível."
        return "Acesso não autorizado ou URL incorreta."
    return GENERIC_CONNECTION_MESSAGE


@router.get("/azure-devops", response_model=AzureDevOpsSettingsOut)
def get_azure_devops_settings(db: Session = Depends(get_db)) -> AzureDevOpsSettingsOut:
    view = get_config_view(db)
    return AzureDevOpsSettingsOut(
        configured=view.configured,
        base_url=view.base_url,
        organization=view.organization,
        project=view.project,
        pat_configured=view.pat_configured,
        pat_expires_at=view.pat_expires_at,
        last_test_at=view.last_test_at,
        last_test_ok=view.last_test_ok,
    )


@router.put("/azure-devops", response_model=AzureDevOpsSettingsOut)
def update_azure_devops_settings(
    payload: AzureDevOpsSettingsUpdate,
    db: Session = Depends(get_db),
) -> AzureDevOpsSettingsOut:
    try:
        view = save_settings(
            db,
            base_url=payload.base_url,
            organization=payload.organization,
            project=payload.project,
            pat=payload.pat,
            pat_expires_at=payload.pat_expires_at,
        )
    except AzureDevOpsConfigError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Não foi possível salvar a configuração.") from exc

    return AzureDevOpsSettingsOut(
        configured=view.configured,
        base_url=view.base_url,
        organization=view.organization,
        project=view.project,
        pat_configured=view.pat_configured,
        pat_expires_at=view.pat_expires_at,
        last_test_at=view.last_test_at,
        last_test_ok=view.last_test_ok,
    )


@router.post("/azure-devops/test-connection", response_model=AzureDevOpsTestOut)
def test_azure_devops_settings(db: Session = Depends(get_db)) -> AzureDevOpsTestOut:
    if not is_configured(db):
        return AzureDevOpsTestOut(ok=False, message="Integração não configurada.")
    try:
        service = build_service(db)
        service.test_connection()
        record_test_result(db, ok=True)
        return AzureDevOpsTestOut(ok=True, message="Conexão realizada com sucesso")
    except AzureDevOpsError as exc:
        record_test_result(db, ok=False)
        return AzureDevOpsTestOut(ok=False, message=_friendly_error(exc))
    except Exception:
        record_test_result(db, ok=False)
        return AzureDevOpsTestOut(ok=False, message=GENERIC_CONNECTION_MESSAGE)
