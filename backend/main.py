from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.lunch import router as lunch_router

app = FastAPI(title="ku-helper backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(lunch_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
