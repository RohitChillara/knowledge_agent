from __future__ import annotations
from typing import Optional, Literal
from agent import llm
from agent import schema
from agent import instructions
from agent import chunk
from agent import graph
from agent.queries import NODE_LABELS, REL_TYPES
import hashlib

    
class KG_Generator:
    def __init__(self,document : str):
        self.document = document
        self.doc_id = self._hash_document()
        self.kg = graph.Graph()
        self.kg.execute(node_id=self.doc_id,props= {"SourceDocument":self.document},
                     type="SourceDocument")

    def create_graph(self):
        pieces = self.chunks()
        for index,piece in enumerate(pieces, start=1):
            chunk_id = f"{self.doc_id}:{index}"
            self.kg.execute(node_id=chunk_id, props={"ChunkText": piece},type="Chunk")


    # def connect(source_label: str, target_label:str, source_id:str, target_id:str,rel: str):



    def chunks(self) -> list[str]:
        chunks = chunk.chunking(self.document,"Recursive")
        self.total_chunks = len(chunks)
        return chunks

    def _hash_document(self) -> str:
        encoded = self.document.encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()