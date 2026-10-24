from __future__ import annotations
from typing import Optional
from agent import llm
from agent import schema
from agent import instructions
from agent import chunk
from agent import graph
from agent import queries
import hashlib

    
class KG_Generator:
    def __init__(self,document : str):
        self.document = document
        self.doc_id = self._hash_document()
        self.kg = graph.Graph()
        self.kg.create(self.document,self.doc_id,{"SourceText": self.document},"SourceDocument")

    def create_graph(self):
        pieces = self.chunks()
        for index,piece in enumerate(pieces, start=1):
            chunk_id = f"{self.doc_id}:{index}"
            self.kg.create(piece,chunk_id ,"Chunk")


    def chunks(self) -> list[str]:
        chunks = chunk.chunking(self.document)
        return chunks

    def _hash_document(self) -> str:
        encoded = self.document.encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()