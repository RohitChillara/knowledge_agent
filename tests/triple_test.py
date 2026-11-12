from agent.db import graph
from agent.ingest.kg_generator import KG_Generator
from agent.llm import schema
import asyncio

query = """MATCH (c:Chunk)
OPTIONAL MATCH (c)-[m:MENTIONS]->(e:Entity)
RETURN c.id AS id,
       c.index AS idx,
       c.text AS text,
       collect(CASE WHEN e IS NOT NULL
               THEN {name: e.name, label: e.label, mentions: m.mentions} END) AS entities
ORDER BY idx"""


async def main():
    g = graph.Graph()
    async with await g.create() as driver:
        result = await driver.get(query=query)
        for index, records in enumerate(result.records,start=1):
            ents = records["entities"]
            entities = [schema.Entity.model_validate(d) for d in records["entities"]]
            result = schema.Enitity_extraction(entities=entities)
            # print(entities)
            async with await KG_Generator.create("HI",title="TEST") as kg:
                triples = await kg.triple_extraction(entities=result,chunk=records["text"])
                print(triples)


asyncio.run(main())
