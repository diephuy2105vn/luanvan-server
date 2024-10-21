from datetime import datetime
from typing import Optional

from bson import ObjectId
from pydantic import BaseModel, Field
from pydantic.functional_validators import BeforeValidator
from typing_extensions import Annotated

from server.web.api.package.schema import Package

PyObjectId = Annotated[str, BeforeValidator(str)]


from typing import Optional

from pydantic import BaseModel


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
