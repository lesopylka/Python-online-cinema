# app/streaming/endpoints.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/test")
async def test_endpoint():
    return {"message": "Streaming endpoint works"}