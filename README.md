# From Retrieval to Recall: Building Governed Agentic Memory on Vector Databases

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Weaviate](https://img.shields.io/badge/weaviate-1.32-green.svg)

> Build the write path for agent memory: capture candidates with provenance, score them for novelty and contradiction, gate them with a deterministic policy, promote them through tiers, and decay them on a schedule.

## Overview

Retrieval-augmented generation reads. Memory writes. That difference changes almost everything about the machinery you need.

A RAG corpus is curated by humans before the system ever runs. An agent's memory is written by the agent itself, at speed, from whatever it happened to observe. Nobody reviews it first. So the interesting failure modes move from the read path to the write path: an agent stores something wrong, stores it confidently, and then retrieves it for weeks as if it were fact. Worse, an attacker who can influence what the agent observes can influence what the agent believes.

This workshop builds the governance layer that sits between an agent and its memory store. You will implement a fail-closed policy gate, then try to poison your own memory store and watch the gate catch it.

## What You'll Learn

The workshop runs on a five-step vocabulary. Every notebook uses the same five words: **Capture, Score, Gate, Promote, Decay**.

### Part 1: Why Memory Is Not RAG
**Framing** (0:00 to 0:10): What changes when the system writes its own corpus
- Read-path assumptions that do not carry over to the write path
- Where memory systems actually fail in production
- **Key insight**: The curator moved from a human to the agent, and no one replaced the review step

### Part 2: The Retrieval Substrate ([0-setup.ipynb](notebooks/0-setup.ipynb))
**Foundation** (0:10 to 0:30): The store, and the metadata that makes governance possible
- Connect to a local Weaviate instance and confirm your environment
- Memory-oriented schemas: provenance, confidence, tier, corroboration count, review date
- Hybrid search over memory records, and why sparse matching matters for contradiction detection
- **Key insight**: Governance needs metadata that a plain RAG schema does not carry

### Part 3: Building the Write Path
**Hands-on build** (0:30 to 1:15): The core of the workshop, and the part you implement

**[1-capture-and-score.ipynb](notebooks/1-capture-and-score.ipynb)**
- Capture candidate memories with full provenance: who, when, in what context, with what confidence
- Score for novelty against what is already stored, for utility, and for contradiction
- **Key insight**: A candidate memory is a proposal, not a fact

**[2-gate.ipynb](notebooks/2-gate.ipynb)**
- Build a deterministic, fail-closed policy gate in front of the store
- **The poisoning exercise**: attempt to inject false memories into your own store and watch the gate reject them
- **Key insight**: Policy as a gate behaves differently from policy as a prompt, because a gate cannot be talked out of its decision

**[3-promote-and-decay.ipynb](notebooks/3-promote-and-decay.ipynb)**
- Tiered promotion from session to team to organization, with corroboration counts
- Explicit human endorsement as a requirement for the top tier
- Decay through lifespans, review triggers, and usage-based aging
- **Key insight**: Memories that are never re-examined drift out of true, so aging is a feature

### Part 4: Evaluating and Governing Memory ([4-evaluation.ipynb](notebooks/4-evaluation.ipynb))
**Measurement** (1:15 to 1:40): Knowing whether the governance layer actually works
- Promotion precision and recall, measured against a small labeled set of candidate memories
- Gate catch rate on a held-out set of known-bad candidates
- Poisoning resistance, measured as the share of adversarial candidates the gate rejects
- Each metric is defined in the notebook, alongside how the labeled data was built and what it does not tell you
- **Key insight**: Without labels you have opinions about your memory system, not measurements

The remaining 20 minutes are reserved for setup issues, troubleshooting, recap, and questions.

## What Is Prebuilt and What You Build

Two hours is not long, so the repo hands you the parts that teach little and protects your time for the parts that teach a lot.

| Component | Who builds it |
|---|---|
| Weaviate container, schema, seed corpus | Prebuilt. Handed to you working. |
| Capture and scoring functions | Scaffolded with TODO cells you complete |
| The policy gate | You build most of it. This is the centerpiece. |
| Promotion and decay | Mostly prebuilt, walked through together |
| Evaluation harness | Prebuilt, run together |

## This Pattern Is Not Weaviate-Specific

Weaviate is the teaching substrate here, chosen because hybrid search helps with contradiction detection and because the container is easy to run locally. The governance layer sits **above** the vector database and reads it through a narrow interface: similarity search, metadata filtering, and writes.

Every notebook marks what is Weaviate-specific and what is portable. The same pattern runs on Qdrant, Milvus, pgvector, or anything else that can do vector search with metadata filters. If you came here to learn Weaviate, you will learn some. If you came here to learn governed memory, the vendor is an implementation detail.

## Quick Start

### Prerequisites
- Python 3.10+
- Docker Desktop ([download here](https://docs.docker.com/get-started/get-docker/))
- OpenAI API key ([get one here](https://platform.openai.com/api-keys))
- A code editor with Jupyter notebook support. [VS Code](https://code.visualstudio.com/) or [Cursor](https://www.cursor.com/) recommended.

> **Important**: Setup downloads several hundred MB. **Complete all setup at home before the workshop.** Conference Wi-Fi will not reliably carry a room full of people doing this at once.

### Setup

**1. Clone the repository**
```bash
git clone https://github.com/saskinosie/from-retrieval-to-recall.git
cd from-retrieval-to-recall
```

**2. Run the setup script**
```bash
python setup.py
```

This pulls the Weaviate image, installs dependencies, and verifies the result. To do it by hand instead:

```bash
docker pull semitechnologies/weaviate:1.32.9
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**3. Configure credentials**
```bash
cp .env.example .env
# Edit .env and add your OpenAI API key
```

**4. Start Weaviate**
```bash
docker compose up -d
```

Weaviate will be available at `http://localhost:8080`.

**5. Verify**

Open `notebooks/0-setup.ipynb` and run the cells. If the last cell prints a green check, you are ready.

### Fallback Options

If Docker or your model endpoint will not cooperate, you have two ways to keep going. Neither one changes what you learn.

1. **Weaviate Embedded**: runs in-process, no Docker required. Set `USE_EMBEDDED_WEAVIATE=1` in your `.env` and restart the notebook kernel. Notebook 0 detects the flag and takes the embedded path.
2. **Prebaked collection snapshots**: if ingestion fails or is slow, load the snapshot in `data/` and skip straight to the write-path notebooks.

Both fallbacks are checked during setup in notebook 0, so you will know which path you are on before the build block starts.

## Architecture

```
Agent observes something
 ↓
[Capture] ........ candidate memory + provenance (who, when, context, confidence)
 ↓
[Score] .......... novelty vs. existing store | utility | contradiction check
 ↓
[Gate] ........... deterministic policy, fail-closed
 ↓                      ↓
accept              reject → logged with reason, never silently dropped
 ↓
[Promote] ........ session → team → org, gated on corroboration + human endorsement
 ↓
[Decay] .......... lifespan, review trigger, usage-based aging
 ↓
Weaviate (vector + metadata)
 ↑
Agent reads (hybrid search, tier-filtered)
```

## Project Structure

```
├── notebooks/
│   ├── 0-setup.ipynb                  # Environment check, schema, fallback path
│   ├── 1-capture-and-score.ipynb      # Provenance, novelty, contradiction
│   ├── 2-gate.ipynb                   # Fail-closed policy gate + poisoning exercise
│   ├── 3-promote-and-decay.ipynb      # Tiered promotion, endorsement, aging
│   └── 4-evaluation.ipynb             # Memory-specific metrics on labeled data
├── memory/                            # The governance layer as importable modules
├── data/                              # Seed corpus and prebaked snapshots
├── img/                               # Setup screenshots
├── setup.py                           # Pre-download script, run before the workshop
├── docker-compose.yml                 # Local Weaviate instance
├── requirements.txt                   # Python dependencies
├── .env.example                       # Template for credentials
├── pyproject.toml                     # Ruff linter/formatter config
└── README.md                          # You are here!
```

## Key Technologies

- **[Weaviate](https://weaviate.io/)** Open-source vector database with native hybrid search, run locally via Docker
- **[Pydantic AI](https://ai.pydantic.dev/)** Framework for building production-grade AI agents
- **[OpenAI](https://platform.openai.com/)** Embeddings and language model for scoring and agent reasoning
- **Docker** Local, reproducible substrate so nothing depends on a hosted account

## Key Takeaways

- Why the write path, not the read path, is where memory systems fail
- How to make a memory candidate carry enough provenance to be judged
- How a deterministic gate differs from an instruction in a system prompt
- Why promotion tiers need corroboration and human endorsement, not just a confidence score
- How to measure a memory system instead of trusting it

## Contributing

Found a bug? Have an improvement? Contributions are welcome!

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-addition`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-addition`)
5. Open a Pull Request

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## About the Presenter

Scott Askinosie is a Senior Principal AI Engineer at Steel Engine, where he leads the design and deployment of autonomous, agentic AI systems for enterprise clients. His current work centers on a question that is becoming urgent for the field: how do we govern AI systems that act on their own? From observability and tracing to evaluation and guardrails, Scott focuses on the infrastructure that makes agentic AI trustworthy enough to put into production.

Scott came to AI engineering by way of science. He holds a PhD in Quantitative Biology and spent his early career as a research scientist before moving into data science and, eventually, applied AI. That research training still shapes how he works, with an emphasis on measurement, reproducibility, and asking whether a system actually does what we claim it does.

## Resources & Further Reading

- [Weaviate Documentation](https://weaviate.io/developers/weaviate)
- [Weaviate Hybrid Search](https://weaviate.io/developers/weaviate/search/hybrid)
- [Pydantic AI Documentation](https://ai.pydantic.dev/)
- [OWASP Agentic Security Initiative](https://genai.owasp.org/)

---

**See you in San Francisco!**
