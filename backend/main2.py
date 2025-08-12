from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from backend.core.settings import settings
from backend.core.logging import setup_logging
from backend.db_settings import init_db
from backend.routers import cameras, streams, frames, stats, admin

app = FastAPI()
setup_logging()

Instrumentator().instrument(app).expose(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cameras.router, prefix="/api", tags=["cameras"])
app.include_router(streams.router, tags=["streams"])
app.include_router(frames.router, tags=["frames"])
app.include_router(stats.router, prefix="/api/detection-stats", tags=["stats"])
app.include_router(admin.router, prefix="/api", tags=["admin"])

@app.on_event("startup")
async def startup():
    init_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.APP_HOST, port=settings.APP_PORT)
