from groq import Groq
from dotenv import load_dotenv
import os
from pathlib import Path
from pydantic import BaseModel, ConfigDict
import json
from typing import Literal


class Entity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity:str
    label:Literal["Person", "Organization", "Location", "Date"]

class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entities: list[Entity]



load_dotenv(dotenv_path=Path.home()/".env")

client=Groq(api_key=os.environ.get("OPENAI_API_KEY"))

test="""
    Elena Petrova is currently studying at the Technical University of Munich,
    where she is pursuing a Master's degree. Before that, she completed her
    Bachelor's degree at the University of Belgrade. The University of Belgrade
    is located in Serbia. The Technical University of Munich is located in
    Germany. In her free time, Elena enjoys hiking in the Alps.
    """

response=client.chat.completions.create(
    messages=[
        {
            "role":"system",
            "content":"You are an expert in exctracting entities and their labels from given text",
        },
        {
            "role":"user",
            "content":test,
        },
        ],
        model="qwen/qwen3.8-27b",
        temperature=0,
        response_format={
        "type": "json_schema",
        "json_schema": {
            "name":"Extraction",
            "strict": True,
            "schema":Extraction.model_json_schema()
            }
        }
)


raw_result = json.loads(response.choices[0].message.content or "{}")
result = Extraction.model_validate(raw_result)
print(result.model_dump_json(indent=2))