from pydantic import BaseModel


class BillSchema(BaseModel):
    status: bool = True
    id: str = ""
    url: str = ""


class RuKassaSchema(BillSchema):
    frozen: bool = False
