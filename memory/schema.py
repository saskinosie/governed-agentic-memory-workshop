"""
The MemoryRecord collection: what a governed memory has to carry.

A plain RAG chunk has text and a vector. A memory record also needs enough
metadata to be judged later: who said it, when, in what context, how sure
they were, which tier it has earned, who corroborated it, who endorsed it,
when it should be looked at again, and whether it is still alive.

Weaviate-specific: the Property / DataType declarations and the filter
tokenization. Portable: the field list itself. Any store with metadata
filters can hold this.
"""

from datetime import datetime, timedelta, timezone

from weaviate import WeaviateClient
from weaviate.classes.config import Configure, DataType, Property, Tokenization
from weaviate.classes.query import Filter
from weaviate.collections import Collection

from memory.connect import collection_name


TIERS = ["session", "team", "org"]

# How long a record lives in each tier before Decay expires it. None means it
# does not expire on its own; it gets flagged for review instead.
LIFESPAN_DAYS = {"session": 7, "team": 90, "org": None}

# When Decay asks a human to look at a record again.
REVIEW_DAYS = {"session": 3, "team": 30, "org": 180}

STATUSES = ["active", "needs_review", "expired", "quarantined"]

SOURCE_TYPES = ["human", "document", "agent", "tool", "web"]


def _field(name: str) -> Property:
    """A text field used for exact-match filters, not for search."""
    return Property(name=name, data_type=DataType.TEXT, tokenization=Tokenization.FIELD)


PROPERTIES = [
    # What was observed.
    Property(name="text", data_type=DataType.TEXT),
    _field("topic"),
    # Capture: provenance.
    _field("source"),
    _field("source_type"),
    _field("context"),
    Property(name="confidence", data_type=DataType.NUMBER),
    Property(name="captured_at", data_type=DataType.DATE),
    _field("candidate_id"),
    # Promote: where it sits and who vouches for it.
    _field("tier"),
    _field("scope"),
    Property(name="corroboration_count", data_type=DataType.INT),
    Property(
        name="corroborated_by", data_type=DataType.TEXT_ARRAY, tokenization=Tokenization.FIELD
    ),
    _field("endorsed_by"),
    Property(name="promoted_at", data_type=DataType.DATE),
    # Decay: when it should be looked at again, and whether it is still alive.
    Property(name="expires_at", data_type=DataType.DATE),
    Property(name="review_at", data_type=DataType.DATE),
    Property(name="last_used", data_type=DataType.DATE),
    Property(name="use_count", data_type=DataType.INT),
    _field("status"),
]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def far_future() -> datetime:
    """Stand-in for 'does not expire'. Weaviate DATE fields cannot be null in a filter."""
    return datetime(2999, 1, 1, tzinfo=timezone.utc)


def lifecycle_dates(tier: str, start: datetime) -> dict:
    """expires_at and review_at for a record entering `tier` at `start`."""
    lifespan = LIFESPAN_DAYS[tier]
    return {
        "expires_at": start + timedelta(days=lifespan) if lifespan else far_future(),
        "review_at": start + timedelta(days=REVIEW_DAYS[tier]),
    }


def ensure_collection(
    client: WeaviateClient, name: str | None = None, reset: bool = False
) -> Collection:
    """Create the collection if it is missing (or recreate it when reset=True) and return it."""
    name = name or collection_name()
    if reset and client.collections.exists(name):
        client.collections.delete(name)
    if not client.collections.exists(name):
        client.collections.create(
            name=name,
            # Vectors come from the client (memory/embed.py), not a Weaviate module. That
            # keeps the embedding choice open and the pattern portable.
            vector_config=Configure.Vectors.self_provided(),
            properties=PROPERTIES,
        )
    return client.collections.get(name)


def reset_collection(client: WeaviateClient, name: str | None = None) -> Collection:
    return ensure_collection(client, name=name, reset=True)


def record_to_dict(obj) -> dict:
    """Flatten a Weaviate object into {uuid, ...properties}."""
    return {"uuid": str(obj.uuid), **obj.properties}


def fetch_all(
    collection: Collection, status: str | None = None, tier: str | None = None, limit: int = 1000
) -> list[dict]:
    """Every record, optionally filtered by status and tier. Fine for a workshop-sized store."""
    filters = None
    if status:
        filters = Filter.by_property("status").equal(status)
    if tier:
        tier_filter = Filter.by_property("tier").equal(tier)
        filters = tier_filter if filters is None else filters & tier_filter
    result = collection.query.fetch_objects(filters=filters, limit=limit)
    return [record_to_dict(o) for o in result.objects]
