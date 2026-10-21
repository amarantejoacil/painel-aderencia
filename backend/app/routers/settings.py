from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    AiModelsOut,
    AiModelOut,
    AiSettingsOut,
    AiSettingsUpdate,
    AiTestOut,
    AzureDevOpsSettingsOut,
    AzureDevOpsSettingsUpdate,
    AzureDevOpsTestOut,
    InconsistenciesReportSettingsOut,
    InconsistenciesReportSettingsUpdate,
    ProjectTrackingIgnoredScopesUpdate,
    ProjectTrackingScopeOptionOut,
    ProjectTrackingScopeSettingsOut,
)
from app.services.inconsistencies_report_settings import (
    get_settings_view as get_inconsistencies_report_settings_view,
    save_settings as save_inconsistencies_report_settings,
)
from app.services.ai.errors import (
    AiAuthError,
    AiConfigError,
    AiConnectionError,
    AiError,
    AiModelUnavailableError,
    AiRateLimitError,
)
from app.services.ai.gemini_client import GeminiClient
from app.services.gemini_config import (
    clear_api_key,
    get_config_view as get_ai_config_view,
    is_configured as is_ai_configured,
    record_test_result as record_ai_test_result,
    require_api_key,
    require_model,
    save_settings as save_ai_settings,
)
from app.services.azure_devops_config import (
    build_service,
    get_config_view,
    get_ignored_project_scope_keys,
    is_configured,
    record_test_result,
    save_ignored_project_scope_keys,
    save_settings,
)
from app.services.project_tracking.facade import load_scopes
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
        projects=view.projects,
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
            projects=payload.projects,
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
        projects=view.projects,
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


@router.get("/project-tracking/scopes", response_model=ProjectTrackingScopeSettingsOut)
def get_project_tracking_scope_settings(db: Session = Depends(get_db)) -> ProjectTrackingScopeSettingsOut:
    if not is_configured(db):
        raise HTTPException(status_code=503, detail="Integração Azure DevOps não configurada.")
    try:
        service = build_service(db)
        scopes = load_scopes(db, service, apply_ignore_filter=False)
        area_scopes = [item for item in scopes if item.area_path]
        area_scopes.sort(key=lambda item: (item.team_project.casefold(), item.label.casefold()))
        allowed = {item.key for item in area_scopes}
        ignored = [key for key in get_ignored_project_scope_keys(db) if key in allowed]
        return ProjectTrackingScopeSettingsOut(
            scopes=[
                ProjectTrackingScopeOptionOut(
                    key=item.key,
                    label=item.label,
                    team_project=item.team_project,
                    area_path=item.area_path or "",
                )
                for item in area_scopes
            ],
            ignored_scope_keys=ignored,
        )
    except AzureDevOpsError as exc:
        raise HTTPException(status_code=502, detail=_friendly_error(exc)) from exc


@router.put("/project-tracking/ignored-scopes", response_model=ProjectTrackingScopeSettingsOut)
def update_project_tracking_ignored_scopes(
    payload: ProjectTrackingIgnoredScopesUpdate,
    db: Session = Depends(get_db),
) -> ProjectTrackingScopeSettingsOut:
    if not is_configured(db):
        raise HTTPException(status_code=503, detail="Integração Azure DevOps não configurada.")
    try:
        service = build_service(db)
        scopes = load_scopes(db, service, apply_ignore_filter=False)
        allowed = {item.key for item in scopes if item.area_path}
        cleaned = [key for key in payload.ignored_scope_keys if key in allowed]
        save_ignored_project_scope_keys(db, cleaned)
        return get_project_tracking_scope_settings(db)
    except AzureDevOpsError as exc:
        raise HTTPException(status_code=502, detail=_friendly_error(exc)) from exc


def _ai_settings_out(db: Session) -> AiSettingsOut:
    view = get_ai_config_view(db)
    return AiSettingsOut(
        provider=view.provider,
        provider_label=view.provider_label,
        status=view.status,
        api_key_configured=view.api_key_configured,
        model_id=view.model_id,
        enabled=view.enabled,
        last_test_at=view.last_test_at,
        last_test_ok=view.last_test_ok,
        last_test_message=view.last_test_message,
    )


