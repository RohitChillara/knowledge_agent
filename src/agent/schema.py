from pydantic import BaseModel, ConfigDict
from typing import Literal

class Entity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name:str
    label: Literal["PERSON", "ORGANIZATION", "LOCATION", "EVENT",
                   "PRODUCT", "WORK", "CONCEPT", "OTHER"]
    mentions: list[str]

class Enitity_extraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entities: list[Entity]


class Triples(BaseModel):
    model_config=ConfigDict(extra='forbid')
    triple: str
    source_span: str

class Triple_Extraction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    triples: list[Triples]