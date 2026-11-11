from __future__ import annotations
from agent.llm import llm
from agent.db import queries
from agent.llm import schema
from agent.llm import instructions
from agent.db import graph
from typing import Literal, Optional
import re

LUCENE_SPECIAL = r'([+\-!(){}\[\]^"~*?:\\/]|&&|\|\|)'
class Retrieval:
    def __init__(self, prompt:str):
        self.llm = llm.LLM()
        self.graph = graph.Graph()
        self.prompt = prompt
        self.predicate_list = self.graph.get(query=queries.ALL_PREDICATES)[0][0]["predicates"]

    def pipeline(self):
        entities = self.query2entity()
        print(entities)
        relations, missed = self.getEntity(entities)
        predicates = self.getPreds(relations)
        self.contextAware(entities=relations,predicates=predicates)

    def contextAware(self,
                    entities: list[str],
                    predicates: Optional[list[str]] = None,
                    visited: Optional[set[str]] = None,
                    facts: Optional[list[str]] = None,
                    depth: int = 0):
        system_instructions = instructions.ACTION_INSTRUCTIONS
        structure = schema.RetrievalPlan
        str_ents = "\n".join(f"- {e['name']}" for e in entities)
        predicates = "\n".join(predicates)

        user_prompt = instructions.CONTEXT_AWARE.format(
            prompt = self.prompt,
            entities = str_ents,
            neighborhood = predicates,
            facts = "\n".join(facts or []) or "None",
            visited = ", ".join(visited or []) or "None",
            available = ", ".join(sorted(self.predicate_list))
        )

        print("### USER PROMPT ####\n"+user_prompt)

        print("\n### RESULT ###\n")
        result = self.llm.send(prompt=user_prompt,system_instructions=system_instructions,
                               schema=structure)

        print(result)
        if result.action == "enough" and not result.follow:
            print(result)
        else:
            if result.action == "follow" and result.follow:
                query = queries.FOLLOW_STEPS
                steps = result["follow"]
                params = {
                    "steps" : steps,
                    "visited" : visited or {},
                    "beam" : 20
                }
                result = self.format_result(self.graph.get(query=query,params=params))
                print(result)



    def query2entity(self):
        system_instructions = instructions.RETRIEVAL_ENTITY_EXTRACTION
        structure = schema.QueryEntities
        result = self.llm.send(prompt=self.prompt,system_instructions=system_instructions,
                               schema=structure)

        return result


    def vector_seeding(self):
        embeddings = self.llm.embeddings(self.prompt)
        query = queries.VECTOR_SEARCH_CHUNKS
        params = {
            "query_vector" : embeddings,
            "k" : 3
        }
        result = self.graph.get(query,params)
        chunk_ids = []
        for row in result.records:
            chunk_ids.append(row["id"])

        mentions = queries.ENTITIES_FROM_CHUNKS
        params = {
            "chunk_ids" : chunk_ids,
            "k" : 5
        }
        vector_search = self.graph.get(mentions,params)
        result = schema.QueryEntities(entities=[
            schema.QueryEntity(text=r["name"], label=r["label"]) for r in vector_search.records
        ])
        return result

    def getPreds(self, kept: list):
        pred = queries.PREDICATE_SUMMARY
        record_ids = [record["id"] for record in kept]

        result = self.graph.get(query=pred, params={"ids": record_ids})
        return self.format_result(result)


    def format_result(self,result):
        lines = []
        for r in result[0]:
            others = ", ".join(r["examples"])
            if r["edges"] > len(r["examples"]):          # more edges than examples shown
                others += f", ... ({r['edges']} total)"

            if r["direction"] == "out":
                line = f"({r['entity']}) -[{r['predicate']}]-> ({others})"
            else:
                line = f"({others}) -[{r['predicate']}]-> ({r['entity']})"

            if line not in lines:                         # drop duplicate facts
                lines.append(line)

        return lines



    def getEntity(self, result):
        exact = queries.EXACT_MATCH
        kept = []
        missed = []
        seen = set()
        for e in result.entities:
            words = [w for w in e.text.split() if w.lower() not in {"the", "a", "an"}]
            text = " ".join(words)
            if not text:
                missed.append(e)
                continue

            response = self.graph.get(query=exact, params={"text": text})
            if response[0]:
                record = response[0][0]                 # first exact match
            else:
                candidates = self.getLucene(e)
                if not candidates:
                    missed.append(e)
                    continue
                record = candidates[0]                  # best fuzzy match

            if record["id"] not in seen:                # de-duplicate by id
                seen.add(record["id"])
                kept.append(record)

        return kept, missed

    def getLucene(self, e):
        fuzzy = queries.FUZZY_MATCH
        text = re.sub(LUCENE_SPECIAL, r"\\\1", e.text)
        words = [w for w in text.split() if w.lower() not in {"the", "a", "an"}]

        # no fuzzy for short names, and nothing to search if only articles were left
        if len(" ".join(words)) <= 4:
            return []

        # ~ only on words longer than 3 characters
        words = [w + "~" if len(w) > 3 else w for w in words]
        text = " ".join(words)

        result = self.graph.get(query=fuzzy, params={"lucene_query": text,
                                                     "min_score": 2,
                                                     "label": e.label})
        return result[0]


if __name__=="__main__":
    d = Retrieval("Why did the queen behead the cat?")
    d.pipeline()