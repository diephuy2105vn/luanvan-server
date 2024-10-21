from datetime import datetime, timezone
from typing import List, Optional

from bson import ObjectId
from pydantic import BaseModel, Field
from pydantic.functional_validators import BeforeValidator
from typing_extensions import Annotated

PyObjectId = Annotated[str, BeforeValidator(str)]


class ChatHistory(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: str = ""
    bot_id: str
    list_messages: List[str] = []
    disabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        json_encoders = {ObjectId: str}


class ChatMessage(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    chat_history_id: str
    question: str
    answer: str
    source: Optional[dict] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        json_encoders = {ObjectId: str}
