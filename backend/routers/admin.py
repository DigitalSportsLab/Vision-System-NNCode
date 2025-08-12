from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import JSONResponse

# /init-db absichern:
# Entweder über Settings-Flag oder entfernst du den Endpoint komplett.
import os
ALLOW_INIT_DB = os.getenv("ALLOW_INIT_DB", "false").lower() in {"1","true","yes","y"}

# Falls du Base/engine bereitstellst, importiere sie hier – ansonsten entferne /init-db.
try:
    from backend.db_settings import Base, engine
    HAS_DDL = True
except Exception:
    HAS_DDL = False

router = APIRouter()

@router.get("/camera-threads")
async def get_camera_threads(request: Request):
    """Get information about currently running camera threads"""
    info = getattr(request.app, 'camera_threads_info', {})
    return JSONResponse(content={"camera_threads": list(info.values())})


@router.post("/init-db")
async def initialize_database():
    """
    ⚠️ Geschützt. Nur wenn ALLOW_INIT_DB=true und DDL verfügbar.
    In Prod besser komplett entfernen.
    """
    if not ALLOW_INIT_DB:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="init-db is disabled")

    if not HAS_DDL:
        raise HTTPException(status_code=500, detail="DDL objects (Base, engine) not available")

    try:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        return {"message": "Database initialized successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error initializing database: {e}")


# Optional: ganz entfernen, wenn du kein Risiko willst:
#  -> lösche die gesamte /init-db-Funktion und ihren Import.
