from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.api import endpoints
import uvicorn

app = FastAPI(title="Enterprise Multimodal RAG")

# Allow CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routes
app.include_router(endpoints.router, prefix="/api")
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    print("Starting Multimodal RAG Server...")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)