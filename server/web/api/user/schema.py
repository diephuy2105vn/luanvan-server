from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field
from pydantic.functional_validators import BeforeValidator
from typing_extensions import Annotated
from datetime import datetime
from bson import ObjectId
from server.web.api.package.schema import Package

PyObjectId = Annotated[str, BeforeValidator(str)]


class UserPackageInfo(BaseModel):
    pack: Package
    registration_date: Optional[datetime]
    expiration_date: Optional[datetime]
    price: int


class UserResponse(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    username: str
    role: Literal["user", "admin"]
    email: Optional[str]
    full_name: Optional[str]
    phone_number: Optional[str]
    disabled: bool
    avatar_source: Optional[str] = None

    class Config:
        json_encoders = {EmailStr: str, ObjectId: str}


class UserRegister(BaseModel):
    username: str
    password: str
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    role: Literal["user", "admin"]


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
