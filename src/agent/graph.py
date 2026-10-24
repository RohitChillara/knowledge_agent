from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError
import os
from dotenv import load_dotenv
from typing import Literal, get_args, Optional
from agent import queries
load_dotenv()

class Connection:
    def __init__(self):
        self.URI = os.environ["NEO4J_URI"]
        self.auth = (os.environ["DB_USER"],os.environ["DB_PWD"])

    def connect(self):
        try:
            driver = GraphDatabase.driver(self.URI, auth=self.auth)
            return driver
        except Neo4jError as e:
            driver.close()
            raise ValueError("Error: "+e)


class Graph:
    def __init__(self):
        self.db = Connection()
        self.driver = self.db.connect()
        self.NodeLable = Literal["SourceDocument", "Chunk", "Entity"]

    def create(self, text: str, node_id: str,props: Optional[dict], type: Literal["SourceDocument", "Chunk", "Entity"]):

        if type not in get_args(self.NodeLable):
            raise ValueError(f"unknown node label: {type!r}")

        if type == "SourceDocument":
            query = queries.create_node_query(type)
            print(query)

        elif type == "Chunk":
            query = queries.create_node_query(type)

        elif type == "Entity":
            query = queries.create_node_query(type)


        self.driver.execute_query(query, id = node_id, props = props or {}, database_="knowledge") 



