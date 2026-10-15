"""
The read path, kept small on purpose. This workshop is about writes.

recall() runs a hybrid query (dense vector plus BM25 keywords) over active
records, optionally restricted to tiers, and can mark the hits as used so
Decay knows what the agent actually reads.

Weaviate-specific: the hybrid query and the filter syntax. Portable: the
idea that reads are tier-filtered and leave a usage trail.
"""

from datetime import datetime

from weaviate.classes.query import Filter, MetadataQuery
from weaviate.collections import Collection

from memory.embed import embed_one
from memory.schema import now_utc, record_to_dict


def recall(
    collection: Collection,
    query: str,
    limit: int = 5,
    alpha: float = 0.5,
    tiers: list[str] | None = None,
    scope: str | None = None,
    track_usage: bool = False,
    now: datetime | None = None,
) -> list[dict]:
    """
    Hybrid search over active memories, limited to org records plus the one scope
    you name. alpha=1 is pure vector, alpha=0 is pure
    keyword. 0.5 is a fair default; drop it toward 0 when exact words matter
    (names, amounts, system identifiers).
    """
    filters = Filter.by_property("status").equal("active")
    if tiers:
        filters = filters & Filter.by_property("tier").contains_any(tiers)
    # Fail closed on scope: with no scope named you see only shared org memories.
    # Name a scope to also see that customer's or team's records, never anyone else's.
    filters = filters & Filter.by_property("scope").contains_any(
        [scope, "org"] if scope else ["org"]
    )
    result = collection.query.hybrid(
        query=query,
        vector=embed_one(query),
        alpha=alpha,
        limit=limit,
        filters=filters,
        return_metadata=MetadataQuery(score=True),
    )
    hits = []
    for o in result.objects:
        hit = record_to_dict(o)
        hit["score"] = round(float(o.metadata.score or 0.0), 4)
        hits.append(hit)
    if track_usage:
        stamp = now or now_utc()
        for hit in hits:
            collection.data.update(
                uuid=hit["uuid"],
                properties={"last_used": stamp, "use_count": int(hit.get("use_count") or 0) + 1},
            )
    return hits


def show(hits: list[dict], width: int = 80) -> None:
    for h in hits:
        print(f"{h['score']:.3f}  [{h['tier']:7s}] {h['text'][:width]}")
        print(
            f"        from {h['source']} ({h['source_type']}), confidence {h['confidence']:.2f}, x{h['corroboration_count']}"
        )
