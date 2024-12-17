from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from bson import ObjectId
from pydantic import BaseModel, Field
from pydantic.functional_validators import BeforeValidator
from typing_extensions import Annotated

from server.web.api.user.schema import UserResponse

PyObjectId = Annotated[str, BeforeValidator(str)]


class FileStatus(str, Enum):
    loading = "LOADING"
    success = "SUCCESS"
    error = "ERROR"


class FileSchema(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    name: str
    path: Optional[str] = None
    extension: Optional[str] = None
    size: Optional[int] = None
    owner: Optional[PyObjectId] = None
    owner_info: Optional[UserResponse] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    disabled: bool = False
    status: FileStatus

    class Config:
        json_encoders = {ObjectId: str, Enum: lambda e: e.value}


class Doc(BaseModel):
    id: int = Field(alias="id", default=None)
    text: str
    page: int
    file_id: str

    class Config:
        json_encoders = {int: str}


class FileResponse(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    name: str
    path: Optional[str] = None
    extension: Optional[str] = None
    size: Optional[int] = None
    owner: Optional[str] = None
    owner_info: Optional[UserResponse] = None
    created_at: datetime
    docs: Optional[List[Doc]] = None
    disabled: bool = False

    class Config:
        json_encoders = {ObjectId: str}
