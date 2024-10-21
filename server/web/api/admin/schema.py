from typing import Optional

from pydantic import BaseModel, EmailStr, Field
from pydantic.functional_validators import BeforeValidator
from typing_extensions import Annotated
from datetime import datetime
from bson import ObjectId
from server.web.api.package.schema import Package

PyObjectId = Annotated[str, BeforeValidator(str)]


from pydantic import BaseModel
from typing import Optional


class OrderResponse(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: str
    package_id: str
    order_date: datetime
    expiration_date: datetime
    price: float
    pack: Optional[Package]

    class Config:
        json_encoders = {ObjectId: str}
