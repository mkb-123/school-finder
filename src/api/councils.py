from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from src.db.base import SchoolRepository
from src.db.factory import get_school_repository

router = APIRouter(tags=["councils"])


@router.get("/api/councils", response_model=list[str])
async def list_councils(
    repo: Annotated[SchoolRepository, Depends(get_school_repository)],
) -> list[str]:
    """List all available council names."""
    councils = await repo.list_councils()
    return councils
