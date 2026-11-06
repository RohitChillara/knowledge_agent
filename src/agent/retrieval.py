from __future__ import annotations
from agent import llm
from agent import queries
from agent import schema
from agent import instructions
from agent import graph
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
        relations, missed = self.getEntity(entities)
        predicates = self.getPreds(relations)
        self.contextAware(entities=relations,predicates=predicates)

    def contextAware(self,
                    entities: list[str],
                    predicates: list[str],
                    visited: Optional[set[str]] = None,
                    facts: Optional[list[str]] = None,
                    depth: int = 0):
        system_instructions = instructions.ACTION_INSTRUCTIONS
        structure = schema.RetrievalPlan
        str_ents = ''
        str_preds = ''
        for e in entities:
            str_ents = ", ".join(e["name"])
        for p in predicates:
            str_preds = "\n".join(p)

        user_prompt = instructions.CONTEXT_AWARE.format(
            prompt = self.prompt,
            entities = str_ents,
            neighborhood = str_preds,
            facts = facts or "None",
            visited = visited or "None"
        )

        result = self.llm.send(prompt=self.prompt,system_instructions=system_instructions,
                               schema=structure)

        print(result)

    def query2entity(self):
        system_instructions = instructions.RETRIEVAL_ENTITY_EXTRACTION
        structure = schema.QueryEntities
        result = self.llm.send(prompt=self.prompt,system_instructions=system_instructions,
                               schema=structure)

        return result


    def getPreds(self, kept: list):
        print("\n###Predicates###\n")
        pred = queries.PREDICATE_SUMMARY
        record_ids = [record["id"] for record in kept]

        result = self.graph.get(query=pred, params={"ids": record_ids})

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

        for line in lines:
            print(line)
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
    d = Retrieval("What do the mad hatter, the queen of hearts, the chesire cat and two have in common with the queen?")
    d.pipeline()