from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from pydantic import BaseModel, Field
from pydantic.functional_validators import BeforeValidator
from typing_extensions import Annotated

PyObjectId = Annotated[str, BeforeValidator(str)]


class Package(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    type: str
    name: str
    price: int
    numBot: int
    capacity_file: int
    capacity_bot: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat(),
        }


class PackageUpdate(BaseModel):
    type: Optional[str] = None
    name: Optional[str] = None
    price: Optional[int] = None
    numBot: Optional[int] = None
    capacity_file: Optional[int] = None
    capacity_bot: Optional[int] = None


class PackageCreate(BaseModel):
    type: str
    name: str
    price: int
    numBot: int
    capacity_file: int
    capacity_bot: int