def _friendly_ai_error(exc: AiError) -> str:
    if isinstance(exc, AiAuthError):
        return "Chave inválida."
    if isinstance(exc, AiModelUnavailableError):
        return "Modelo indisponível."
    if isinstance(exc, AiRateLimitError):
        return "Limite de utilização atingido."
    if isinstance(exc, AiConnectionError):
        return "Falha de comunicação."
    if isinstance(exc, AiConfigError):
        return str(exc)
    return "Falha de comunicação."


@router.get("/inconsistencies-report", response_model=InconsistenciesReportSettingsOut)
def get_inconsistencies_report_settings(db: Session = Depends(get_db)) -> InconsistenciesReportSettingsOut:
    view = get_inconsistencies_report_settings_view(db)
    return InconsistenciesReportSettingsOut(
        copy_intro_requires_review=view.copy_intro_requires_review,
        copy_intro_ok=view.copy_intro_ok,
        updated_at=view.updated_at,
    )


@router.put("/inconsistencies-report", response_model=InconsistenciesReportSettingsOut)
def update_inconsistencies_report_settings(
    payload: InconsistenciesReportSettingsUpdate,
    db: Session = Depends(get_db),
) -> InconsistenciesReportSettingsOut:
    try:
        view = save_inconsistencies_report_settings(
            db,
            copy_intro_requires_review=payload.copy_intro_requires_review,
            copy_intro_ok=payload.copy_intro_ok,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Não foi possível salvar a configuração.") from exc
    return InconsistenciesReportSettingsOut(
        copy_intro_requires_review=view.copy_intro_requires_review,
        copy_intro_ok=view.copy_intro_ok,
        updated_at=view.updated_at,
    )


@router.get("/gemini", response_model=AiSettingsOut)
def get_gemini_settings(db: Session = Depends(get_db)) -> AiSettingsOut:
    return _ai_settings_out(db)


@router.put("/gemini", response_model=AiSettingsOut)
def update_gemini_settings(payload: AiSettingsUpdate, db: Session = Depends(get_db)) -> AiSettingsOut:
    try:
        save_ai_settings(
            db,
            api_key=payload.api_key,
            clear_api_key=payload.clear_api_key,
            model_id=payload.model_id,
            enabled=payload.enabled,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Não foi possível salvar a configuração.") from exc
    return _ai_settings_out(db)


@router.delete("/gemini/api-key", response_model=AiSettingsOut)
def delete_gemini_api_key(db: Session = Depends(get_db)) -> AiSettingsOut:
    clear_api_key(db)
    return _ai_settings_out(db)


@router.get("/gemini/models", response_model=AiModelsOut)
def list_gemini_models(db: Session = Depends(get_db)) -> AiModelsOut:
    try:
        row, api_key = require_api_key(db)
        _ = row
        client = GeminiClient(api_key)
        models = client.list_generation_models()
        return AiModelsOut(models=[AiModelOut(id=item.id, display_name=item.display_name) for item in models])
    except AiConfigError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AiError as exc:
        raise HTTPException(status_code=502, detail=_friendly_ai_error(exc)) from exc


@router.post("/gemini/test-connection", response_model=AiTestOut)
def test_gemini_settings(db: Session = Depends(get_db)) -> AiTestOut:
    if not is_ai_configured(db):
        return AiTestOut(ok=False, message="Integração não configurada.")
    try:
        row, api_key = require_api_key(db)
        model_id = require_model(row)
        client = GeminiClient(api_key)
        client.test_connection(model_id)
        record_ai_test_result(db, ok=True, message="Conexão estabelecida com sucesso.")
        return AiTestOut(ok=True, message="Conexão estabelecida com sucesso.")
    except AiError as exc:
        message = _friendly_ai_error(exc)
        record_ai_test_result(db, ok=False, message=message)
        return AiTestOut(ok=False, message=message)
    except Exception:
        message = "Falha de comunicação."
        record_ai_test_result(db, ok=False, message=message)
        return AiTestOut(ok=False, message=message)
