"""
Step 0: connect to Weaviate on whichever tier you are on.

One environment variable, WEAVIATE_MODE, picks the tier:

    docker    local container (tier 1, primary)
    embedded  in-process Weaviate, Mac and Linux only (tier 2)
    cloud     shared Weaviate Cloud sandbox, per-attendee collections (tier 3)

Everything above this module is identical on all three tiers.

Weaviate-specific: all of it. This is the one module you would rewrite for
another vector database, and it is about forty lines.
"""

import os
import platform
import re
from pathlib import Path

import weaviate
from dotenv import load_dotenv
from weaviate.classes.init import Auth


WEAVIATE_VERSION = "1.32.9"
REPO_ROOT = Path(__file__).resolve().parent.parent
BASE_COLLECTION = "MemoryRecord"

load_dotenv(REPO_ROOT / ".env")


def mode() -> str:
    """The tier named in .env. Defaults to docker."""
    return os.getenv("WEAVIATE_MODE", "docker").strip().lower() or "docker"


def handle() -> str:
    """ATTENDEE_HANDLE, cleaned into something Weaviate accepts as a name prefix."""
    raw = os.getenv("ATTENDEE_HANDLE", "")
    clean = re.sub(r"[^A-Za-z0-9]", "", raw)
    if clean and not clean[0].isalpha():
        clean = "A" + clean
    return clean[:1].upper() + clean[1:] if clean else ""


def collection_name(base: str = BASE_COLLECTION) -> str:
    """
    Your collection's name. On the cloud tier the shared cluster needs one
    collection per attendee, so the handle is required there and becomes a
    prefix: ATTENDEE_HANDLE=ada gives Ada_MemoryRecord.
    """
    h = handle()
    if mode() == "cloud" and not h:
        raise RuntimeError(
            "WEAVIATE_MODE=cloud needs ATTENDEE_HANDLE set in .env, so your collection "
            "does not collide with the person next to you."
        )
    return f"{h}_{base}" if h else base


def connect() -> weaviate.WeaviateClient:
    """Return a connected client for the configured tier, or a clear error naming the next tier."""
    m = mode()

    if m == "docker":
        try:
            return weaviate.connect_to_local(
                host=os.getenv("WEAVIATE_HOST", "localhost"),
                port=int(os.getenv("WEAVIATE_PORT", "8080")),
                grpc_port=int(os.getenv("WEAVIATE_GRPC_PORT", "50051")),
            )
        except Exception as exc:
            raise ConnectionError(
                "Could not reach the Weaviate container. Is it running? Try `docker compose up -d`. "
                "If Docker will not start, set WEAVIATE_MODE=embedded (Mac/Linux) or "
                "WEAVIATE_MODE=cloud in .env and restart the kernel."
            ) from exc

    if m == "embedded":
        if platform.system() == "Windows":
            raise RuntimeError(
                "Weaviate Embedded does not run on Windows. Set WEAVIATE_MODE=cloud in .env."
            )
        return weaviate.connect_to_embedded(
            version=WEAVIATE_VERSION,
            persistence_data_path=str(REPO_ROOT / ".weaviate-embedded"),
            port=int(os.getenv("WEAVIATE_EMBEDDED_PORT", "8079")),
            grpc_port=int(os.getenv("WEAVIATE_EMBEDDED_GRPC_PORT", "50050")),
        )

    if m == "cloud":
        url = os.getenv("WEAVIATE_CLOUD_URL", "").strip()
        key = os.getenv("WEAVIATE_CLOUD_KEY", "").strip()
        if not url or not key:
            raise RuntimeError(
                "WEAVIATE_MODE=cloud needs WEAVIATE_CLOUD_URL and WEAVIATE_CLOUD_KEY in .env. "
                "Scott hands these out in the room."
            )
        collection_name()  # fail early if the handle is missing
        return weaviate.connect_to_weaviate_cloud(
            cluster_url=url, auth_credentials=Auth.api_key(key)
        )

    raise ValueError(f"WEAVIATE_MODE={m!r} is not one of docker, embedded, cloud.")


def describe_tier() -> str:
    """One line for the top of every notebook."""
    labels = {
        "docker": "tier 1, local Docker container",
        "embedded": "tier 2, Weaviate Embedded (in-process)",
        "cloud": "tier 3, Weaviate Cloud sandbox",
    }
    name = collection_name() if mode() != "cloud" or handle() else "(handle not set)"
    return f"WEAVIATE_MODE={mode()} ({labels.get(mode(), 'unknown')}), collection {name}"
