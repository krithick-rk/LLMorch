"""
LLMorch API — Models router (Phase 9.1).
GET /api/models            — list all configured models
GET /api/models/{model_id} — get detailed model info
"""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from api.models import ModelSummary, ModelDetail, PaginatedResponse
from api.session import require_session, SessionInfo
from registry.model_registry import ModelRegistry

router = APIRouter(prefix="/api/models", tags=["models"])

# Singleton model registry for API layer
_model_registry = ModelRegistry()


def get_model_registry() -> ModelRegistry:
    return _model_registry


@router.get("", response_model=PaginatedResponse)
def list_models(
    provider: Optional[str] = Query(None, description="Filter by provider"),
    capability: Optional[str] = Query(None, description="Filter by capability"),
    enabled_only: bool = Query(True, description="Only enabled models"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: SessionInfo = Depends(require_session),
):
    reg = get_model_registry()
    models = reg.list_models(provider=provider, capability=capability, enabled_only=enabled_only)
    total = len(models)
    paged = models[offset : offset + limit]

    items = [
        ModelSummary(
            model_id=m.model_id,
            provider=m.provider,
            display_name=m.display_name,
            context_window=m.context_window,
            max_output_tokens=m.max_output_tokens,
            input_token_tracking_supported=m.input_token_tracking_supported,
            output_token_tracking_supported=m.output_token_tracking_supported,
            token_estimation_method=m.token_estimation_method.value,
            capabilities=m.capabilities,
            enabled=m.enabled,
            cost_per_million_input=m.cost_per_million_input,
            cost_per_million_output=m.cost_per_million_output,
        ).model_dump()
        for m in paged
    ]

    return PaginatedResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/{model_id}", response_model=ModelDetail)
def get_model(
    model_id: str,
    session: SessionInfo = Depends(require_session),
):
    reg = get_model_registry()
    m = reg.get_model(model_id)
    if not m:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")

    return ModelDetail(
        model_id=m.model_id,
        provider=m.provider,
        display_name=m.display_name,
        context_window=m.context_window,
        max_output_tokens=m.max_output_tokens,
        input_token_tracking_supported=m.input_token_tracking_supported,
        output_token_tracking_supported=m.output_token_tracking_supported,
        token_estimation_method=m.token_estimation_method.value,
        capabilities=m.capabilities,
        enabled=m.enabled,
        cost_per_million_input=m.cost_per_million_input,
        cost_per_million_output=m.cost_per_million_output,
        metadata=m.metadata,
        created_at=m.created_at,
    )
