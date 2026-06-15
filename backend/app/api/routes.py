from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.schemas.design import DesignContract, PromptRequest
from app.workflow import build_graph

router = APIRouter(prefix="/api")
graph = build_graph()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/design", response_model=DesignContract)
def create_design(request: PromptRequest) -> DesignContract:
    state = _run_pipeline(request)
    result = state.get("result")
    if not isinstance(result, DesignContract):
        raise HTTPException(status_code=500, detail="Design pipeline did not return a valid result")
    return result


@router.post("/design/debug")
def create_design_debug(request: PromptRequest) -> dict[str, Any]:
    state = _run_pipeline(request)
    result = state.get("result")
    return {
        "result": result.model_dump() if isinstance(result, DesignContract) else result,
        "state": {
            key: value.model_dump() if hasattr(value, "model_dump") else value
            for key, value in state.items()
            if key != "result"
        },
    }


def _run_pipeline(request: PromptRequest) -> dict[str, Any]:
    try:
        return graph.invoke(
            {
                "prompt": request.prompt,
                "email": request.email,
                "design_hint": request.design_hint,
                "technology_node": request.technology_node,
                "modeling_style": request.modeling_style,
                "validate_vivado": request.validate_vivado,
            }
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Design pipeline failed: {exc}") from exc
