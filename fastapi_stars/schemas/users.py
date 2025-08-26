from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # Pydantic v2: ORM mode
    id: int
    wallet_address: str
