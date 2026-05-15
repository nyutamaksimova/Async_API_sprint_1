from pydantic import BaseModel, ConfigDict


class Person(BaseModel):
    uuid: str
    full_name: str

    model_config = ConfigDict(from_attributes=True)
