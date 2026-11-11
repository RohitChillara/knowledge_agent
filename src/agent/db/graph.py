from neo4j import AsyncGraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable
import os
from dotenv import load_dotenv
from typing import Literal, get_args, Optional
from agent.db import queries
load_dotenv()

class Connection:
    def __init__(self):
        self.URI = os.environ["NEO4J_URI"]
        self.auth = (os.environ["DB_USER"], os.environ["DB_PWD"])

    async def connect(self):
        driver = AsyncGraphDatabase.driver(self.URI, auth=self.auth)
        try:
            await driver.verify_connectivity()
        except (Neo4jError, ServiceUnavailable) as e:
            await driver.close()
            raise ConnectionError(f"Cannot connect to Neo4j at {self.URI}: {e}") from e
        return driver


class Graph:
    def __init__(self):
        self.db = Connection()
        self.driver = None
        self.NodeLable = Literal["SourceDocument", "Chunk", "Entity","Connect"]


    @classmethod
    async def create(cls):
        self = cls()
        self.driver = await self.db.connect()
        return self

    async def close(self):
        if self.driver is not None:
            await self.driver.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()
        return False

    async def get(self, query:str,params:Optional[dict] = None):
        return await self.driver.execute_query(query,parameters_=params or {}, database_="neo4j")
            

    async def execute(self, type: Literal["SourceDocument", "Chunk", "Entity", "Connect"],
            node_id: Optional[str] = None, props: Optional[dict] = None,
            source_label: Optional[str] = None, rel: Optional[str] = None,
            target_label: Optional[str] = None, source_id: Optional[str] = None,
            target_id: Optional[str] = None):

        if type not in get_args(self.NodeLable):
            raise ValueError(f"unknown type label: {type!r}")

        if type == "SourceDocument":
            query = queries.create_node_query(type)
            params = {"id":node_id, "props":props or {}}
            
        elif type == "Chunk":
            query = queries.create_node_query(type)
            params = {"id":node_id, "props":props or {}}

        elif type == "Entity":
            query = queries.create_node_query(type)
            params = {"id":node_id, "props":props or {}}

        elif type == "Connect":
            if source_label is None or target_label is None:
                raise ValueError("Missing source or target label")
            if source_id is None or target_id is None:
                raise ValueError("Missing source or target ids")
            if rel is None or rel not in queries.REL_TYPES:
                raise ValueError(
                    f"Missing or invalid relationship type. "
                    f"Expected one of {queries.REL_TYPES!r}, received {rel!r}"
                )

            query = queries.connect_query(source_label=source_label,rel=rel,target_label=target_label)
            params={
                "source_id":source_id,
                "target_id":target_id,
                "props": props or {}
            }
            

        await self.driver.execute_query(query, parameters_=params, database_="neo4j")


    



