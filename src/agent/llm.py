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

        self.client = Groq(api_key=os.environ["GROQ_API_KEY"],max_retries=3)
        self.retries = 0

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
                reasoning_effort="none",
                temperature=0,
                response_format={
                    "type":"json_schema",
                    "json_schema":{
                    "strict":True,
                    "name":schema.__name__,
                    "schema":schema.model_json_schema(),
                    }
                }

            )

            choice = response.choices[0]
            content = choice.message.content

            if choice.finish_reason == "length":
                raise RuntimeError("output truncated (hit the token limit)")
            if not content or not content.strip():
                raise RuntimeError(f"empty response (finish_reason={choice.finish_reason})")

            result = schema.model_validate_json(content)

            if getattr(result, "entities", None) == [] and self.retries < 2:
                self.retries += 1
                return self.send(prompt, system_instructions, schema)
            if getattr(result, "entities", None) == []:
                print(f"WARNING: empty after 3 attempts: {prompt[:60]!r}")

            self.retries = 0
            return result

        except (groq.RateLimitError, groq.APIConnectionError) as e:
            self.retries = 0
            raise RuntimeError(f"Transient Groq error, retry: {e}") from e

        except ValidationError as e:
            self.retries = 0
            raise RuntimeError(f"Invalid structure returned, retry: {e}") from e

        except groq.BadRequestError as e:
            if self.retries < 3:
                self.retries += 1
                return self.send(prompt, system_instructions, schema)
            self.retries = 0
            raise RuntimeError(f"Bad Request, More details: {e}") from e