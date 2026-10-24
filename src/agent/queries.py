from typing import Literal, get_args

NodeLabel = Literal["SourceDocument", "Chunk", "Entity"]
RelType = Literal["PART_OF", "NEXT_CHUNK", "MENTIONS", "RELATED"]

NODE_LABELS = get_args(NodeLabel)
REL_TYPES = get_args(RelType)


# --- constraints: run once at startup ---------------------------------
CONSTRAINTS = [
    f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS "
    f"FOR (n:{label}) REQUIRE n.id IS UNIQUE"
    for label in NODE_LABELS
]


# --- templates: labels and types cannot be Cypher parameters -----------
_CREATE_NODE = (
    "MERGE (n:{label} {{id: $id}}) "
    "ON CREATE SET  n.created_at = datetime() "
    "SET n += $props"
)

_CONNECT = (
    "MATCH (a:{source_label} {{id: $source_id}}), "
    "(b:{target_label} {{id: $target_id}}) "
    "MERGE (a)-[r:{rel}]->(b) "
    "SET r += $props "
    "RETURN count(r) AS n"
)


def create_node_query(label: str) -> str:
    if label not in NODE_LABELS:
        raise ValueError(f"unknown node label: {label!r}")
    return _CREATE_NODE.format(label=label)


def connect_query(source_label: str, rel: str, target_label: str) -> str:
    for label in (source_label, target_label):
        if label not in NODE_LABELS:
            raise ValueError(f"unknown node label: {label!r}")
    if rel not in REL_TYPES:
        raise ValueError(f"unknown relationship type: {rel!r}")
    return _CONNECT.format(
        source_label=source_label, rel=rel, target_label=target_label
    )


# --- checks: run after ingestion --------------------------------------
# params: doc_id. Expect (chunk_count, 1, chunk_count).
CHECK_CHUNKS = """
MATCH (c:Chunk)-[:PART_OF]->(:SourceDocument {id: $doc_id})
RETURN count(c) AS chunks, min(c.index) AS first, max(c.index) AS last
"""

# params: doc_id. Expect reachable = chunk_count - 1.
CHECK_CHAIN = """
MATCH (:Chunk {id: $doc_id + ':1'})-[:NEXT_CHUNK*]->(c:Chunk)
RETURN count(c) AS reachable
"""

# Expect 0.
CHECK_ORPHAN_CHUNKS = """
MATCH (c:Chunk)
WHERE NOT (c)-[:PART_OF]->(:SourceDocument)
RETURN count(c) AS orphans
"""

# Entities by label: shows how much lands in OTHER.
CHECK_ENTITY_LABELS = """
MATCH (e:Entity)
RETURN e.label AS label, count(*) AS n
ORDER BY n DESC
"""

# Relationship predicates, to spot near-duplicates.
CHECK_PREDICATES = """
MATCH ()-[r:RELATED]->()
RETURN r.predicate AS predicate, count(*) AS n
ORDER BY n DESC
"""