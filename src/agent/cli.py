from __future__ import annotations
import argparse
import asyncio
from pathlib import Path

from agent.ingest import chunk
from agent.ingest.kg_generator import KG_Generator


async def run_ingest(args):
    text = chunk.load_text(args.path)
    title = args.title or args.path.stem
    async with await KG_Generator.create(text, title=title, max_parallel=args.parallel) as kg:
        await kg.pipeline()


parser = argparse.ArgumentParser(prog="agent", description="A knowledge agent")
sub = parser.add_subparsers(dest="command", required=True)

ingest = sub.add_parser("ingest", help="Ingest data into the knowledge graph")
ingest.add_argument("path", type=Path, help="Text file to ingest")
ingest.add_argument("--title", default="", help="Document title (default: file name)")
ingest.add_argument("--parallel", type=int, default=2, help="Concurrent LLM calls")
ingest.add_argument("--chunking", choices=["Recursive", "Semantic"], default="Recursive")
ingest.set_defaults(func=run_ingest)


def main():
    args = parser.parse_args()
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()