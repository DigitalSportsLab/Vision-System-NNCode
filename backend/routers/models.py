from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from backend.services.models.registry import registry
from backend.services.models.interfaces import ModelTask

router = APIRouter(tags=["models"])

@router.get("/models")
def list_models(
    provider: Optional[str] = Query(None, description="z.B. 'yolo', 'sapiens', 'mediapipe'"),
    task: Optional[str] = Query(None, description="z.B. 'detect', 'pose', 'segment', ..."),
    q: Optional[str] = Query(None, description="Substring-Suche im Key"),
    details: bool = Query(False, description="true = Details statt nur Keys zurückgeben")
):
    """
    Liefert alle in der Registry bekannten Modelle.
    - Standard: nur Keys
    - details=true: volle Spezifikation (provider, version, task, weights)
    - Optional: Filter nach provider, task, Substring
    """
    specs = registry.all().values()

    items: List[Any] = []
    for s in specs:
        if provider and s.provider != provider:
            continue
        if task and s.task.value != task:
            continue
        if q and q.lower() not in s.key.lower():
            continue

        if details:
            items.append({
                "key": s.key,
                "provider": s.provider,
                "version": s.version,
                "task": s.task.value,
                "weights": s.weights,  # Hinweis: kann ein Pfad sein
            })
        else:
            items.append(s.key)

    return {"count": len(items), "items": items}

@router.get("/models/{key}")
def get_model(key: str):
    """Details zu einem konkreten model_key."""
    try:
        s = registry.get(key)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown model key")
    return {
        "key": s.key,
        "provider": s.provider,
        "version": s.version,
        "task": s.task.value,
        "weights": s.weights,
    }
