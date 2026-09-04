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
    relation_type: str
    object: str
    qualifiers: list
    source_span: str

class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    triples: list[Triple]




class Model:
    SYSTEM_INSTRUCTIONS_PRIMARY = """You are extracting factual relationships from a document for a knowledge graph.
    Your only job is to identify what the text explicitly states — not what is
    likely true, not what you already know, not what would complete the picture.

    Each fact you extract has this shape:
    - subject
    - relation_type (from the allowed list below)
    - object
    - qualifiers: a list of additional key-value details that belong to THIS
    specific fact, if the text provides any
    - source_span: the exact sentence or clause that supports this fact

    Rules:

    1. GROUNDING: Every fact you extract — including every qualifier — must be
    directly and explicitly stated in the provided text. Do not use outside
    knowledge, do not infer unstated facts, and do not fill in plausible-
    sounding details (dates, locations, quantities) that the text does not
    contain. If a fact seems true but isn't stated, leave it out.

    2. EVIDENCE: For every fact, quote the exact sentence or clause from the
    source text that supports it, verbatim, in the source_span field. If you
    cannot find a literal sentence to quote, you cannot extract the fact.

    3. VOCABULARY: Use only relation_type values from this list: {allowed_predicates}
    Do not invent new relation types. If a real relationship in the text
    doesn't fit any type on this list, omit it rather than force it into the
    wrong category.

    4. ENTITY NAMING: Use the same, consistent name for an entity every time it
    appears, even if the text refers to it differently (e.g. "the University"
    vs. its full name) — pick one canonical form and use it throughout.

    5. QUALIFIER BUNDLING: If a sentence gives additional context about a fact —
    which institution, which location, what quantity, what date, what role —
    attach that context as a qualifier ON that same fact. Do not split one
    real-world fact into two separate, disconnected facts that each hold half
    the information. A fact and its context belong together every time, not
    only when convenient.

    6. NO EMPTY QUALIFIERS FROM GUESSING: Only add a qualifier if the text
    actually states it. An empty qualifiers list is correct and expected when
    the text gives no extra context — do not invent a qualifier just to fill
    the field.

    7. OMISSION OVER INVENTION: When in doubt about whether something is stated
    clearly enough to extract, do not extract it. An incomplete but accurate
    graph is far more useful than a complete but partially fabricated one."""


    VERIFICATION_INSTRUCTIONS = """You are reviewing and correcting a first-pass extraction of facts from a
    document for a knowledge graph. You are given the original source text and
    the facts already extracted from it. Your job is not to extract from
    scratch — it is to find and fix two specific problems in what's already
    there.

    Each fact has this shape:
    - subject
    - relation_type (from the allowed list below)
    - object
    - qualifiers: a list of additional key-value details belonging to this fact
    - source_span: the exact sentence or clause that supports this fact

    Rules:

    1. FIND FRAGMENTED FACTS: If two or more extracted facts share the same
    source_span and the same subject, check whether they actually describe
    ONE real-world fact that was incorrectly split apart. If so, merge them
    into a single fact, moving the split-off information into qualifiers.
    Do not merge facts that are genuinely separate, even if they share a
    source_span.

    2. FIND MISSING FACTS: Re-read the source text directly, not just the
    extracted facts. For each relation_type in the allowed list, check
    whether the text supports a fact of that type that is not present in
    the extracted set. If you find one, add it — but only if you can quote
    a literal source_span for it. Do not add anything you cannot ground in
    the text.

    3. GROUNDING STILL APPLIES: Every fact you add or modify must have a real,
    verbatim source_span from the original text. This review pass is not
    exempt from that rule — invented or paraphrased spans are not allowed
    here either.

    4. VOCABULARY: Use only relation_type values from this list: {allowed_predicates}
    Do not invent new relation types, including when adding missing facts.

    5. DO NOT TOUCH WHAT'S ALREADY CORRECT: If a fact is already accurate,
    complete, and properly grounded, leave it exactly as it is. Your job is
    to fix specific problems, not to regenerate or rephrase everything.

    6. RETURN THE COMPLETE SET: Your output must be the full, corrected list of
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
