from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import asam, extraction, tjc
from app.db.database import engine
from app.db.models import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="Perspectives Health Clinical Intelligence",
    description="Clinical data extraction, ASAM Level of Care estimation, and TJC CTS compliance auditing.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(extraction.router, prefix="/api/v1", tags=["extraction"])
app.include_router(asam.router, prefix="/api/v1", tags=["asam"])
app.include_router(tjc.router, prefix="/api/v1", tags=["tjc"])


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return FileResponse(Path(__file__).parent / "static" / "index.html")
