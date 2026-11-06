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


class QueryEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    label: Literal["PERSON", "ORGANIZATION", "LOCATION", "EVENT",
                   "PRODUCT", "WORK", "CONCEPT", "OTHER"]

class QueryEntities(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entities: list[QueryEntity]


class FollowStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity: str               # entity name from the neighbourhood
    predicates: list[str]     # predicates to follow from that entity


class RetrievalPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["enough", "follow", "cypher"]
    reason: str
    follow: list[FollowStep]  # empty unless action == "follow"
    cypher: str               # "" unless action == "cypher