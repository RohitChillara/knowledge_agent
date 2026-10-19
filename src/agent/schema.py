from pydantic import BaseModel, ConfigDict
from typing import Literal

class Entity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity:str
    label:Literal["Person", "Organization", "Location", "Date"]

class Enitity_extraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entities: list[Entity]


class Triples(BaseModel):
    model_config=ConfigDict(extra='forbid')
    triple: str
    source_span: str