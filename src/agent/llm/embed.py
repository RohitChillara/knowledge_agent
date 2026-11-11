from __future__ import annotations
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv
import asyncio
load_dotenv()

client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

async def embed(text:list[str])->list:
    response = await client.embeddings.create(
        input = text,
        model = os.environ["EMBED_MODEL"]
    )
    return [d.embedding for d in sorted(response.data, key=lambda d: d.index)]