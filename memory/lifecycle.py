"""
Steps 4 and 5: Promote and Decay.

Promote: a memory earns its way up. session -> team on corroboration from
distinct sources; team -> org only with an explicit human endorsement. The
endorsement is an intentional gate by design: the top tier is where the whole
organization reads from, so a person signs off.

Decay: memories age. Each tier has a lifespan and a review interval. Session
memories nobody used expire early. Org memories never expire on their own;
they get flagged for a human to look at again.

Every function takes `now` so a notebook can move the clock.

Weaviate-specific: the update calls (collection.data.update) and the fetch.
Portable: the rules.
"""

from datetime import datetime, timedelta

from weaviate.collections import Collection

from memory.capture import Candidate
from memory.embed import embed_one
from memory.schema import TIERS, fetch_all, lifecycle_dates, now_utc
from memory.score import Scores


# What it takes to move up. Confidence is the record's own; corroboration counts distinct sources.
PROMOTION_RULES = {
    "team": {"min_corroboration": 2, "min_confidence": 0.6, "needs_endorsement": False},
    "org": {"min_corroboration": 3, "min_confidence": 0.7, "needs_endorsement": True},
}

# Usage-based aging.
SESSION_UNUSED_DAYS = 3  # a session memory nobody read in 3 days was not worth keeping
TEAM_UNUSED_DAYS = 60  # a team memory idle for 60 days gets a second look


def _get(collection: Collection, uuid: str) -> dict:
    obj = collection.query.fetch_object_by_id(uuid)
    if obj is None:
        raise KeyError(f"no record {uuid}")
    return {"uuid": str(obj.uuid), **obj.properties}


def write_or_corroborate(
    collection: Collection,
    candidate: Candidate,
    scores: Scores,
    vector: list[float] | None = None,
    now: datetime | None = None,
) -> tuple[str, str]:
    """
    The write the Gate asked for. If the store already holds this memory (a near
    duplicate), a new record would be noise, so the existing one is corroborated
    instead. Returns (outcome, uuid).
    """
    now = now or now_utc()
    if scores.duplicate_of is not None:
        corroborate(collection, scores.duplicate_of.uuid, candidate.source, now=now)
        return "corroborated", scores.duplicate_of.uuid
    vector = vector or embed_one(candidate.text)
    uuid = collection.data.insert(properties=candidate.to_properties(now=now), vector=vector)
    return "written", str(uuid)


def corroborate(
    collection: Collection, uuid: str, source: str, now: datetime | None = None
) -> dict:
    """Another source agrees. Counts only if that source has not already vouched."""
    record = _get(collection, uuid)
    sources = list(record.get("corroborated_by") or [])
    if source not in sources:
        sources.append(source)
        collection.data.update(
            uuid=uuid,
            properties={
                "corroborated_by": sources,
                "corroboration_count": len(sources),
                "last_used": now or now_utc(),
            },
        )
    return _get(collection, uuid)


def endorse(collection: Collection, uuid: str, by: str, now: datetime | None = None) -> dict:
    """A human signs off. Required for the org tier. Recorded by name."""
    collection.data.update(uuid=uuid, properties={"endorsed_by": by, "last_used": now or now_utc()})
    return _get(collection, uuid)


def promotion_decision(record: dict) -> tuple[str | None, str]:
    """Which tier the record should move to next, if any, and why."""
    tier = record["tier"]
    if tier == TIERS[-1]:
        return None, "already at org"
    next_tier = TIERS[TIERS.index(tier) + 1]
    rule = PROMOTION_RULES[next_tier]
    count = int(record.get("corroboration_count") or 0)
    confidence = float(record.get("confidence") or 0)
    if count < rule["min_corroboration"]:
        return None, f"needs {rule['min_corroboration']} distinct sources, has {count}"
    if confidence < rule["min_confidence"]:
        return None, f"confidence {confidence:.2f} below {rule['min_confidence']}"
    if rule["needs_endorsement"] and not record.get("endorsed_by"):
        return None, "org tier needs a human endorsement"
    return next_tier, f"{count} sources, confidence {confidence:.2f}" + (
        f", endorsed by {record['endorsed_by']}" if rule["needs_endorsement"] else ""
    )


def promote(
    collection: Collection, uuid: str, now: datetime | None = None
) -> tuple[str | None, str]:
    """Apply the promotion rules to one record. Returns (new tier or None, reason)."""
    now = now or now_utc()
    record = _get(collection, uuid)
    if record.get("status") != "active":
        return None, f"status is {record.get('status')}"
    next_tier, reason = promotion_decision(record)
    if next_tier:
        collection.data.update(
            uuid=uuid,
            properties={"tier": next_tier, "promoted_at": now, **lifecycle_dates(next_tier, now)},
        )
    return next_tier, reason


def promote_all(collection: Collection, now: datetime | None = None) -> list[dict]:
    """One promotion pass over every active record."""
    results = []
    for record in fetch_all(collection, status="active"):
        new_tier, reason = promote(collection, record["uuid"], now=now)
        results.append(
            {
                "uuid": record["uuid"],
                "text": record["text"],
                "from": record["tier"],
                "to": new_tier,
                "reason": reason,
            }
        )
    return results


def decay_decision(record: dict, now: datetime) -> tuple[str | None, str]:
    """What Decay should do to this record right now: a new status, or None to leave it."""
    tier = record["tier"]
    expires_at = record.get("expires_at")
    review_at = record.get("review_at")
    last_used = record.get("last_used") or record.get("captured_at")
    use_count = int(record.get("use_count") or 0)
    age = now - record["captured_at"]

    if tier != "org" and expires_at and now >= expires_at:
        return "expired", f"{tier} lifespan ended {expires_at.date()}"
    if tier == "session" and use_count == 0 and age >= timedelta(days=SESSION_UNUSED_DAYS):
        return "expired", f"never used in {age.days} days"
    if tier == "team" and last_used and now - last_used >= timedelta(days=TEAM_UNUSED_DAYS):
        return "needs_review", f"not used since {last_used.date()}"
    if review_at and now >= review_at:
        return "needs_review", f"review was due {review_at.date()}"
    return None, "healthy"


def decay(collection: Collection, now: datetime | None = None) -> list[dict]:
    """One decay pass. Changes status; never deletes. Returns what it did and why."""
    now = now or now_utc()
    actions = []
    for record in fetch_all(collection, status="active"):
        new_status, reason = decay_decision(record, now)
        if new_status:
            collection.data.update(uuid=record["uuid"], properties={"status": new_status})
        actions.append(
            {
                "uuid": record["uuid"],
                "text": record["text"],
                "tier": record["tier"],
                "action": new_status or "keep",
                "reason": reason,
            }
        )
    return actions


def renew(collection: Collection, uuid: str, by: str, now: datetime | None = None) -> dict:
    """A human looked at a needs_review record and said it still holds. Back to active, clock reset."""
    now = now or now_utc()
    record = _get(collection, uuid)
    collection.data.update(
        uuid=uuid,
        properties={
            "status": "active",
            "endorsed_by": by,
            "last_used": now,
            **lifecycle_dates(record["tier"], now),
        },
    )
    return _get(collection, uuid)
