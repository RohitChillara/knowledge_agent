from __future__ import annotations
from groq import Groq
import groq
from pydantic import BaseModel,ValidationError
import os
from dotenv import load_dotenv
import json
load_dotenv()


class LLM:
    def __init__(self):

        self.client = Groq(api_key=os.environ["GROQ_API_KEY"])

    def send[T: BaseModel](self, prompt: str, system_instructions: str, schema: type[T]) -> T:
        try:
            response=self.client.chat.completions.create(
                messages=[
                    {
                        "role":"system",
                        "content":system_instructions,
                    },
                    {
                        "role":"user",
                        "content":prompt,
                    }
                ],
                model="qwen/qwen3.8-27b",
                temperature=0,
                response_format={
                    "type":"json_schema",
                    "json_schema":{
                    "strict":True,
                    "name":schema.__name__,
                    "schema":schema.model_json_schema(),
                    "additionalProperties":False
                    }
                }

            )

            content = response.choices[0].message.content
            if not content:
                raise RuntimeError("empty response")
            return schema.model_validate_json(content)

        except (groq.RateLimitError, groq.APIConnectionError) as e:
            raise RuntimeError(f"Transient Groq error, retry: {e}") from e

        except ValidationError as e:
            raise RuntimeError(f"Invalid structure returned, retry: {e}") from e
