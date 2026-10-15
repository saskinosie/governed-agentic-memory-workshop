"""
Seed the store with the Brightwater Supply Co. handbook: about fifty short
facts about policies, people, systems, products, and customers. Fictional
company, fictional people. They land in the org tier, endorsed, because a
document loader with a human owner is the one path that skips the gate.

Portable: all of it except the batch insert.
"""

import json
import time
from datetime import datetime, timedelta

from weaviate.collections import Collection

from memory.capture import Candidate
from memory.connect import REPO_ROOT
from memory.embed import embed
from memory.schema import now_utc


SEED_PATH = REPO_ROOT / "data" / "seed_corpus.json"
ATTACKS_PATH = REPO_ROOT / "data" / "attacks.json"
HANDBOOK_OWNER = "user:priya.natarajan"


def load_seed() -> list[dict]:
    with open(SEED_PATH) as f:
        return json.load(f)


def load_attacks() -> list[dict]:
    with open(ATTACKS_PATH) as f:
        return json.load(f)


def wait_for_index(collection: Collection, timeout: float = 30.0) -> None:
    """
    Block until the vector index has caught up with the inserts. Some tiers index
    asynchronously, and a gate that checks for duplicates against a half-built
    index is a gate that lets duplicates through on the first run.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        shards = collection.shards()
        if all(
            s.vector_queue_length == 0 and s.vector_indexing_status != "INDEXING" for s in shards
        ):
            return
        time.sleep(0.25)
    raise TimeoutError("the vector index did not catch up within 30 seconds")


def seed_store(collection: Collection, now: datetime | None = None) -> int:
    """Insert the handbook as endorsed org-tier records. Returns how many were written."""
    now = now or now_utc()
    items = load_seed()
    vectors = embed([item["text"] for item in items])
    captured = now - timedelta(days=30)  # the handbook predates the session
    with collection.batch.fixed_size(batch_size=50) as batch:
        for item, vec in zip(items, vectors):
            cand = Candidate(
                text=item["text"],
                source=item["source"],
                source_type=item["source_type"],
                context="handbook ingest",
                confidence=item["confidence"],
                topic=item["topic"],
                scope="org",
                tier="org",
                captured_at=captured,
                candidate_id=item["id"],
            )
            props = cand.to_properties(now=captured)
            props["endorsed_by"] = HANDBOOK_OWNER
            batch.add_object(properties=props, vector=vec)
    failed = collection.batch.failed_objects
    if failed:
        raise RuntimeError(f"{len(failed)} seed records failed to insert: {failed[0].message}")
    wait_for_index(collection)
    return len(items)
