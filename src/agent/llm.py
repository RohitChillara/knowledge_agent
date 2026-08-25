from groq import Groq
from dotenv import load_dotenv
import os
from pathlib import Path
import json
from pydantic import BaseModel


TEST_PREDICATES = [
    "studiesAt",           # current institution
    "previouslyStudiedAt", # past institution
    "pursuedDegree",       # links a person to a degree type (Bachelor, Master, etc.)
    "degreeInstitution",   # links a degree type to the institution that granted it
    "locatedIn",           # links a place/institution to its country or city
]

#System Instrucrions
allowed_predicates=",".join(TEST_PREDICATES)

SYSTEM_INSTRUCTIONS = """You are extracting factual relationships from a document for a knowledge graph.
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

load_dotenv(dotenv_path=Path.home() / ".env")


class Triple(BaseModel):
    subject: str
    relation_type: str
    object: str
    qualifiers: list
    source_span: str

class ExtractionResult(BaseModel):
    triples: list[Triple]

class Model:

    def __init__(self,prompt):
        self.prompt=prompt

    def extract_triple(self):
        client =Groq(api_key=os.environ.get("OPENAI_API_KEY"))
        response=client.chat.completions.create(
        messages=[
                {
                    "role": "system",
                    "content": SYSTEM_INSTRUCTIONS.format(allowed_predicates=allowed_predicates)
                },
                {
                    "role": "user",
                    "content": self.prompt,
                }
            ],
        model="openai/gpt-oss-120b",
        response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "Extraction_Triples",
            "schema": ExtractionResult.model_json_schema()
        }
    }
        )

        raw_result = json.loads(response.choices[0].message.content or "{}")
        result = ExtractionResult.model_validate(raw_result)
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
    test.extract_triple()
