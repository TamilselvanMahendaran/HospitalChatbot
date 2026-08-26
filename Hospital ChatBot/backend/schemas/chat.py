from typing import Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):

    message: str

    history: list[dict] = []


class ChatResponse(BaseModel):

    answer: str

    appointment_id: Optional[int] = None
