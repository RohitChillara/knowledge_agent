from agent.ingest import chunk as c
from agent.ingest.kg_generator import KG_Generator as kg
import asyncio

text = c.load_text("/home/rohitchillara/agent/data/NIAM.txt")

async def main():
    async with await kg.create(text,title="NIAM") as kg1:
        await kg1.pipeline(max_parallel= 2)


asyncio.run(main())