from __future__ import annotations
from groq import Groq
import groq
from pydantic import BaseModel,ValidationError
import os
from pathlib import Path
import json



class LLM:
    def __init__(self,api_key:str):
        try:
            self.client=Groq(api_key=api_key)

        except groq.AuthenticationError as e:
            raise RuntimeError("Invalid Groq API key") from e

    def send[T:BaseModel](self,prompt:str,system_instructions:str,schema:T)->T:
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
                    "additionalProperties":False
                    }
                }

            )

            result = json.loads(response.choices[0].message.content or "{}")
            validation=schema.model_validate(result)
            return validation

        except (groq.RateLimitError, groq.APIConnectionError) as e:
            raise RuntimeError(f"Transient Groq error, retry: {e}") from e

        except ValidationError as e:
            raise RuntimeError(f"Invalid structure returned, retry: {e}") from e
