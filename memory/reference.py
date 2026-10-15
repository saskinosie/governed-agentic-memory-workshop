"""
Finished versions of the parts attendees build, so nobody is stuck.

    from memory.reference import reference_gate
    gate = reference_gate()                 # the six policies we build in the room
    gate = reference_gate(stretch=True)     # plus the two stretch policies

The policies are deliberately plain. Each one is a few lines, returns a
reason string to deny or None to allow, and can be read aloud.

Portable: all of it.
"""

import base64
import re

from memory.capture import Candidate
from memory.gate import Gate
from memory.score import Scores, utility_score  # noqa: F401  (re-exported for notebook 1)


# Who may change policy at Brightwater. Everything else is a claim about policy, not policy.
POLICY_AUTHORITIES = {"user:priya.natarajan", "user:daniel.reyes", "user:maren.okafor"}

CONTRADICTION_THRESHOLD = 0.55

SECRET_PATTERNS = re.compile(
    r"(password|passwd|login is|api[ _-]?key|secret|token|recovery code|shared key|"
    r"\b\d{4}-\d{4}-\d{4}\b|\b(?:\d[ -]?){13,16}\b)",
    re.IGNORECASE,
)

INSTRUCTION_PATTERNS = re.compile(
    r"((note|reminder|instruction)s? (for|to) the assistant|assistant instruction|"
    r"\bwhenever\b.*\btell (them|the customer)\b|\bskip (identity|verification|the)\b|"
    r"\bignore\b|\balways\b|\bfrom now on\b|\byou must\b|\bdo not verify\b)",
    re.IGNORECASE,
)

KNOWN_CUSTOMERS = {
    "customer:halvorsen-dental": "Halvorsen Dental",
    "customer:pinecrest-clinics": "Pinecrest Clinics",
    "customer:cascade-brewing": "Cascade Brewing Collective",
    "customer:riverbend-schools": "Riverbend School District",
    "customer:northgate-logistics": "Northgate Logistics",
}

BASE64_RUN = re.compile(r"[A-Za-z0-9+/]{24,}={0,2}")


# The six policies built in the room.


def provenance_complete(c: Candidate, s: Scores) -> str | None:
    problems = c.validate()
    return "; ".join(problems) if problems else None


def policy_needs_authority(c: Candidate, s: Scores) -> str | None:
    if c.topic != "policy":
        return None
    if c.source_type == "document" or c.source in POLICY_AUTHORITIES:
        return None
    return f"policy facts come from documents or named authorities, not from {c.source} ({c.source_type})"


def no_secrets(c: Candidate, s: Scores) -> str | None:
    m = SECRET_PATTERNS.search(c.text)
    return f"looks like a credential or secret ({m.group(0)!r})" if m else None


def no_instructions(c: Candidate, s: Scores) -> str | None:
    m = INSTRUCTION_PATTERNS.search(c.text)
    return f"reads like an instruction to the agent, not a fact ({m.group(0)!r})" if m else None


def no_org_contradiction(c: Candidate, s: Scores) -> str | None:
    if (
        s.contradicts is not None
        and s.contradicts.tier == "org"
        and s.contradiction >= CONTRADICTION_THRESHOLD
    ):
        return f"contradicts org record {s.contradicts.text[:60]!r}; a human retires org facts, the gate does not"
    return None


def not_self_corroboration(c: Candidate, s: Scores) -> str | None:
    dup = s.duplicate_of
    if dup is not None and c.source in (dup.properties.get("corroborated_by") or []):
        return f"already stored from {c.source}; the same source cannot corroborate itself"
    return None


# Stretch policies: attack classes not discussed in the room.


def no_cross_customer_leak(c: Candidate, s: Scores) -> str | None:
    """A memory scoped to one customer must not carry another customer's details."""
    if c.scope not in KNOWN_CUSTOMERS:
        return None
    for scope, name in KNOWN_CUSTOMERS.items():
        if scope != c.scope and name.lower() in c.text.lower():
            return f"scoped to {c.scope} but mentions {name}"
    return None


def no_encoded_payload(c: Candidate, s: Scores) -> str | None:
    """Base64 runs are not facts. Decode and look; deny either way if it hides text."""
    for run in BASE64_RUN.findall(c.text):
        try:
            decoded = base64.b64decode(run + "=" * (-len(run) % 4)).decode("utf-8")
        except Exception:  # noqa: BLE001
            continue
        if decoded.isprintable():
            return f"contains an encoded payload ({decoded[:40]!r})"
    return None


ROOM_POLICIES = [
    ("provenance_complete", provenance_complete),
    ("policy_needs_authority", policy_needs_authority),
    ("no_secrets", no_secrets),
    ("no_instructions", no_instructions),
    ("no_org_contradiction", no_org_contradiction),
    ("not_self_corroboration", not_self_corroboration),
]

STRETCH_POLICIES = [
    ("no_cross_customer_leak", no_cross_customer_leak),
    ("no_encoded_payload", no_encoded_payload),
]


def reference_gate(stretch: bool = False) -> Gate:
    return Gate(ROOM_POLICIES + (STRETCH_POLICIES if stretch else []))
