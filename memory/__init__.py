"""
Governed agentic memory, teaching implementation.

Five steps, in this order, with these names: Capture, Score, Gate, Promote, Decay.

    from memory import connect, ensure_collection, capture, score_candidate, Gate

Everything here is plain Python on top of a narrow slice of Weaviate:
similarity search, metadata filters, inserts, and updates. The governance
pattern sits above the database. See each module's docstring for what is
Weaviate-specific and what is portable.
"""

from memory.capture import Candidate, capture
from memory.connect import collection_name, connect, describe_tier, mode
from memory.embed import embed, embed_one
from memory.gate import Decision, Gate
from memory.lifecycle import corroborate, decay, endorse, promote, promote_all
from memory.retrieve import recall
from memory.schema import ensure_collection, fetch_all, reset_collection
from memory.score import Scores, score_candidate


__version__ = "0.1.0"

__all__ = [
    "Candidate",
    "Decision",
    "Gate",
    "Scores",
    "capture",
    "collection_name",
    "connect",
    "corroborate",
    "decay",
    "describe_tier",
    "embed",
    "embed_one",
    "endorse",
    "ensure_collection",
    "fetch_all",
    "mode",
    "promote",
    "promote_all",
    "recall",
    "reset_collection",
    "score_candidate",
]
