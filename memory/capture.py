"""
Step 1: Capture.

A candidate memory is a proposal, not a fact. It arrives with provenance
(who, when, in what context, how confident) and nothing is written until the
Gate says so.

Portable: all of it.
"""

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime

from memory.schema import SOURCE_TYPES, TIERS, lifecycle_dates, now_utc


@dataclass
class Candidate:
    """What an agent (or a person, or a document loader) proposes to remember."""

    text: str
    source: str  # who produced it: "user:ada", "agent:harbor", "doc:handbook-2026", "web:forum"
    source_type: str  # human | document | agent | tool | web
    context: str  # where it was observed: "support-session-4471", "handbook ingest"
    confidence: float  # the source's own confidence, 0 to 1
    topic: str = "general"  # policy | people | systems | product | customer | process | general
    scope: str = "session"  # whose memory this is: a user handle, a team, or "org"
    tier: str = (
        "session"  # every candidate starts at the bottom unless a document loader says otherwise
    )
    captured_at: datetime = field(default_factory=now_utc)
    candidate_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def validate(self) -> list[str]:
        """Provenance problems, as plain sentences. Empty list means the candidate is well formed."""
        problems = []
        if not self.text or not self.text.strip():
            problems.append("text is empty")
        if not self.source or ":" not in self.source:
            problems.append("source must look like kind:name, for example user:ada or doc:handbook")
        if self.source_type not in SOURCE_TYPES:
            problems.append(f"source_type must be one of {SOURCE_TYPES}")
        if not self.context or not self.context.strip():
            problems.append("context is empty")
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not 0.0 <= float(self.confidence) <= 1.0
        ):
            problems.append("confidence must be a number between 0 and 1")
        if self.tier not in TIERS:
            problems.append(f"tier must be one of {TIERS}")
        if self.captured_at.tzinfo is None:
            problems.append("captured_at must be timezone-aware")
        return problems

    def to_properties(self, now: datetime | None = None) -> dict:
        """The Weaviate properties for a freshly admitted record."""
        start = now or self.captured_at
        return {
            "text": self.text.strip(),
            "topic": self.topic,
            "source": self.source,
            "source_type": self.source_type,
            "context": self.context,
            "confidence": float(self.confidence),
            "captured_at": self.captured_at,
            "candidate_id": self.candidate_id,
            "tier": self.tier,
            "scope": self.scope,
            "corroboration_count": 1,
            "corroborated_by": [self.source],
            "endorsed_by": "",
            "promoted_at": start,
            "last_used": start,
            "use_count": 0,
            "status": "active",
            **lifecycle_dates(self.tier, start),
        }

    def as_dict(self) -> dict:
        d = asdict(self)
        d["captured_at"] = self.captured_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Candidate":
        """Build a Candidate from a JSON record in data/. Extra keys (labels) are ignored."""
        keys = {
            "text",
            "source",
            "source_type",
            "context",
            "confidence",
            "topic",
            "scope",
            "tier",
            "candidate_id",
        }
        kwargs = {k: v for k, v in d.items() if k in keys}
        if "captured_at" in d and d["captured_at"]:
            kwargs["captured_at"] = datetime.fromisoformat(d["captured_at"])
        return cls(**kwargs)


def capture(
    text: str,
    source: str,
    source_type: str,
    context: str,
    confidence: float,
    topic: str = "general",
    scope: str = "session",
    tier: str = "session",
) -> Candidate:
    """Make a candidate. This is the whole Capture step: wrap the observation in its provenance."""
    return Candidate(
        text=text,
        source=source,
        source_type=source_type,
        context=context,
        confidence=confidence,
        topic=topic,
        scope=scope,
        tier=tier,
    )
