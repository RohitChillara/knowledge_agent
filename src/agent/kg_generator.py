from __future__ import annotations
from typing import Optional
from agent import llm
from agent import schema
from agent import instructions
from agent import chunk

class KG_Generator:
    def __init__(self,document : str):
        self.document = document

    def create_graph(entities : Optional[list], relations : Optional[list]):
        pieces = KG_Generator.chunks()
        


    def chunks(self) -> list[str]:
        chunks = chunk.chunking(self.document)
        return chunks