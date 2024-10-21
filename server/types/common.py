from typing import Generic, List, Literal, Optional, TypeVar

from bson import ObjectId
from pydantic import BaseModel, EmailStr, Field
from pydantic.functional_validators import BeforeValidator
from typing_extensions import Annotated
from datetime import datetime


PyObjectId = Annotated[str, BeforeValidator(str)]

T = TypeVar("T")


class ListDataResponse(BaseModel, Generic[T]):
    total: int
    data: List[T]
    capacity: Optional[int] = None


class User(BaseModel):

    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    username: str
    password: str
    role: Literal["user", "admin"]
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    disabled: bool = False
    avatar_source: Optional[str] = None

    class Config:
        json_encoders = {EmailStr: str, ObjectId: str}


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str
    role: str
