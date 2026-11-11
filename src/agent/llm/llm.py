from __future__ import annotations
from typing import Callable, Optional
from groq import AsyncGroq
import groq
from pydantic import BaseModel, ValidationError
import os
from dotenv import load_dotenv
from openai import OpenAI
import asyncio
load_dotenv()

MAX_RETRIES = 2          # 1 first attempt + 2 retries = 3 attempts
TEMP_STEP = 0.3          # temperature added on every retry


class LLM:
    def __init__(self):
        self.client = AsyncGroq(api_key=os.environ["GROQ_API_KEY"], max_retries=3)


    async def send[T: BaseModel](self, prompt: str, system_instructions: str, schema: type[T],
                                 is_valid: Optional[Callable[[T], bool]] = None,
                                 attempt: int = 0) -> T:
        temp = attempt * TEMP_STEP
        print(f"Attempt {attempt}, temperature {temp}")
        try:
            response = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_instructions},
                    {"role": "user", "content": prompt},
                ],
                model="qwen/qwen3.8-27b",
                reasoning_effort="none",
                temperature=temp,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "strict": True,
                        "name": schema.__name__,
                        "schema": schema.model_json_schema(),
                    },
                },
            )

            choice = response.choices[0]
            content = choice.message.content

            if choice.finish_reason == "length":
                raise RuntimeError("output truncated (hit the token limit)")
            if not content or not content.strip():
                raise RuntimeError(f"empty response (finish_reason={choice.finish_reason})")

            result = schema.model_validate_json(content)

            if is_valid is not None and not is_valid(result):
                if attempt < MAX_RETRIES:
                    return await self.send(prompt, system_instructions, schema,
                                           is_valid=is_valid, attempt=attempt + 1)
                print(f"WARNING: invalid after {attempt + 1} attempts: {prompt[:60]!r}")

            return result

        except groq.RateLimitError as e:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2 ** (attempt + 1))      # 2 s, then 4 s
                return await self.send(prompt, system_instructions, schema,
                                       is_valid=is_valid, attempt=attempt + 1)
            raise RuntimeError(f"Rate limited after {attempt + 1} attempts: {e}") from e

        except groq.APIConnectionError as e:
            raise RuntimeError(f"Transient Groq error, retry: {e}") from e

        except ValidationError as e:
            raise RuntimeError(f"Invalid structure returned, retry: {e}") from e

        except groq.BadRequestError as e:
            code = (e.body or {}).get("error", {}).get("code") if isinstance(e.body, dict) else None
            if code == "json_validate_failed" and attempt < MAX_RETRIES:
                return await self.send(prompt, system_instructions, schema,
                                       is_valid=is_valid, attempt=attempt + 1)
            raise RuntimeError(f"Bad Request, More details: {e}") from e