from __future__ import annotations
from typing import Callable, Optional
from groq import Groq
import groq
from pydantic import BaseModel, ValidationError
import os
from dotenv import load_dotenv
from openai import OpenAI
load_dotenv()

MAX_RETRIES = 2          # 1 first attempt + 2 retries = 3 attempts
TEMP_STEP = 0.3          # temperature added on every retry


class LLM:
    def __init__(self):
        self.client = Groq(api_key=os.environ["GROQ_API_KEY"], max_retries=3)
        self.retries = 0
        self.temp = 0.0
        self.embed = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def embeddings(self,prompt:str):
        response = self.embed.embeddings.create(
            input = prompt,
            model = "text-embedding-3-small"
        )
        return response.data[0].embedding

    def send[T: BaseModel](self, prompt: str, system_instructions: str, schema: type[T],
                           is_valid: Optional[Callable[[T], bool]] = None) -> T:
        print("Retry " + str(self.retries))
        try:
            response = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": system_instructions,
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model="qwen/qwen3.8-27b",
                reasoning_effort="none",
                temperature=self.temp,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "strict": True,
                        "name": schema.__name__,
                        "schema": schema.model_json_schema(),
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

            # caller-defined check: retry with a higher temperature if it fails
            if is_valid is not None and not is_valid(result):
                if self.retries < MAX_RETRIES:
                    self.retries += 1
                    self.temp += TEMP_STEP
                    print("Temperature " + str(self.temp))
                    return self.send(prompt, system_instructions, schema, is_valid=is_valid)
                print(f"WARNING: invalid after {self.retries + 1} attempts: {prompt[:60]!r}")

            return result

        except (groq.RateLimitError, groq.APIConnectionError) as e:
            raise RuntimeError(f"Transient Groq error, retry: {e}") from e

        except ValidationError as e:
            raise RuntimeError(f"Invalid structure returned, retry: {e}") from e

        except groq.BadRequestError as e:
            # only the model's own JSON failure is worth retrying; a real bad request fails every time
            code = (e.body or {}).get("error", {}).get("code") if isinstance(e.body, dict) else None
            if code == "json_validate_failed" and self.retries < MAX_RETRIES:
                self.retries += 1
                self.temp += TEMP_STEP
                return self.send(prompt, system_instructions, schema, is_valid=is_valid)
            raise RuntimeError(f"Bad Request, More details: {e}") from e

        finally:
            # runs on every exit; recursive calls finish before this runs,
            # so the counters survive during a retry
            self.retries = 0
            self.temp = 0.0