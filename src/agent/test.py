from langchain_groq import ChatGroq
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_core.documents import Document
from pydantic import BaseModel, ConfigDict
from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv(dotenv_path=Path.home()/".env")


class ResponseFormat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str
    predicate : str
    object : str


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    triples: list[ResponseFormat]

model=ChatGroq(
    api_key=os.environ.get("OPENAI_API_KEY"),
    model="qwen/qwen3.8-27b",
    temperature=0,
    max_retries=2
)

llm_transformer = LLMGraphTransformer(
    llm=model,
    allowed_nodes=["Person", "Institution", "Degree", "Country"],
    allowed_relationships=[
        ("Person", "studiesAt", "Institution"),
        ("Person", "previouslyStudiedAt", "Institution"),
        ("Person", "pursuedDegree", "Degree"),
        ("Degree", "degreeInstitution", "Institution"),
        ("Institution", "locatedIn", "Country"),
    ],
    strict_mode=True,
)
prompt="""
    Elena Petrova is currently studying at the Technical University of Munich,
    where she is pursuing a Master's degree. Before that, she completed her
    Bachelor's degree at the University of Belgrade. The University of Belgrade
    is located in Serbia. The Technical University of Munich is located in
    Germany. In her free time, Elena enjoys hiking in the Alps.
    """
doc = Document(page_content=prompt)
graph_documents = llm_transformer.convert_to_graph_documents([doc])

for graph_doc in graph_documents:
    print("Nodes:")
    for node in graph_doc.nodes:
        print(f"  {node.id} ({node.type}) {node.properties}")
    print("Relationships:")
    for rel in graph_doc.relationships:
        print(f"  {rel.source.id} -[{rel.type}]-> {rel.target.id} {rel.properties}")

# messages = [
#     ("system", "You are an agent programmed to decipher the text into a knowledge graph return the output in JSON. You can provide multiple triples"),
#     ("human", "Rohit studies at University of Stuttgart in Germany and he is currently pursuing his masters."),
# ]
# structured_model=model.with_structured_output(ExtractionResult,method="json_schema")
# response=structured_model.invoke(messages)
# print(response)