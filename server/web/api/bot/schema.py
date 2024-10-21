from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from bson import ObjectId
from pydantic import BaseModel, Field
from pydantic.functional_validators import BeforeValidator
from typing_extensions import Annotated

from server.web.api.user.schema import UserResponse

PyObjectId = Annotated[str, BeforeValidator(str)]


class PermissionEnum(str, Enum):
    read_file = "READ_FILE"
    write_file = "WRITE_FILE"
    read_user = "READ_USER"
    write_user = "WRITE_USER"


class UserPermission(BaseModel):
    user_id: str
    permissions: List[PermissionEnum] = []
    confirm: Optional[bool] = False


class UserPermissionResponse(BaseModel):
    user: UserResponse
    permissions: List[PermissionEnum] = []
    confirm: Optional[bool] = False


class Bot(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    name: str
    description: Optional[str] = None
    owner: str
    list_user_permission: Optional[List[UserPermission]] = []
    list_files: Optional[List[str]] = []
    favorited_users: Optional[List[str]] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    avatar_source: Optional[str] = None
    response_model: str

    class Config:
        json_encoders = {ObjectId: str}


class BotCreate(BaseModel):
    name: str
    description: Optional[str] = None
    list_user_permission: Optional[List[UserPermission]] = []
    list_files: List[str] = []
    response_model: str


class BotUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    list_user_permission: Optional[List[UserPermission]] = None
    list_files: Optional[List[str]] = None
    response_model: str


class BotResponse(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    name: str
    owner: str
    description: Optional[str] = None
    list_user_permission: List[UserPermission] = []
    favorited_users: List[str]
    list_files: List[str] = []
    created_at: datetime
    avatar_source: Optional[str] = None
    response_model: str

    class Config:
        json_encoders = {ObjectId: str}
