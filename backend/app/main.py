from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.auth.router import router as auth_router
from app.drugs.router import router as drugs_router
from app.drugs.ndc_router import router as ndc_router
from app.chat.router import router as chat_router
from app.interactions.router import router as interactions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="HeyMed API",
    description="Pharmacy AI System powered by RxNorm",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(drugs_router, prefix="/api/v1/drugs", tags=["drugs"])
app.include_router(ndc_router, prefix="/api/v1/ndc", tags=["ndc"])
app.include_router(interactions_router, prefix="/api/v1/interactions", tags=["interactions"])
app.include_router(chat_router, prefix="/api/v1/chat", tags=["chat"])


STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}
