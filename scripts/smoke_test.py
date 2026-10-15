"""
End-to-end check of the governance layer on whatever tier .env names.

    python scripts/smoke_test.py

Seeds a scratch collection, scores and gates every attack with the reference
gate, runs promotion and decay on a simulated clock, and prints the
evaluation metrics. Exits non-zero if any attack gets through.
"""

import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memory import Candidate, connect, describe_tier, ensure_collection, score_candidate  # noqa: E402
from memory.connect import collection_name  # noqa: E402
from memory.evaluate import gate_metrics, promotion_metrics, run_gate_eval, run_promotion_eval  # noqa: E402
from memory.lifecycle import corroborate, decay, endorse, promote  # noqa: E402
from memory.reference import reference_gate  # noqa: E402
from memory.retrieve import recall, show  # noqa: E402
from memory.schema import now_utc  # noqa: E402
from memory.seed import load_attacks, seed_store  # noqa: E402


def main() -> int:
    print(describe_tier())
    client = connect()
    try:
        coll = ensure_collection(client, name=collection_name("MemorySmoke"), reset=True)
        n = seed_store(coll)
        print(f"seeded {n} records")

        print("\nrecall: 'Who approves refunds over $500?'")
        show(recall(coll, "Who approves refunds over $500?", limit=3))

        gate = reference_gate(stretch=True)
        leaked = 0
        print("\nattacks through the reference gate (with stretch policies):")
        for item in load_attacks():
            cand = Candidate.from_dict(item)
            decision = gate.admit(coll, cand, score_candidate(coll, cand))
            print(" ", decision)
            leaked += decision.allowed
        print(" ", gate.summary())

        now = now_utc()
        good = Candidate(
            text="Northgate Logistics asked for a 24 hour heads-up before freight deliveries.",
            source="agent:harbor",
            source_type="agent",
            context="support-session-9001",
            confidence=0.85,
            topic="customer",
            scope="customer:northgate-logistics",
        )
        d = gate.admit(coll, good, score_candidate(coll, good), now=now)
        print("\ngood candidate:", d)
        uid = d.record_uuid
        print(" promote (1 source):", promote(coll, uid, now=now))
        corroborate(coll, uid, "user:ben.oyelaran", now=now)
        print(" promote (2 sources):", promote(coll, uid, now=now + timedelta(days=1)))
        corroborate(coll, uid, "user:carla.mendes", now=now)
        print(" promote (3, no endorsement):", promote(coll, uid, now=now + timedelta(days=2)))
        endorse(coll, uid, "user:aisha.karim", now=now)
        print(" promote (endorsed):", promote(coll, uid, now=now + timedelta(days=3)))
        actions = decay(coll, now=now + timedelta(days=200))
        from collections import Counter

        print(" decay at +200 days:", Counter(a["action"] for a in actions))

        print("\nevaluation on labeled candidates:")
        ev = ensure_collection(client, name=collection_name("MemoryEval"), reset=True)
        seed_store(ev)
        df = run_gate_eval(ev, reference_gate(stretch=True))
        print(" ", gate_metrics(df))
        misses = df[df.actual != df.expected]
        if len(misses):
            print(misses[["id", "expected", "actual", "policy", "text"]].to_string())
        df_base = run_gate_eval(ev, reference_gate(stretch=False))
        print("  without stretch:", gate_metrics(df_base))
        pdf = run_promotion_eval(ev)
        print(" ", promotion_metrics(pdf))
        pm = pdf[pdf.expected_tier != pdf.reached_tier]
        if len(pm):
            print(pm[["id", "expected_tier", "reached_tier", "last_reason"]].to_string())
        client.collections.delete(collection_name("MemorySmoke"))
        client.collections.delete(collection_name("MemoryEval"))
        return 1 if leaked or len(misses) or len(pm) else 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
