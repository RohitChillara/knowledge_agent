from groq import Groq
from dotenv import load_dotenv
import os
from pathlib import Path
import json
from pydantic import BaseModel, ConfigDict


TEST_PREDICATES = [
    "studiesAt",           # current institution
    "previouslyStudiedAt", # past institution
    "pursuedDegree",       # links a person to a degree type (Bachelor, Master, etc.)
    "degreeInstitution",   # links a degree type to the institution that granted it
    "locatedIn",           # links a place/institution to its country or city
]

#System Instrucrions
allowed_predicates=",".join(TEST_PREDICATES)



load_dotenv(dotenv_path=Path.home() / ".env")

client=Groq(api_key=os.environ.get("OPENAI_API_KEY"))


class Triple(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str
    predicate: str
    object: str
    source_span: str

class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    triples: list[Triple]




class Model:
    SYSTEM_INSTRUCTIONS = """You are extracting factual relationships from a document for a knowledge graph.
    Your only job is to identify what the text explicitly states — not what is
    likely true, not what you already know, not what would complete the picture.

    Each fact you extract has this shape:
    - subject
    - subject_type (from the allowed entity types below)
    - predicate (from the allowed predicates below)
    - object
    - object_type (from the allowed entity types below)
    - source_span: the exact sentence or clause that supports this fact

    Rules:

    1. GROUNDING: Every fact you extract must be directly and explicitly stated
    in the provided text. Do not use outside knowledge, do not infer unstated
    facts, and do not fill in plausible-sounding details (dates, locations,
    quantities) that the text does not contain. If a fact seems true but
    isn't stated, leave it out.

    2. EVIDENCE: For every fact, quote the exact sentence or clause from the
    source text that supports it, verbatim, in the source_span field. If you
    cannot find a literal sentence to quote, you cannot extract the fact.

    3. PREDICATE VOCABULARY: Use only predicate values from this list:
    {allowed_predicates}
    Do not invent new predicates. If a real relationship in the text doesn't
    fit any value on this list, omit it rather than force it into the wrong
    category.

    4. ENTITY TYPE VOCABULARY: Use only subject_type/object_type values from
    this list: {allowed_entity_types}
    Every entity must be assigned exactly one type from this list. Do not
    invent new types.

    5. ENTITY NAMING: Use the same, consistent name for an entity every time it
    appears, even if the text refers to it differently (e.g. "the University"
    vs. its full name) — pick one canonical form and use it throughout. This
    is critical: two facts only connect into a chain if they use the exact
    same name for the shared entity.

    6. CHAIN, DON'T QUALIFY: There are no qualifiers or extra properties in this
    schema. If a fact has additional context (which institution, which
    location, what role), express that context as a SEPARATE fact whose
    subject is the object of the first fact. Example: instead of attaching
    "institution: X" to a degree fact, extract a second fact stating that the
    degree's object connects to X directly, using the degree as the new
    subject. Every piece of stated context must become its own linked fact,
    not be dropped and not be bundled onto another fact.

    7. OMISSION OVER INVENTION: When in doubt about whether something is stated
    clearly enough to extract, do not extract it. An incomplete but accurate
    graph is far more useful than a complete but partially fabricated one."""


    VERIFICATION_INSTRUCTIONS = """You are reviewing and correcting a first-pass extraction of facts from a
    document for a knowledge graph. You are given the original source text and
    the facts already extracted from it. Your job is not to extract from
    scratch — it is to find and fix problems in what's already there.

    Each fact has this shape:
    - subject / subject_type
    - predicate
    - object / object_type
    - source_span

    Rules:

    1. FIND BROKEN CHAINS: This schema has no qualifiers — context is expressed
    by chaining facts through a shared entity (the object of one fact becomes
    the subject of the next). Check whether every fact that should chain to
    further context actually has that next link present. If the text states
    context for a fact (an institution, a location, a role) and no fact
    carries that context forward as its own subject, this is a missing link,
    not an acceptable gap.

    2. FIND MISSING FACTS: Re-read the source text directly, not just the
    extracted facts. For each predicate in the allowed list, check whether
    the text supports a fact of that type, involving entities already in the
    extracted set, that is not present. If you find one, add it — but only if
    you can quote a literal source_span for it.

    3. CHECK ENTITY NAME CONSISTENCY: If the same real-world entity appears
    under two different names across facts, this breaks the chain between
    them. Normalize to one consistent name across all facts referring to the
    same entity.

    4. GROUNDING STILL APPLIES: Every fact you add or modify must have a real,
    verbatim source_span from the original text. This review pass is not
    exempt from that rule.

    5. VOCABULARY: Use only predicate values from {allowed_predicates} and
    subject_type/object_type values from {allowed_entity_types}. Do not
    invent new values, including when adding missing facts.

    6. DO NOT TOUCH WHAT'S ALREADY CORRECT: If a fact is already accurate,
    complete, and properly grounded, leave it exactly as it is.

    7. RETURN THE COMPLETE SET: Your output must be the full, corrected list of
    facts — not just the facts you changed or added."""



    def __init__(self,prompt):
        self.prompt=prompt
    
    def extract_triple(self):
        print("Extracting triples\n")
        response=client.chat.completions.create(
        messages=[
                {
                    "role": "system",
                    "content": self.SYSTEM_INSTRUCTIONS_PRIMARY.format(allowed_predicates=allowed_predicates)
                },
                {
                    "role": "user",
                    "content": self.prompt,
                }
            ],
        model="qwen/qwen3.8-27b",
        temperature=0,
        response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "Extraction_Triples",
            "strict": True,
            "schema": ExtractionResult.model_json_schema(),
            "additionalProperties": False
            }
        }
            )

        raw_result = json.loads(response.choices[0].message.content or "{}")
        result = ExtractionResult.model_validate(raw_result)
        print("First Pass\n")
        print(result.model_dump_json(indent=2))
        return result.model_dump_json(indent=2)

    def triple_verification(self):
        input="""Source text:
            {original_text}

            Extracted facts (JSON):
            {extracted_facts}
        """
        extracted_facts=self.extract_triple()
        print("Verification commencing\n")
        response=client.chat.completions.create(
            messages=[
                    {
                        "role": "system",
                        "content": self.VERIFICATION_INSTRUCTIONS.format(allowed_predicates=allowed_predicates)
                    },
                    {
                        "role": "user",
                        "content": input.format(original_text=self.prompt,extracted_facts=extracted_facts),
                    }
                ],
            model="qwen/qwen3.8-27b",
            temperature=0,
            response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "Extraction_Triples",
                "strict": True,
                "schema": ExtractionResult.model_json_schema(),
                "additionalProperties": False
                }
            }
                )
        
        raw_result = json.loads(response.choices[0].message.content or "{}")
        result = ExtractionResult.model_validate(raw_result)

        print("\nSecond Pass\n")
        print(result.model_dump_json(indent=2))







if __name__=='__main__':
    prompt="""
    Elena Petrova is currently studying at the Technical University of Munich,
    where she is pursuing a Master's degree. Before that, she completed her
    Bachelor's degree at the University of Belgrade. The University of Belgrade
    is located in Serbia. The Technical University of Munich is located in
    Germany. In her free time, Elena enjoys hiking in the Alps.
    """

    test=Model(prompt=prompt)
    test.triple_verification()
