from __future__ import annotations
from typing import Optional, Literal
from agent import llm
from agent import schema
from agent import instructions
from agent import chunk
from agent import graph
from agent.queries import NODE_LABELS, REL_TYPES
import hashlib
import time

    
class KG_Generator:
    def __init__(self,document : str):
        self.document = document
        self.doc_id = self._hash_document()
        self.kg = graph.Graph()
        self.kg.execute(node_id=self.doc_id,props= {"SourceDocument":self.document},
                     type="SourceDocument")
        self.llm = llm.LLM()
        self.en_ext = schema.Enitity_extraction
        

    def create_graph(self):
        pieces = self.chunks()
        chunks_id = list()
        for index,piece in enumerate(pieces, start=1):
            chunk_id = f"{self.doc_id}:{index}"
            chunks_id.append(chunk_id)
            # entities = self.entity_extraction(piece)
            self.kg.execute(node_id=chunk_id, props={"ChunkText": piece},type="Chunk")
            self.connect(source_label="Chunk",target_label="SourceDocument",source_id=chunk_id,
                         target_id=self.doc_id,rel="PART_OF")
            if(index>1):
                self.connect(source_label="Chunk",target_label="Chunk",source_id=chunks_id[index-2],
                                         target_id=chunk_id,rel="NEXT_CHUNK")
        # for i in range(3):
        #     print("\nChunk "+ str(i) +"\n"+pieces[i]+"\n")
        #     assert pieces[i] in self.document, f"chunk {i} is not an exact substring"
        #     entities = self.entity_extraction(pieces[i])
        #     time.sleep(2)


    def connect(self,source_label: Literal["SourceDocument", "Chunk", "Entity"]
                , target_label:Literal["SourceDocument", "Chunk", "Entity"]
                , source_id:str, target_id:str,rel: Literal["PART_OF", "NEXT_CHUNK", "MENTIONS", "RELATED"]):
        if source_label is None or target_label is None:
            raise ValueError("Missing source or target label")
        if source_id is None or target_id is None:
            raise ValueError("Missing source or target id")
        if rel is None:
            raise ValueError("Missing rel")

        self.kg.execute(source_label=source_label,target_label=target_label,
                        source_id=source_id,target_id=target_id,type="Connect",rel=rel)


    def entity_extraction(self,chunk:str):
        prompt = "<chunk>\n"+chunk+"\n</chunk>"
        result =self.llm.send(prompt=prompt,
                      system_instructions=instructions.ENTITY_EXTRACTION,schema=self.en_ext)
        print(result.model_dump_json(indent=2))

    def chunks(self) -> list[str]:
        chunks = chunk.chunking(self.document,"Recursive")
        self.total_chunks = len(chunks)
        return chunks

    def _hash_document(self) -> str:
        encoded = self.document.encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()