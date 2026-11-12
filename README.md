# Knowledge Graph Agent

Builds a knowledge graph from plain-text documents with an LLM, stores it in Neo4j, and
retrieves over it (graph traversal plus vector search). The goal is to keep LLM cost low
while getting answers that are grounded in the source text: every fact in the graph keeps
the sentence it came from.

## How ingestion works

```
document ─► chunks ─► entities (LLM) ─► clean ─► triples (LLM) ─► clean ─► Neo4j
                 └──► embeddings (one batch call) ───────────────────────► Neo4j
```

1. **Chunking** – recursive, token-based splitting (`cl100k_base`).
2. **Entity extraction** – one LLM call per chunk with a strict JSON schema. Each entity has a
   name, one of eight labels (PERSON, ORGANIZATION, LOCATION, EVENT, PRODUCT, WORK, CONCEPT,
   OTHER) and the surface forms ("mentions") the chunk uses for it.
3. **Entity cleaning** (code, deterministic):
   - strips articles and titles 
   - splits bracketed abbreviations
   - keeps only mentions that occur verbatim in the chunk

4. **Relation extraction** – a second LLM call per chunk links the cleaned entities as
   `(subject, predicate, object, evidence)` triples, with a preferred predicate vocabulary.
5. **Triple cleaning** (code):
   - maps short forms back to main names; forms shared by two entities are treated as ambiguous and not guessed
   - evidence must be an exact quote from the chunk
   - normalises predicates, drops self-loops and duplicates
   - stores a `grounded` score: how many of the two entities are named in the evidence (0–2)
6. **Writing** – idempotent `MERGE` writes, batched with `UNWIND`. Entity ids are a hash of the
   name, so the same entity from different chunks becomes one node; the label stored is the
   most frequent one across chunks.


## Graph schema
```
(:SourceDocument {id, title, text})
(:Chunk {id, index, text, embedding})-[:PART_OF]->(:SourceDocument)
(:Chunk)-[:NEXT_CHUNK]->(:Chunk)
(:Chunk)-[:MENTIONS {mentions}]->(:Entity {id, name, label, aliases})
(:Entity)-[:RELATED {predicate, chunk_id, evidence, grounded}]->(:Entity)
```

Ids: document = SHA-256 of its text; chunk = `<doc_id>:<index>`; entity = SHA-256 of the
case-folded name. Constraints, a full-text index (entity names and aliases) and a vector index
(chunk embeddings, 1536-d, cosine) are created automatically before each ingest.

## Running it

### Requirements

- Docker with Docker Compose
- API keys for Groq (extraction) and OpenAI (embeddings)

### Configuration

Create `.env` in the project root (it is git- and docker-ignored):

```
GROQ_API_KEY=...
OPENAI_API_KEY=...
EMBED_MODEL=text-embedding-3-small
NEO4J_URI=bolt://localhost:7687
NEO4J_DATABASE=neo4j
DB_USER=neo4j
DB_PWD=<at least 8 characters>
```

`DB_PWD` also sets the Neo4j password on the first start of an empty database. Changing it
later does not change the password inside Neo4j.

### With Docker (recommended)

```bash
# start Neo4j (Browser: http://localhost:7474, user neo4j, password DB_PWD)
docker compose up -d

# ingest a document; starts Neo4j too if needed and waits until it is healthy
docker compose run --rm --build agent ingest data/NIAM.txt --title NIAM --parallel 2

# stop (the graph is kept in the neo4j_data volume)
docker compose down
```

`docker compose down -v` also deletes the volume, i.e. the whole graph.

### Locally

```bash
uv sync
source .venv/bin/activate
docker compose up -d neo4j
agent ingest data/NIAM.txt --title NIAM --parallel 2
```

`agent --help` and `agent ingest --help` list all options.

### After an ingest

The run ends with a report: chunk count and index range, chain reachability, orphan chunks,
embedding sizes, entities per label and predicate counts. Quick checks in the Browser:

```cypher
MATCH (s:Entity)-[r:RELATED]->(o:Entity)
RETURN s.name, r.predicate, o.name, r.grounded, r.evidence LIMIT 50
```

## Project layout

```
src/agent/
  cli.py              command-line entry point (`agent`)
  ingest/             chunking and the ingestion pipeline (kg_generator.py)
  llm/                LLM client with retries and cache, prompts, schemas, embeddings
  db/                 Neo4j connection and all Cypher queries
  retrieval/          entity linking, neighbourhood, guided multi-hop traversal
data/                 input documents (mounted into the container)
cache/                LLM response cache (created on first run)
```

## Known limitations and next steps

- **Entity resolution** – surnames and abbreviations that appear without their full name in a
  chunk (`Voss`, `TUM`) are still separate nodes. Candidate pairs can be found with a query;
  merging them needs care (two people share the surname Keller).
- **Wrong objects** – when the right entity is missing, the model sometimes attaches a relation
  to a related one (`leads` the institute instead of a group). The `grounded` score flags part
  of this; a planned check flags predicates whose label pairs are unusual for the document.
- **Text cleaning** – headings, page headers and footers are not removed yet.
- **Retrieval** – implemented in `retrieval/`, not yet exposed in the CLI.
- **Chunking option** – `--chunking` is accepted but the pipeline currently always uses
  recursive chunking.
- **Evaluation** – a hand-labelled gold set (entities, merge cases, facts with evidence) exists
  for scoring extraction; a graph-vs-vector-RAG comparison is planned.
