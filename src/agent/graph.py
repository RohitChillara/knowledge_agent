from neo4j import GraphDatabase
from dotenv import load_dotenv
import os
import json
from pathlib import Path
load_dotenv(dotenv_path=Path.home() / ".env")

URI = os.environ.get("NEO4J_URI")
AUTH = (os.environ.get("DB_USER"), os.environ.get("DB_PWD"))

driver=GraphDatabase.driver(URI, auth=AUTH)

# summary = driver.execute_query("""
#     CREATE (a:Person {name: $name})
#     CREATE (b:Person {name: $friendName})
#     CREATE (a)-[:KNOWS]->(b)
#     """,
#     name="Alice", friendName="David",
#     database_="neo4j",
# ).summary
# print("Created {nodes_created} nodes in {time} ms.".format(
#     nodes_created=summary.counters.nodes_created,
#     time=summary.result_available_after
# ))


records, summary, keys = driver.execute_query("""
    MATCH (p:Person)-[:KNOWS]->(:Person)
    RETURN p.name AS name
    """,
    database_="neo4j",
)

# Loop through results and do something with them
for record in records:
    print(record.data())  # obtain record as dict

# Summary information
print("The query `{query}` returned {records_count} records in {time} ms.".format(
    query=summary.query, records_count=len(records),
    time=summary.result_available_after
))

driver.close()