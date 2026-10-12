from fastapi import APIRouter


router = APIRouter(tags=["System"])


@router.get("/health")
def health() -> dict[str, str]:
    """Application liveness only, not a database readiness check."""
    return {"status": "ok"}
