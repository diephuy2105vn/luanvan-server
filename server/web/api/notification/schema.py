from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from bson import ObjectId
from pydantic import BaseModel, Field
from pydantic.functional_validators import BeforeValidator
from typing_extensions import Annotated

PyObjectId = Annotated[str, BeforeValidator(str)]


class NotificationType(str, Enum):
    bot_invite = "BOT_INVITE"
    file_error = "FILE_ERROR"
    file_success = "FILE_SUCCESS"
    message = "MESSAGE"


class Notification(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    sender: Optional[str] = None
    receiver: str
    type: NotificationType
    content: str
    metadata: dict
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    read: Optional[bool] = False

    class Config:
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat(),
        }
