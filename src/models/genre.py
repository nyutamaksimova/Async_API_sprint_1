from pydantic import BaseModel, ConfigDict


class Genre(BaseModel):
    uuid: str
    name: str

    model_config = ConfigDict(from_attributes=True)
