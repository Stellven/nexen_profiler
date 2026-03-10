from __future__ import annotations

from fastapi import FastAPI

from app.api.routes_profile import router as profile_router

app = FastAPI(title="User Profiler")
app.include_router(profile_router)
