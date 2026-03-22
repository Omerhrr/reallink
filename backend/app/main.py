"""
RealLink Ecosystem - FastAPI Backend
Main application entry point
"""

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from app.models import init_db, get_engine, get_session_maker
from app.routes import auth, properties, agents, verification, interactions, ussd, admin, chat

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./reallink.db")
engine = get_engine(DATABASE_URL)
SessionLocal = get_session_maker(engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup"""
    init_db(engine)
    yield


app = FastAPI(
    title="RealLink Ecosystem",
    description="Fraud-resistant real estate platform for Africa",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(properties.router, prefix="/api/properties", tags=["Properties"])
app.include_router(agents.router, prefix="/api/agents", tags=["Agents"])
app.include_router(verification.router, prefix="/api/verification", tags=["Verification"])
app.include_router(interactions.router, prefix="/api/interactions", tags=["Interactions"])
app.include_router(ussd.router, prefix="/api/ussd", tags=["USSD/SMS"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat Assistant"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "RealLink Ecosystem API",
        "version": "1.0.0",
        "description": "Fraud-resistant real estate platform for Africa"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
