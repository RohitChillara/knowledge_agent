from __future__ import annotations
from typing import Literal
from agent.llm import llm
from agent.llm.embed import embed
from agent.llm import schema
from agent.llm import instructions
from agent.ingest import chunk
from agent.db import graph
import hashlib
import asyncio
import re


ARTICLE = re.compile(r"^(the|a|an)\s+", re.IGNORECASE)

TITLE = re.compile(r"^((dr|prof|mr|mrs|ms|sir|dame)\.?\s+)+", re.IGNORECASE)

BRACKET_ABBR = re.compile(r"\s*\(([A-Z][A-Za-z0-9&.\-]{1,12})\)\s*$")

POSSESSIVE = re.compile(r"[’']s\s")

class KG_Generator:

    def __init__(self, document: str, title: str = ""):
        self.document = document
        self.title = title
        self.doc_id = self._hash_document()
        self.kg = None
        self.llm = llm.LLM()
        self.en_ext = schema.Enitity_extraction

    @classmethod
    async def create(cls, document: str, title: str = ""):
        self = cls(document, title)
        self.kg = await graph.Graph.create()
        await self.kg.execute(node_id=self.doc_id,
                              props={"text": self.document, "title": self.title},
                              type="SourceDocument")
        return self

    async def close(self):
        if self.kg is not None:
            await self.kg.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()
        return False

    async def pipeline(self, max_parallel: int = 3):
        pieces = await self.chunks()
        sem = asyncio.Semaphore(max_parallel)
        async def extract(piece):
            async with sem:                      # at most max_parallel LLM calls at once
                return await self.entity_extraction(piece)

        # entities for all chunks concurrently, and embeddings for all chunks in one batch call
        Failed = [4]

        retry = [(index, p) for index, p in enumerate(pieces, start=1) if index in Failed]

        results = await asyncio.gather(*(extract(p) for _, p in retry), return_exceptions=True)
        # all_entities, all_vectors = await asyncio.gather(
        #     asyncio.gather(*(extract(p) for index,p in enumerate(pieces,start=1)), return_exceptions=True),
        #     embed(pieces),
        # )
        for (index, piece), entities in zip(retry, results):
            chunk_id = f"{self.doc_id}:{index}"
            if isinstance(entities, Exception):
                print(f"Chunk {index} failed again: {entities}")
                continue
            await self.add_entity(entities, chunk_id)
        chunks_id = []
        failed = []
        # for index, (piece, entities, vector) in enumerate(zip(pieces, all_entities, all_vectors), start=1):
        #     chunk_id = f"{self.doc_id}:{index}"
        #     chunks_id.append(chunk_id)

        #     # the chunk is always written, so the NEXT_CHUNK chain stays intact
        #     await self.kg.execute(node_id=chunk_id,
        #                           props={"text": piece, "index": index, "embedding": vector},
        #                           type="Chunk")
        #     await self.connect(source_label="Chunk", target_label="SourceDocument",
        #                        source_id=chunk_id, target_id=self.doc_id, rel="PART_OF")
        #     if index > 1:
        #         await self.connect(source_label="Chunk", target_label="Chunk",
        #                            source_id=chunks_id[index - 2], target_id=chunk_id, rel="NEXT_CHUNK")

        #     if isinstance(entities, Exception):
        #         failed.append(index)
        #         print(f"Chunk {index} failed: {entities}")
        #         continue                          # chunk exists, just without entities
        #     await self.add_entity(entities, chunk_id)

        # if failed:
        #     print(f"Failed chunks: {failed}")



    async def add_entity(self,result,chunk_id):
        for e in result.entities:
            eid = self.entity_id(e.label, e.name)
            await self.kg.execute(type="Entity",node_id=eid,props={"name": e.name, "label": e.label})
            await self.kg.execute(type="Connect",
                   source_label="Chunk", rel="MENTIONS", target_label="Entity",
                   source_id=chunk_id, target_id=eid,
                   props={"mentions": e.mentions})
            

    async def connect(self,source_label: Literal["SourceDocument", "Chunk", "Entity"]
                , target_label:Literal["SourceDocument", "Chunk", "Entity"]
                , source_id:str, target_id:str,rel: Literal["PART_OF", "NEXT_CHUNK", "MENTIONS", "RELATED"]):
        if source_label is None or target_label is None:
            raise ValueError("Missing source or target label")
        if source_id is None or target_id is None:
            raise ValueError("Missing source or target id")
        if rel is None:
            raise ValueError("Missing rel")

        await self.kg.execute(source_label=source_label,target_label=target_label,
                        source_id=source_id,target_id=target_id,type="Connect",rel=rel)


    async def entity_extraction(self,chunk:str):
        prompt = "<chunk>\n"+chunk+"\n</chunk>"
        result =await self.llm.send(prompt=prompt,
                    system_instructions=instructions.ENTITY_EXTRACTION,schema=self.en_ext,
                    is_valid=lambda r: len(r.entities) > 0)
        
        if result is None:
            raise RuntimeError(f"LLM returned None for chunk: {chunk[:60]!r}")
        output = self.clean(result=result, chunk_text=chunk)

        return output

    async def chunks(self) -> list[str]:
        chunks = await asyncio.to_thread(chunk.chunking, self.document, "Recursive")
        self.total_chunks = len(chunks)
        return chunks

    def _hash_document(self) -> str:
        encoded = self.document.encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()

    def entity_id(self,label: str, name: str) -> str:
        return hashlib.sha256(f"{label}:{name.casefold()}".encode("utf-8")).hexdigest()

    @staticmethod
    def _normalise(text: str) -> tuple[str, str | None]:
        """Strip article and titles; split off a trailing (ABBR). Returns (name, abbr or None)."""
        text = ARTICLE.sub("", text.strip())
        text = TITLE.sub("", text)
        abbr = None
        m = BRACKET_ABBR.search(text)
        if m:
            abbr = m.group(1)
            text = text[:m.start()]
        return text.strip(), abbr

    @staticmethod
    def _belongs(mention: str, name: str) -> bool:
        """Is this mention a form of this name? Containment, a shared word, or an abbreviation."""
        m, n = mention.lower(), name.lower()
        if m in n or n in m:
            return True
        name_words = re.findall(r"[a-z0-9]+", n)
        mention_words = re.findall(r"[a-z0-9]+", m)
        if {w for w in mention_words if len(w) > 2} & {w for w in name_words if len(w) > 2}:
            return True
        # abbreviation: its letters appear in order among the initials, so small words
        # can be skipped ("TUM" = Technical University of Munich)
        initials = iter(w[0] for w in name_words)
        letters = re.sub(r"[^a-z0-9]", "", m)
        return len(letters) >= 2 and all(ch in initials for ch in letters)


    def clean(self, result, chunk_text):
        kept = []
        # names of all entities in this chunk, after normalising
        all_names = {self._normalise(x.name)[0] for x in result.entities}
        for e in result.entities:
            name, name_abbr = self._normalise(e.name)

            mentions = []
            for m in e.mentions:
                form, abbr = self._normalise(m)
                mentions.append(form)
                if abbr:
                    mentions.append(abbr)        
            if name_abbr:
                mentions.append(name_abbr)

            # keep only mentions that are exact substrings of the chunk
            mentions = [m for m in mentions if m and m in chunk_text]

            # a mention may not be another entity's name ("TUM" listing "Hollis Foundation")
            mentions = [m for m in mentions if m == name or m not in all_names]

            # drop possessive phrases ("Queen’s hedgehog")
            mentions = [m for m in mentions if not POSSESSIVE.search(m)]

            # keep only mentions that start with a capital letter (names, not generic nouns)
            mentions = [m for m in mentions if m[:1].isupper()]

            # de-duplicate, keep order
            mentions = list(dict.fromkeys(mentions))

            # split off mentions that are not forms of this entity's name
            fits = [m for m in mentions if self._belongs(m, name)]
            strays = [m for m in mentions if m not in fits]
            for s in strays:
                if s not in all_names:
                    kept.append(schema.Entity(name=s, label=e.label, mentions=[s]))
                    all_names.add(s)
            mentions = fits

            if not mentions:          # drop entities with no valid mention
                continue

            # the name must be one of the mentions; otherwise use the longest mention
            e.name = name if name in mentions else max(mentions, key=len)
            e.mentions = mentions
            kept.append(e)
        result.entities = kept
        return result