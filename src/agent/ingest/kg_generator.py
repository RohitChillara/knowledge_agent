from __future__ import annotations
from typing import Literal
from agent.llm import llm
from agent.llm.embed import embed
from agent.llm import schema
from agent.llm import instructions
from agent.ingest import chunk
from agent.db import graph, queries
import hashlib
import asyncio
import re
from collections import Counter


ARTICLE = re.compile(r"^(the|a|an)\s+", re.IGNORECASE)

TITLE = re.compile(r"^((dr|prof|mr|mrs|ms|sir|dame)\.?\s+)+", re.IGNORECASE)

BRACKET_ABBR = re.compile(r"\s*\(([A-Z][A-Za-z0-9&.\-]{1,12})\)\s*$")

POSSESSIVE = re.compile(r"[’']s(\s|$)")

PREDICATE_CHARS = re.compile(r"[^a-z0-9_]")

# a named unit needs at least one word before the unit word ("crystal growth group", not "group")
UNIT_WORDS = re.compile(r"\b\w+\s+(group|department|division|lab|laboratory|team|unit)$", re.IGNORECASE)

MAX_RETRY_ROUNDS = 3      # retry rounds for failed chunks
RETRY_WAIT = 120           # seconds; round n waits n * RETRY_WAIT

class KG_Generator:

    def __init__(self, document: str, title: str = ""):
        self.document = document
        self.title = title
        self.doc_id = self._hash_document()
        self.kg = None
        self.sem = None
        self.labels: dict[str, str] = {}      # casefolded name -> majority label
        self.llm = llm.LLM()

    @classmethod
    async def create(cls, document: str, title: str = "", max_parallel:int =2):
        self = cls(document, title)
        self.kg = await graph.Graph.create()
        self.sem = asyncio.Semaphore(max_parallel)
        await self.before()                      # schema first: the document node below needs its constraint
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

    async def extract(self,piece):
        async with self.sem:                      # at most max_parallel LLM calls at once
            entities = await self.entity_extraction(piece)
            try:
                triples = await self.triple_extraction(entities=entities,chunk=piece)
            except Exception as e:
                print(f"Triples failed for chunk {piece[:40]!r}: {e}")
                triples = []
            return entities, triples

    async def pipeline(self):
        pieces = await self.chunks()
        # entities for all chunks concurrently, and embeddings for all chunks in one batch call 
        results, all_vectors = await asyncio.gather(
            asyncio.gather(*(self.extract(p) for p in pieces), return_exceptions=True),
            embed(pieces))

        # one label per entity: the most frequent across all chunks (ids no longer include the label)
        self._count_labels(results)

        chunks_id = []
        failed = []
        for index, (piece, result, vector) in enumerate(zip(pieces, results, all_vectors), start=1):
            chunk_id = f"{self.doc_id}:{index}"
            chunks_id.append(chunk_id)

            # the chunk is always written, so the NEXT_CHUNK chain stays intact
            await self.kg.execute(node_id=chunk_id,
                                  props={"text": piece, "index": index, "embedding": vector},
                                  type="Chunk")
            await self.connect(source_label="Chunk", target_label="SourceDocument",
                               source_id=chunk_id, target_id=self.doc_id, rel="PART_OF")
            if index > 1:
                await self.connect(source_label="Chunk", target_label="Chunk",
                                   source_id=chunks_id[index - 2], target_id=chunk_id, rel="NEXT_CHUNK")

            if isinstance(result, Exception):
                failed.append((index,piece))
                print(f"Chunk {index} failed: {result}")
                continue                          # chunk exists, just without entities
            entities, triples = result
            await self.add_entity(entities, chunk_id)
            await self.add_triples(triples,chunk_id)

        if failed:
            print(f"Failed chunks: {[i for i, _ in failed]}")
            print("Retry initialised")
            await self.retries(failed=failed)

        # after retries, so aliases also cover entities from retried chunks
        await self.after()

    async def before(self):
        """Schema setup; idempotent (IF NOT EXISTS), safe before every ingest."""
        for statement in queries.CONSTRAINTS:
            await self.kg.get(query=statement)
        await self.kg.get(query=queries.CREATE_FULLTEXT_INDEX)
        await self.kg.get(query=queries.CREATE_VECTOR_INDEX)

    async def after(self):
        """Post-ingest step (aliases for retrieval) and a check report."""
        await self.kg.get(query=queries.SET_ALIASES)

        p = {"doc_id": self.doc_id}
        chunks = (await self.kg.get(query=queries.CHECK_CHUNKS, params=p)).records[0]
        chain = (await self.kg.get(query=queries.CHECK_CHAIN, params=p)).records[0]["reachable"]
        orphans = (await self.kg.get(query=queries.CHECK_ORPHAN_CHUNKS)).records[0]["orphans"]
        emb = (await self.kg.get(query=queries.CHECK_EMBEDDINGS)).records

        print("\n### Ingest report ###")
        print(f"chunks: {chunks['chunks']} (index {chunks['first']}..{chunks['last']}), "
              f"chain reachable: {chain} (expect {chunks['chunks'] - 1}), orphans: {orphans}")
        print("embeddings (dims, chunks):", [(r["dims"], r["chunks"]) for r in emb])

        print("entities by label:")
        for r in (await self.kg.get(query=queries.CHECK_ENTITY_LABELS)).records:
            print(f"  {r['label']:13} {r['n']}")

        print("predicates:")
        for r in (await self.kg.get(query=queries.CHECK_PREDICATES)).records:
            print(f"  {r['predicate']:28} {r['n']}")

    def _count_labels(self, results):
        """Majority label per casefolded name, from all successful chunk results."""
        votes: dict[str, Counter] = {}
        for result in results:
            if isinstance(result, Exception):
                continue
            entities, _ = result
            for e in entities.entities:
                votes.setdefault(e.name.casefold(), Counter())[e.label] += 1
        for name, counter in votes.items():
            self.labels[name] = counter.most_common(1)[0][0]

    async def retries(self, failed: list, attempts: int = 1):
        if attempts > MAX_RETRY_ROUNDS:
            print(f"Giving up on chunks {[i for i, _ in failed]}; please rerun them later")
            return

        await asyncio.sleep(attempts * RETRY_WAIT)
        results = await asyncio.gather(*(self.extract(p) for _, p in failed), return_exceptions=True)

        again = []
        for (index, piece), result in zip(failed, results):
            chunk_id = f"{self.doc_id}:{index}"
            if isinstance(result, Exception):
                print(f"Chunk {index} failed again: {result}")
                again.append((index, piece))
                continue
            entities, triples = result
            await self.add_entity(entities, chunk_id)
            await self.add_triples(triples, chunk_id)

        if again:
            print(f"Retry round {attempts + 1} for chunks {[i for i, _ in again]}")
            await self.retries(again, attempts + 1)

    async def add_entity(self,result,chunk_id):
        for e in result.entities:
            eid = self.entity_id(e.name)
            # majority label across chunks; chunks seen only in a retry fall back to their own label
            label = self.labels.get(e.name.casefold(), e.label)
            await self.kg.execute(type="Entity",node_id=eid,props={"name": e.name, "label": label})
            await self.kg.execute(type="Connect",
                   source_label="Chunk", rel="MENTIONS", target_label="Entity",
                   source_id=chunk_id, target_id=eid,
                   props={"mentions": e.mentions})

    async def add_triples(self,triples: list[dict],chunk_id):
        query = queries.CONNECT_RELATED
        rows = [{
            "source_id": self.entity_id(t["subject"]),
            "target_id": self.entity_id(t["object"]),
            "predicate": t["predicate"],
            "evidence": t["evidence"],
            "grounded": t["grounded"],
        } for t in triples]
        if not rows:
            return
        result = await self.kg.get(query=query, params={"rows": rows, "chunk_id": chunk_id})
        written = result.records[0]["n"]
        if written != len(rows):
            print(f"WARNING: chunk {chunk_id[-4:]}: wrote {written} of {len(rows)} triples "
                  f"- some subject or object ids did not match an entity node")
            

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
                    system_instructions=instructions.ENTITY_EXTRACTION,schema=schema.Enitity_extraction,
                    is_valid=lambda r: len(r.entities) > 0)
        
        if result is None:
            raise RuntimeError(f"LLM returned None for chunk: {chunk[:60]!r}")
        output = self.clean(result=result, chunk_text=chunk)

        return output


    async def triple_extraction(self,entities,chunk):
        system_instructions = instructions.RELATION_EXTRACTION
        lines = []
        for e in entities.entities:
            others = [m for m in e.mentions if m != e.name]
            line = f"- {e.name} ({e.label})"
            if others:
                line += "; also called: " + ", ".join(others)
            lines.append(line)
        str_ents = "\n".join(lines)
        user_prompt = instructions.RELATION_PROMPT.format(
            entities = str_ents,
            chunk = chunk
        )
        # print(user_prompt)
        result = await self.llm.send(prompt=user_prompt,system_instructions=system_instructions,schema=schema.TripleResult)
        cleaned = self.clean_triples(result,entities,chunk)
        return cleaned





    async def chunks(self) -> list[str]:
        chunks = await asyncio.to_thread(chunk.chunking, self.document, "Recursive")
        self.total_chunks = len(chunks)
        return chunks

    def _hash_document(self) -> str:
        encoded = self.document.encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()

    def entity_id(self, name: str) -> str:
        return hashlib.sha256(name.casefold().encode("utf-8")).hexdigest()

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

            # drop possessive phrases ("Queen’s hedgehog", "Menon's")
            mentions = [m for m in mentions if not POSSESSIVE.search(m)]

            # keep only names: capitalised, or a named unit ("crystal growth group")
            mentions = [m for m in mentions if m[:1].isupper() or UNIT_WORDS.search(m)]

            # de-duplicate, keep order
            mentions = list(dict.fromkeys(mentions))

            # split off mentions that are not forms of this entity's name;
            # each becomes its own entity
            fits = [m for m in mentions if self._belongs(m, name)]
            strays = [m for m in mentions if m not in fits]
            for s in strays:
                if s not in all_names:
                    kept.append(schema.Entity(name=s, label=e.label, mentions=[s]))
                    all_names.add(s)
            mentions = fits

            if not mentions:          # drop entities with no valid mention
                continue

            # prefer the longest mention that contains the name ("Voss" -> "Anika Voss");
            # otherwise keep the name if it is a mention, else the longest mention
            longer = [m for m in mentions if name.lower() in m.lower() and len(m) > len(name)]
            if longer:
                e.name = max(longer, key=len)
            elif name in mentions:
                e.name = name
            else:
                e.name = max(mentions, key=len)

            e.mentions = mentions
            kept.append(e)
        result.entities = kept
        return result

    def clean_triples(self, result, entities, chunk_text) -> list[dict]:
        # every form of every entity -> (main name, label); a form shared by two
        forms: dict[str, tuple[str, str]] = {}
        ambiguous: set[str] = set()
        for e in entities.entities:
            for form in [e.name, *e.mentions]:
                key = form.lower()
                if key in forms and forms[key][0] != e.name:
                    ambiguous.add(key)
                forms[key] = (e.name, e.label)
        for key in ambiguous:
            forms.pop(key, None)

        # all forms of each main name, for the grounding check
        names_to_forms: dict[str, set[str]] = {}
        for form, (name, _label) in forms.items():
            names_to_forms.setdefault(name, set()).add(form)

        kept, seen = [], set()
        for t in result.triples:
            # map subject and object to main names (the model may write "Voss" or "RTU")
            subj = forms.get(t.subject.strip().lower())
            obj = forms.get(t.object.strip().lower())
            if subj is None or obj is None:
                continue                                  # not an entity of this chunk
            (subj_name, subj_label), (obj_name, obj_label) = subj, obj

            if subj_name == obj_name:
                continue                                  # self-loop

            evidence = t.evidence.strip()
            if not evidence or evidence not in chunk_text:
                continue                                  # evidence must be quoted exactly

            predicate = t.predicate.strip().lower().replace(" ", "_").replace("-", "_")
            predicate = PREDICATE_CHARS.sub("", predicate).strip("_")
            if not predicate:
                continue

            key = (subj_name, predicate, obj_name)
            if key in seen:
                continue                                  # duplicate within the chunk
            seen.add(key)

            # grounded: both entities are named in the evidence itself
            ev = evidence.lower()
            subj_named = any(f in ev for f in names_to_forms[subj_name])
            obj_named = any(f in ev for f in names_to_forms[obj_name])
            grounding = int(subj_named) + int(obj_named)

            kept.append({
                "subject": subj_name, "subject_label": subj_label,
                "predicate": predicate,
                "object": obj_name, "object_label": obj_label,
                "evidence": evidence,
                "grounded": grounding,
            })
        return kept