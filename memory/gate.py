"""
Step 3: Gate.

A gate is a list of policies. Each policy is a plain function that looks at a
candidate and its scores and returns a reason to deny, or None to let it
through. The gate runs every policy, denies if any of them object, and logs
the decision either way. Nothing is ever dropped silently.

Fail closed means: no policies configured, deny. A policy throws, deny. The
gate has no opinion of its own and cannot be argued with, which is the whole
difference between a gate and a sentence in a system prompt.

Portable: all of it. The gate never touches Weaviate directly; admit() hands
the write to memory.lifecycle.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from weaviate.collections import Collection

from memory.capture import Candidate
from memory.schema import now_utc
from memory.score import Scores


Policy = Callable[[Candidate, Scores], str | None]


@dataclass
class Decision:
    allowed: bool
    candidate_id: str
    text: str
    reasons: list[tuple[str, str]] = field(default_factory=list)  # (policy name, reason)
    outcome: str = "checked"  # checked | written | corroborated | denied | error
    record_uuid: str | None = None
    at: datetime = field(default_factory=now_utc)

    @property
    def policy(self) -> str:
        return self.reasons[0][0] if self.reasons else ""

    @property
    def reason(self) -> str:
        return "; ".join(f"{name}: {why}" for name, why in self.reasons)

    def __str__(self) -> str:
        verdict = "ALLOW" if self.allowed else "DENY "
        tail = f" <- {self.reason}" if self.reasons else ""
        return f"{verdict} [{self.outcome}] {self.text[:70]!r}{tail}"


class Gate:
    """Deterministic, fail-closed. Build it by adding policies."""

    def __init__(self, policies: list[tuple[str, Policy]] | None = None):
        self.policies: list[tuple[str, Policy]] = list(policies or [])
        self.log: list[Decision] = []

    def add(self, name: str, fn: Policy) -> "Gate":
        self.policies.append((name, fn))
        return self

    def policy(self, name: str):
        """Decorator form: @gate.policy("no_secrets")"""

        def wrap(fn: Policy) -> Policy:
            self.add(name, fn)
            return fn

        return wrap

    def check(self, candidate: Candidate, scores: Scores) -> Decision:
        """Run every policy. Any objection denies. Errors deny. No policies denies."""
        decision = Decision(allowed=False, candidate_id=candidate.candidate_id, text=candidate.text)
        if not self.policies:
            decision.reasons.append(("gate", "no policies configured, failing closed"))
            return decision
        for name, fn in self.policies:
            try:
                reason = fn(candidate, scores)
            except Exception as exc:  # noqa: BLE001
                decision.reasons.append(
                    (name, f"policy raised {type(exc).__name__}: {exc} (failing closed)")
                )
                continue
            if reason:
                decision.reasons.append((name, str(reason)))
        decision.allowed = not decision.reasons
        return decision

    def admit(
        self,
        collection: Collection,
        candidate: Candidate,
        scores: Scores,
        vector: list[float] | None = None,
        now: datetime | None = None,
    ) -> Decision:
        """Check, then write (or corroborate) if allowed. Always logs. Returns the decision."""
        from memory.lifecycle import (
            write_or_corroborate,
        )  # local import keeps the modules readable on their own

        decision = self.check(candidate, scores)
        if decision.allowed:
            outcome, uuid = write_or_corroborate(
                collection, candidate, scores, vector=vector, now=now
            )
            decision.outcome, decision.record_uuid = outcome, uuid
        else:
            decision.outcome = "denied"
        self.log.append(decision)
        return decision

    def summary(self) -> dict:
        allowed = sum(1 for d in self.log if d.allowed)
        denied = len(self.log) - allowed
        by_policy: dict[str, int] = {}
        for d in self.log:
            for name, _ in d.reasons:
                by_policy[name] = by_policy.get(name, 0) + 1
        return {
            "checked": len(self.log),
            "allowed": allowed,
            "denied": denied,
            "denials_by_policy": by_policy,
        }
