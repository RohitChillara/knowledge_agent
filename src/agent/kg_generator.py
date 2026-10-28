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
import re


ARTICLE = re.compile(r"^(the|a|an)\s+", re.IGNORECASE)

class KG_Generator:
    def __init__(self,document : str):
        self.document = document
        self.doc_id = self._hash_document()
        self.kg = graph.Graph()
        self.kg.execute(node_id=self.doc_id,props= {"SourceDocument":self.document},
                     type="SourceDocument")
        self.llm = llm.LLM()
        self.en_ext = schema.Enitity_extraction
        self.retry = 0
        

    def create_graph(self):
        pieces = self.chunks()
        chunks_id = list()
        # for index,piece in enumerate(pieces, start=1):
        #     #entities = self.entity_extraction(piece)
        #     chunk_id = f"{self.doc_id}:{index}"
        #     chunks_id.append(chunk_id)
        #     self.kg.execute(node_id=chunk_id, props={"ChunkText": piece},type="Chunk")
        #     self.connect(source_label="Chunk",target_label="SourceDocument",source_id=chunk_id,
        #                  target_id=self.doc_id,rel="PART_OF")
        #     if(index>1):
        #         self.connect(source_label="Chunk",target_label="Chunk",source_id=chunks_id[index-2],
        #                                  target_id=chunk_id,rel="NEXT_CHUNK")
    
        with open("review.txt","w",encoding="utf-8") as f:
            for i in range(5):
                entities = self.entity_extraction(pieces[i])
                f.write(f"=== chunk {i} ===\n{pieces[i]}\n\n{entities}\n\n")
                time.sleep(5)


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
        
        if result is None:
            raise RuntimeError(f"LLM returned None for chunk: {chunk[:60]!r}")
        output = self.clean(result=result, chunk_text=chunk)

        return output.model_dump_json(indent=2)

    def chunks(self) -> list[str]:
        chunks = chunk.chunking(self.document,"Recursive")
        self.total_chunks = len(chunks)
        return chunks

    def _hash_document(self) -> str:
        encoded = self.document.encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()


    def clean(self,result, chunk_text):
        kept = []
        for e in result.entities:
            # strip leading article from name and mentions
            e.name = ARTICLE.sub("", e.name)
            mentions = [ARTICLE.sub("", m) for m in e.mentions]

            # keep only mentions that are exact substrings of the chunk
            mentions = [m for m in mentions if m in chunk_text]

            # de-duplicate, keep order
            mentions = list(dict.fromkeys(mentions))

            if not mentions:          # drop entities with no valid mention
                continue
            e.mentions = mentions
            kept.append(e)
        result.entities = kept
        return result