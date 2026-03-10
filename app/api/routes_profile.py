from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from app.explain.explain_item import explain_item
from app.pipeline.config import default_config
from app.storage.db import get_session
from app.storage.models import Profile

router = APIRouter()


@router.get("/profile/{user_id}")
def get_profile(user_id: str):
    config = default_config(Path.cwd())
    with get_session(config.db_url) as session:
        profile = session.get(Profile, user_id)
        if not profile:
            return {"error": "not_found"}
        return profile.profile_json


@router.get("/profile/{user_id}/explain/{item_id}")
def get_explain(user_id: str, item_id: str):
    config = default_config(Path.cwd())
    with get_session(config.db_url) as session:
        return explain_item(session, item_id)
