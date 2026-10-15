# From Retrieval to Recall: Building Governed Agentic Memory on Vector Databases

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Weaviate](https://img.shields.io/badge/weaviate-1.32-green.svg)
![No API keys](https://img.shields.io/badge/API%20keys-none%20required-brightgreen.svg)

> Build the write path for agent memory: **Capture** candidates with provenance, **Score** them for novelty and contradiction, **Gate** them with a deterministic policy, **Promote** them through tiers, and **Decay** them on a schedule. Then try to poison your own memory store and watch the gate catch it.

ODSC AI West 2026, Burlingame CA. Two-hour hands-on workshop. The framing is in the companion blog post, [Your Agent's Memory Is an Attack Surface](https://opendatascience.com/governed-agentic-memory-five-step-pattern/), so the room gets the short version and we spend the time building.

## The story first

Retrieval-augmented generation taught us how to read from a vector database. A human curated the corpus, a pipeline embedded it, and the model read from it. The hard problems were on the read path: chunking, hybrid search, reranking.

Agent memory moves the hard problems to the write path. The agent is now the curator. It writes what it observed, at speed, with no reviewer in the loop. If it stores something wrong, it stores it confidently and retrieves it for weeks as if it were fact. And if someone can influence what the agent observes, they can influence what it believes. OWASP now lists memory poisoning as ASI06 in its Top 10 for agentic applications, and the published attacks against ungoverned stores succeed most of the time.

Much of the RAG playbook still applies. What is missing is a review step, and that is what we build: a governance layer that sits between an agent and its memory store.

If you are new to vector databases, no worries. The store is handed to you working and the part you build is plain Python. If you have built RAG before, you already have half of this. If you run agents in production, you know the failure modes better than I do, and I would like to hear about them in the room.

## What you will build

Every notebook uses the same five words, in the same order: **Capture, Score, Gate, Promote, Decay**.

### Part 1: Why Memory Is Not RAG (0:00 to 0:10)
Talk, no laptop needed yet. What changes when the system writes its own corpus, where memory systems fail in production, and the 2026 landscape in one slide.

### Part 2: The Retrieval Substrate (0:10 to 0:30) [notebook 0](notebooks/0-setup.ipynb)
- Confirm your environment and find out which of the three tiers you are on
- A memory-oriented schema: provenance, confidence, tier, corroboration count, review date
- Seed the store with a small fictional company handbook and run hybrid search over it
- **Why it matters**: governance needs metadata that a plain RAG schema does not carry

### Part 3: Building the Write Path (0:30 to 1:15, protected)
The core of the workshop and the part you implement.

**[Notebook 1, Capture and Score](notebooks/1-capture-and-score.ipynb)** (scaffolded, small TODOs)
- Capture a candidate memory with full provenance: who, when, in what context, with what confidence
- Score it for novelty against the store, for utility, and for contradiction with what is already there
- **Why it matters**: a candidate memory is a proposal, not a fact

**[Notebook 2, Gate](notebooks/2-gate.ipynb)** (you build this one)
- A deterministic, fail-closed policy gate in front of the store: a list of plain Python policies, any one of which can deny
- **The poisoning exercise**: inject false policies, smuggled instructions, and leaked credentials into your own store and watch the gate reject them with a logged reason
- A stretch cell: extend the gate to catch an attack class we did not discuss in the room
- **Why it matters**: a policy in a system prompt can be argued with. A gate cannot.

**[Notebook 3, Promote and Decay](notebooks/3-promote-and-decay.ipynb)** (prebuilt, walked through together)
- Promotion from session to team to organization, on corroboration from distinct sources
- The top tier requires explicit human endorsement, an intentional endorsement gate by design
- Decay through lifespans, review triggers, and usage-based aging, with a simulated clock so you can watch a year go by
- **Why it matters**: a memory nobody re-examines drifts out of true, so aging is a feature

### Part 4: Evaluating and Governing Memory (1:15 to 1:40) [notebook 4](notebooks/4-evaluation.ipynb)
- Promotion precision and recall against a small labeled set of candidates
- Gate catch rate on known-bad candidates, and poisoning resistance on adversarial ones
- Each metric defined in the notebook, with how the labels were made and what they do not tell you
- **Why it matters**: without labels you have opinions about your memory system, not measurements

The remaining 20 minutes are a buffer for setup trouble, recap, and questions.

## Prebuilt, scaffolded, or yours

Two hours is not long. The repo hands you the parts that teach little and protects your time for the parts that teach a lot.

| Component | Who builds it |
|---|---|
| Weaviate (any tier), schema, seed corpus, embeddings | Prebuilt. Handed to you working. |
| Capture and Score | Scaffolded. Working code with a few small TODO cells you complete. |
| The Gate | **You build most of it.** This is the centerpiece. |
| Promote and Decay | Prebuilt. Read-through, narrated together. |
| Evaluation | Prebuilt. Run together. |

If you fall behind, every notebook has a cell that loads the reference implementation from `memory/reference.py`, so the next notebook always works.

## Quick start

### Prerequisites
- Python 3.11 or newer
- Docker Desktop ([download](https://docs.docker.com/get-started/get-docker/)). If you cannot run Docker, see the fallback tiers below. You can still do everything.
- A code editor with Jupyter support. [VS Code](https://code.visualstudio.com/) or [Cursor](https://www.cursor.com/) work well, and plain JupyterLab is fine.
- No API keys. Embeddings run locally.

> **Please do the setup at home.** It downloads a few hundred MB (the Weaviate image, PyTorch, and a small embedding model). Conference Wi-Fi will not carry a room full of people doing this at once.

### Setup

**1. Clone the repository**
```bash
git clone https://github.com/saskinosie/governed-agentic-memory-workshop.git
cd governed-agentic-memory-workshop
```

**2. Create an environment and run the setup script**
```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
python setup.py
```

The script pulls the Weaviate image, installs dependencies, pre-downloads the embedding model and the Embedded Weaviate binary, and tells you which tiers are ready on your machine.

**3. Configure**
```bash
cp .env.example .env
```

The defaults are right for Docker. Set `ATTENDEE_HANDLE` to a short name (letters and digits) so your output is labeled.

**4. Start Weaviate**
```bash
docker compose up -d
```

**5. Verify**

Open [notebooks/0-setup.ipynb](notebooks/0-setup.ipynb) and run it. The last cell prints your tier and a green check.

### Fallback tiers

Setup fails for somebody in every room. Three tiers, one variable (`WEAVIATE_MODE` in `.env`), identical code and identical notebooks on each.

| Tier | `WEAVIATE_MODE` | What it is | When to use it |
|---|---|---|---|
| 1 | `docker` | Local container from `docker-compose.yml` | Primary. Use it if Docker runs. |
| 2 | `embedded` | Weaviate Embedded, in-process, no Docker. Mac and Linux only. | Docker will not start. |
| 3 | `cloud` | A shared Weaviate Cloud sandbox with one collection per attendee, prefixed with your handle. A classroom convenience, not tenant isolation: everyone holds the same sandbox key. | Windows, or nothing local works. Credentials given out in the room. |

Notebook 0 walks all three and reports which one you landed on. If ingestion is slow or the embedding model will not load, the workshop texts ship pre-embedded in `data/vector_cache.json`, so seeding takes seconds on any tier and the model is only needed for text you type yourself.

## How it fits together

```
Agent observes something
 |
[Capture] ....... candidate memory + provenance (who, when, context, confidence)
 |
[Score] ......... novelty vs. the store | utility | contradiction check
 |
[Gate] .......... deterministic policies, fail closed
 |                        |
 accept               reject, logged with a reason, never silently dropped
 |
[Promote] ....... session -> team -> org, on corroboration + human endorsement
 |
[Decay] ......... lifespan, review trigger, usage-based aging
 |
Weaviate (vectors + metadata)
 ^
Agent reads (hybrid search, tier-filtered)
```

## This pattern is not Weaviate-specific

Weaviate is the teaching substrate. I picked it because hybrid search helps with contradiction detection, because the container is easy to run locally, and because Embedded gives a second tier with no Docker. The governance layer sits **above** the database and reads it through a narrow interface: similarity search, metadata filters, writes, and updates.

Every notebook ends with a short transferability cell that says what was Weaviate-specific and what was portable. The same pattern runs on Qdrant, Milvus, pgvector, or anything else with vector search and metadata filters. If you came to learn Weaviate you will learn some. If you came to learn governed memory, the vendor is an implementation detail.

## Project structure

```
notebooks/
  0-setup.ipynb                # Tier check, schema, seed, hybrid search
  1-capture-and-score.ipynb    # Provenance, novelty, utility, contradiction (TODOs)
  2-gate.ipynb                 # Fail-closed policy gate + poisoning exercise (you build)
  3-promote-and-decay.ipynb    # Tiers, endorsement, aging (prebuilt)
  4-evaluation.ipynb           # Memory metrics on labeled data (prebuilt)
memory/                        # The governance layer as small importable modules
  connect.py                   # One function, three tiers
  schema.py                    # The MemoryRecord collection
  embed.py                     # Local embeddings, cache first
  capture.py                   # Candidate memories with provenance
  score.py                     # Novelty, utility, contradiction
  gate.py                      # Gate, Policy, Decision. Fail closed.
  lifecycle.py                 # Promote and Decay
  evaluate.py                  # Metrics on labeled candidates
  reference.py                 # Finished versions of the attendee parts
data/
  seed_corpus.json             # Brightwater Supply Co. handbook, about 50 facts
  attacks.json                 # Adversarial candidates for the poisoning exercise
  labeled_candidates.json      # Good / bad / adversarial, labeled, for notebook 4
  vector_cache.json            # Pre-embedded workshop texts
setup.py                       # Run at home before the workshop
docker-compose.yml             # Tier 1
.env.example                   # Tier switch and handle
```

## Key technologies

- **[Weaviate](https://weaviate.io/)**, open-source vector database with native hybrid search. Docker, Embedded, or Cloud.
- **[sentence-transformers](https://www.sbert.net/)**, local embeddings (`all-MiniLM-L6-v2`, 384 dimensions, about 90 MB). No account, no key.
- **Docker**, a local, reproducible substrate so nothing depends on a hosted account.
- Plain Python for the governance layer. No agent framework, on purpose. The pattern should be readable in one sitting.

## What you will take home

- Why the write path, not the read path, is where memory systems tend to fail
- How to make a memory candidate carry enough provenance to be judged
- How a deterministic gate differs from an instruction in a system prompt
- Why promotion tiers need corroboration from distinct sources and human endorsement, not a confidence score alone
- How to measure a memory system instead of trusting it

## Contributing

Found a bug or have an improvement? Open an issue or a pull request. Keep the five step names as they are; they match the published blog.

## License

MIT. See [LICENSE](LICENSE).

## About the presenter

Scott Askinosie, Ph.D., is Principal AI Architect, Knowledge & Memory Systems at SteelEngine, where he works on the memory and governance layers under enterprise agents. His current question is a practical one: how do we govern AI systems that act on their own, and remember what they did?

Scott came to AI engineering by way of science. He holds a Ph.D. in Quantitative Biology and spent his early career as a research scientist before moving into data science and applied AI. That training still shapes the work: measure it, reproduce it, and ask whether the system actually does what we claim.

## Resources and further reading

- [Weaviate documentation](https://weaviate.io/developers/weaviate) and [hybrid search](https://weaviate.io/developers/weaviate/search/hybrid)
- [OWASP Top 10 for Agentic Applications](https://genai.owasp.org/), ASI06 Memory Poisoning
- [AgentPoison](https://arxiv.org/abs/2407.12784) (NeurIPS 2024) and [MINJA](https://arxiv.org/abs/2503.03704), published attacks on agent memory
- [Your Agent's Memory Is an Attack Surface](https://opendatascience.com/governed-agentic-memory-five-step-pattern/), the companion post

---

**See you in Burlingame!**
