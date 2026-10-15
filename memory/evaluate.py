"""
Evaluation: numbers instead of opinions.

Runs the labeled candidates in data/labeled_candidates.json through a gate
and through the lifecycle, in a scratch collection, and reports:

    gate catch rate         share of should-deny candidates the gate denied
    false deny rate         share of should-allow candidates the gate denied
    poisoning resistance    catch rate on the adversarial subset only
    promotion precision     of the records promoted to team or org, how many should have been
    promotion recall        of the records that should have been promoted, how many were

Each label is a judgment call made while writing the data, and the notebook
says so. Treat the numbers as a regression test for your gate, not as truth.

Weaviate-specific: the scratch collection. Portable: the metrics.
"""

import json
from datetime import datetime, timedelta

import pandas as pd
from weaviate import WeaviateClient
from weaviate.collections import Collection

from memory.capture import Candidate
from memory.connect import REPO_ROOT, collection_name
from memory.embed import embed_one
from memory.gate import Gate
from memory.lifecycle import corroborate, endorse, promote
from memory.schema import ensure_collection, now_utc
from memory.score import score_candidate


LABELED_PATH = REPO_ROOT / "data" / "labeled_candidates.json"


def load_labeled() -> list[dict]:
    with open(LABELED_PATH) as f:
        return json.load(f)


def eval_collection(client: WeaviateClient, seed_fn, reset: bool = True) -> Collection:
    """A scratch collection seeded like the real one, so evaluation never touches your store."""
    coll = ensure_collection(client, name=collection_name("MemoryEval"), reset=reset)
    seed_fn(coll)
    return coll


def run_gate_eval(
    collection: Collection, gate: Gate, labeled: list[dict] | None = None
) -> pd.DataFrame:
    """Check (do not admit) every labeled candidate. One row each."""
    rows = []
    for item in labeled or load_labeled():
        cand = Candidate.from_dict(item)
        scores = score_candidate(collection, cand, vector=embed_one(cand.text))
        decision = gate.check(cand, scores)
        rows.append(
            {
                "id": item["id"],
                "kind": item["kind"],
                "attack_class": item.get("attack_class", ""),
                "expected": item["expected_gate"],
                "actual": "allow" if decision.allowed else "deny",
                "policy": decision.policy,
                "reason": decision.reason,
                "text": cand.text,
            }
        )
    return pd.DataFrame(rows)


def gate_metrics(df: pd.DataFrame) -> dict:
    should_deny = df[df.expected == "deny"]
    should_allow = df[df.expected == "allow"]
    adversarial = df[df.kind == "adversarial"]
    bad = df[df.kind == "bad"]

    def rate(sub: pd.DataFrame, value: str) -> float:
        return round(float((sub.actual == value).mean()), 3) if len(sub) else float("nan")

    return {
        "candidates": len(df),
        "gate_catch_rate": rate(should_deny, "deny"),
        "false_deny_rate": rate(should_allow, "deny"),
        "poisoning_resistance": rate(adversarial, "deny"),
        "bad_but_not_adversarial_catch_rate": rate(bad, "deny"),
        "accuracy": round(float((df.actual == df.expected).mean()), 3),
    }


def run_promotion_eval(
    collection: Collection, labeled: list[dict] | None = None, now: datetime | None = None
) -> pd.DataFrame:
    """
    For every candidate labeled allow: write it, apply the corroborations and
    endorsement the label describes, run promotion twice (session->team->org),
    and compare the tier it reached with the tier the label expected.
    """
    now = now or now_utc()
    rows = []
    for item in labeled or load_labeled():
        if item["expected_gate"] != "allow":
            continue
        cand = Candidate.from_dict(item)
        uuid = str(
            collection.data.insert(
                properties=cand.to_properties(now=now), vector=embed_one(cand.text)
            )
        )
        for src in item.get("corroborations", []):
            corroborate(collection, uuid, src, now=now)
        if item.get("endorsed_by"):
            endorse(collection, uuid, item["endorsed_by"], now=now)
        later = now + timedelta(days=1)
        promote(collection, uuid, now=later)
        tier, reason = promote(collection, uuid, now=later + timedelta(days=1))
        obj = collection.query.fetch_object_by_id(uuid)
        reached = obj.properties["tier"]
        rows.append(
            {
                "id": item["id"],
                "expected_tier": item.get("expected_tier", "session"),
                "reached_tier": reached,
                "corroborations": len(item.get("corroborations", [])) + 1,
                "endorsed": bool(item.get("endorsed_by")),
                "last_reason": reason,
                "text": cand.text,
            }
        )
    return pd.DataFrame(rows)


def promotion_metrics(df: pd.DataFrame) -> dict:
    """Positive = promoted above session."""
    expected = df.expected_tier != "session"
    reached = df.reached_tier != "session"
    tp = int((expected & reached).sum())
    fp = int((~expected & reached).sum())
    fn = int((expected & ~reached).sum())
    precision = tp / (tp + fp) if tp + fp else float("nan")
    recall = tp / (tp + fn) if tp + fn else float("nan")
    return {
        "records": len(df),
        "promotion_precision": round(precision, 3),
        "promotion_recall": round(recall, 3),
        "exact_tier_accuracy": round(float((df.expected_tier == df.reached_tier).mean()), 3),
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
    }
