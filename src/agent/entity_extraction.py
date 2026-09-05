from groq import Groq
from dotenv import load_dotenv
import os
from pathlib import Path
from pydantic import BaseModel, ConfigDict
import spacy

spacy.prefer_gpu()
nlp=spacy.load("en_core_web_sm")

load_dotenv(dotenv_path=Path.home()/".env")

client=Groq(
    api_key=os.environ.get("OPENAI_API_KEY")
)

class EntityExtraction(BaseModel):
    model_config=ConfigDict(extra="forbid")
    entity_type : str
    predicate : str


text="Rohit loves Manushri"

doc=nlp(text)

print([(w.text, w.pos_) for w in doc])