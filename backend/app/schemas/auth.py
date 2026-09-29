import uuid

from pydantic import BaseModel, ConfigDict


class ExchangeRequest(BaseModel):
    token: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str | None
    first_name: str | None
