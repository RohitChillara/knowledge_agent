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

# --- One-time setup (rerun after every ingest) ---

SET_ALIASES = """
MATCH (e:Entity)
OPTIONAL MATCH (:Chunk)-[m:MENTIONS]->(e)
UNWIND coalesce(m.mentions, []) + [e.name] AS form
WITH e, collect(DISTINCT form) AS aliases
SET e.aliases = aliases,
    e.aliases_lc = [a IN aliases | toLower(a)],
    e.aliases_text = reduce(s = "", a IN aliases | s + " " + a)
"""

CREATE_FULLTEXT_INDEX = """
CREATE FULLTEXT INDEX entity_names IF NOT EXISTS
FOR (e:Entity) ON EACH [e.name, e.aliases_text]
"""

# --- Entity lookup ---

# params: text
EXACT_MATCH = """
MATCH (e:Entity)
WHERE toLower($text) IN e.aliases_lc
RETURN e.id AS id, e.name AS name, e.label AS label
"""

# params: lucene_query (e.g. "Chesire~ Cat~", Lucene-escaped), min_score, label
FUZZY_MATCH = """
MATCH (node:Entity)
SEARCH node IN (FULLTEXT INDEX entity_names FOR $lucene_query LIMIT 10)
SCORE AS score
WITH node, score
WHERE score >= $min_score
RETURN node.id AS id, node.name AS name, node.label AS label, score,
       node.label = $label AS label_match
ORDER BY label_match DESC, score DESC
LIMIT 3
"""

# --- Neighbourhood and traversal ---

# params: ids
PREDICATE_SUMMARY = """
MATCH (e:Entity)-[r:RELATED]-(n:Entity)
WHERE e.id IN $ids
RETURN e.name AS entity,
       r.predicate AS predicate,
       CASE WHEN startNode(r) = e THEN 'out' ELSE 'in' END AS direction,
       count(*) AS edges,
       collect(DISTINCT n.name)[..3] AS examples
ORDER BY entity, edges DESC
"""

# params: ids, predicates, visited, beam
FOLLOW_PREDICATES = """
MATCH (e:Entity)-[r:RELATED]-(n:Entity)
WHERE e.id IN $ids
  AND r.predicate IN $predicates
  AND NOT n.id IN $visited
RETURN e.name AS from,
       r.predicate AS predicate,
       CASE WHEN startNode(r) = e THEN 'out' ELSE 'in' END AS direction,
       n.id AS to_id, n.name AS to,
       r.evidence AS evidence, r.chunk_id AS chunk_id
LIMIT $beam
"""

# params: a, b
SHORTEST_PATH = """
MATCH (a:Entity {id: $a}), (b:Entity {id: $b})
MATCH p = shortestPath((a)-[:RELATED*..4]-(b))
RETURN [n IN nodes(p) | n.name] AS names,
       [r IN relationships(p) | r.predicate] AS predicates,
       [r IN relationships(p) | r.evidence] AS evidence
"""

# --- Evidence and fallback ---

# params: chunk_ids
EVIDENCE_CHUNKS = """
MATCH (c:Chunk) WHERE c.id IN $chunk_ids
OPTIONAL MATCH (prev:Chunk)-[:NEXT_CHUNK]->(c)
OPTIONAL MATCH (c)-[:NEXT_CHUNK]->(next:Chunk)
RETURN c.id AS id, c.index AS idx, c.text AS text,
       prev.text AS prev_text, next.text AS next_text
ORDER BY c.index
"""

ENTITIES_FROM_CHUNKS = """
MATCH (c:Chunk)-[:MENTIONS]->(e:Entity)
WHERE c.id IN $chunk_ids
RETURN e.id AS id, e.name AS name, e.label AS label, count(c) AS chunks
ORDER BY chunks DESC, name
LIMIT $k
"""

# params: none
ALL_PREDICATES = """
MATCH ()-[r:RELATED]->()
RETURN collect(DISTINCT r.predicate) AS predicates
"""


# params: steps = [{"entity": ..., "predicates": [...]}, ...], visited = [names], beam = int
FOLLOW_STEPS = """
UNWIND $steps AS step
MATCH (e:Entity {name: step.entity})-[r:RELATED]-(n:Entity)
WHERE r.predicate IN step.predicates
  AND NOT n.name IN $visited
WITH e, r, n
LIMIT $beam
RETURN e.name AS entity,
       r.predicate AS predicate,
       CASE WHEN startNode(r) = e THEN 'out' ELSE 'in' END AS direction,
       count(*) AS edges,
       collect(DISTINCT n.name) AS examples,
       collect(DISTINCT n.id) AS next_ids,
       collect(r.evidence) AS evidence,
       collect(DISTINCT r.chunk_id) AS chunk_ids
ORDER BY entity, edges DESC
"""

VECTOR_SEARCH_CHUNKS = """
MATCH (c:Chunk)
SEARCH c IN (VECTOR INDEX chunk_embeddings FOR $query_vector LIMIT $k)
SCORE AS score
RETURN c.id AS id, c.index AS idx, c.chapter AS chapter, score,
       left(c.text, 80) AS start
ORDER BY score DESC
"""