"""
Step 2: Score.

Three numbers for every candidate, all between 0 and 1:

    novelty        how different is this from what the store already holds
    utility        is it specific enough to be worth remembering
    contradiction  does it disagree with something already stored

Scoring never decides anything. It describes the candidate so the Gate can.

The contradiction check here is a deliberately simple heuristic: close
neighbor, same topic, and either a flipped negation or a changed number. In
production you would put an NLI model or an LLM judge behind the same
function signature. The point of the workshop is where the check sits, not
how clever it is.

Weaviate-specific: nearest_records (a near_vector query with a status filter).
Portable: everything else.
"""

import re
from dataclasses import dataclass, field

from weaviate.classes.query import Filter, MetadataQuery
from weaviate.collections import Collection

from memory.capture import Candidate
from memory.embed import embed_one


DUPLICATE_SIMILARITY = 0.92  # at or above this, the candidate is the same memory, not a new one
RELATED_SIMILARITY = 0.55  # below this, two texts are not about the same thing

NEGATIONS = {
    "no",
    "not",
    "never",
    "without",
    "none",
    "cannot",
    "longer",
    "don't",
    "doesn't",
    "isn't",
    "aren't",
}
HEDGES = {"maybe", "probably", "think", "might", "possibly", "seems", "guess", "perhaps", "unsure"}
STOPWORDS = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "were",
    "be",
    "to",
    "of",
    "and",
    "or",
    "in",
    "on",
    "for",
    "by",
    "with",
    "at",
    "from",
    "that",
    "this",
    "it",
    "as",
    "any",
    "all",
    "our",
    "we",
    "you",
    "your",
}


@dataclass
class Neighbor:
    uuid: str
    text: str
    similarity: float
    tier: str
    topic: str
    source: str
    properties: dict = field(default_factory=dict)


@dataclass
class Scores:
    novelty: float
    utility: float
    contradiction: float
    nearest: list[Neighbor] = field(default_factory=list)
    contradicts: Neighbor | None = None
    duplicate_of: Neighbor | None = None

    def summary(self) -> str:
        line = f"novelty={self.novelty:.2f} utility={self.utility:.2f} contradiction={self.contradiction:.2f}"
        if self.duplicate_of:
            line += f" | duplicate of: {self.duplicate_of.text[:50]!r}"
        if self.contradicts:
            line += f" | contradicts [{self.contradicts.tier}]: {self.contradicts.text[:50]!r}"
        return line


def nearest_records(
    collection: Collection, vector: list[float], k: int = 5, active_only: bool = True
) -> list[Neighbor]:
    """The k closest active records, with cosine similarity. Weaviate reports distance = 1 - cosine."""
    filters = Filter.by_property("status").equal("active") if active_only else None
    result = collection.query.near_vector(
        near_vector=vector,
        limit=k,
        filters=filters,
        return_metadata=MetadataQuery(distance=True),
    )
    out = []
    for o in result.objects:
        p = o.properties
        out.append(
            Neighbor(
                uuid=str(o.uuid),
                text=p.get("text", ""),
                similarity=round(1.0 - float(o.metadata.distance), 4),
                tier=p.get("tier", ""),
                topic=p.get("topic", ""),
                source=p.get("source", ""),
                properties=p,
            )
        )
    return out


def novelty_score(neighbors: list[Neighbor]) -> float:
    """1.0 when nothing similar exists, 0.0 when an identical record is already stored."""
    if not neighbors:
        return 1.0
    return round(max(0.0, 1.0 - max(n.similarity for n in neighbors)), 4)


def content_tokens(text: str) -> set[str]:
    """Lowercase word-ish tokens minus stopwords. Trailing periods are dropped so 'approval.' is 'approval'."""
    tokens = (t.rstrip(".") for t in re.findall(r"[a-z0-9$%.]+", text.lower()))
    return {t for t in tokens if t not in STOPWORDS and len(t) > 1}


def numbers_in(text: str) -> set[str]:
    """Numbers as they appear, so $500 and $5,000 do not collide. Commas are dropped."""
    return {n.replace(",", "") for n in re.findall(r"\$?\d[\d,]*(?:\.\d+)?%?", text)}


def utility_score(candidate: Candidate) -> float:
    """
    Is this worth remembering? Specific, confident, right-sized facts score high.
    Vague, hedged, or tiny fragments score low. This is a heuristic, and an
    honest one: it rewards the shape of a useful fact, not its truth.
    """
    text = candidate.text.strip()
    tokens = content_tokens(text)
    score = 0.3
    if 6 <= len(tokens) <= 40:
        score += 0.3  # long enough to mean something, short enough to be one fact
    if numbers_in(text) or re.search(r"\b[A-Z][a-z]+(?: [A-Z][a-z]+)+\b", text):
        score += 0.2  # names a number or a proper noun: it is about something in particular
    if tokens & HEDGES:
        score -= 0.2  # "I think maybe" is not a fact yet
    score += 0.2 * float(candidate.confidence)
    return round(min(1.0, max(0.0, score)), 4)


def contradiction_score(
    candidate: Candidate, neighbors: list[Neighbor]
) -> tuple[float, Neighbor | None]:
    """
    Does the candidate disagree with a stored record? Looks at neighbors that are
    about the same thing (similar, same topic) and asks two cheap questions:
    did a negation appear or disappear, and did a number change. Returns the
    strongest conflict found and the record it conflicts with.
    """
    cand_tokens = content_tokens(candidate.text)
    cand_neg = bool(cand_tokens & NEGATIONS)
    cand_nums = numbers_in(candidate.text)
    best, best_neighbor = 0.0, None
    for n in neighbors:
        if n.similarity < RELATED_SIMILARITY or n.similarity >= DUPLICATE_SIMILARITY:
            continue
        if n.topic and candidate.topic and n.topic != candidate.topic:
            continue
        other_tokens = content_tokens(n.text)
        overlap = len(cand_tokens & other_tokens) / max(1, len(cand_tokens | other_tokens))
        flipped_negation = cand_neg != bool(other_tokens & NEGATIONS)
        other_nums = numbers_in(n.text)
        changed_number = bool(cand_nums and other_nums and cand_nums != other_nums)
        if (flipped_negation or changed_number) and overlap >= 0.2:
            strength = round(n.similarity, 4)
            if strength > best:
                best, best_neighbor = strength, n
    return best, best_neighbor


def score_candidate(
    collection: Collection, candidate: Candidate, vector: list[float] | None = None, k: int = 5
) -> Scores:
    """Run all three scores against the live store."""
    if not candidate.text or not candidate.text.strip():
        # Nothing to compare. No neighbors, so nothing is similar and nothing is contradicted,
        # and the embedding model is not needed (an empty text is never in the vector cache).
        return Scores(novelty=1.0, utility=utility_score(candidate), contradiction=0.0)
    vector = vector or embed_one(candidate.text)
    neighbors = nearest_records(collection, vector, k=k)
    contradiction, conflicts_with = contradiction_score(candidate, neighbors)
    duplicate = next((n for n in neighbors if n.similarity >= DUPLICATE_SIMILARITY), None)
    return Scores(
        novelty=novelty_score(neighbors),
        utility=utility_score(candidate),
        contradiction=contradiction,
        nearest=neighbors,
        contradicts=conflicts_with,
        duplicate_of=duplicate,
    )
