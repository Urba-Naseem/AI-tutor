from fastapi import FastAPI
from app.db.session import engine, Base
import app.models  # Ensures all SQLAlchemy models (User, ActivityEvent, etc.) are registered
from app.api.v1 import auth, curriculum, audit

# Automatically create missing database tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI Tutor API",
    version="0.1.0",
    description="Production-grade AI Tutor Backend with Secure Audit Logging"
)

# Root Health Check Route
@app.get("/", tags=["Health Check"])
def health_check():
    return {"status": "online", "system": "AI Tutor Backend"}

# Register Application API Routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(curriculum.router, prefix="/api/v1/curriculum", tags=["Curriculum"])
app.include_router(audit.router, prefix="/api/v1/audit", tags=["Audit"])