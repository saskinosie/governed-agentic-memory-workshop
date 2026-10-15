"""
Pre-download script for the ODSC AI West 2026 workshop.

From Retrieval to Recall: Building Governed Agentic Memory on Vector Databases

Run this at home BEFORE the workshop. Conference Wi-Fi will not reliably
carry a room full of people downloading this at the same time.

Usage:
    python setup.py            # install, pull, pre-download, verify
    python setup.py --verify   # only report what is ready and which tier you are on

No API keys are needed. Everything runs locally.
"""

import os
import platform
import subprocess
import sys
from pathlib import Path


WEAVIATE_VERSION = "1.32.9"
WEAVIATE_IMAGE = f"semitechnologies/weaviate:{WEAVIATE_VERSION}"
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
PYTHON_MIN = (3, 11)


def banner(text: str) -> None:
    print("=" * 60)
    print(text)
    print("=" * 60)


def check_python() -> bool:
    ok = sys.version_info >= PYTHON_MIN
    status = "OK" if ok else "TOO OLD"
    print(f"  Python:          {status} ({platform.python_version()})")
    if not ok:
        print("    The workshop needs Python 3.11 or newer.")
    return ok


def docker_available() -> bool:
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, timeout=20)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def pull_image() -> None:
    banner(f"Step 1: Pull the Weaviate Docker image ({WEAVIATE_IMAGE})")
    if not docker_available():
        print("Docker is not running or not installed.")
        print("  Install Docker Desktop: https://docs.docker.com/get-started/get-docker/")
        print("  Not possible on your machine? That is fine. See 'Fallback tiers' in the")
        print("  README. Tier 2 (Embedded) or tier 3 (Cloud) will carry you.\n")
        return
    try:
        subprocess.run(["docker", "pull", WEAVIATE_IMAGE], check=True)
        print("Docker image pulled.\n")
    except subprocess.CalledProcessError:
        print("Docker pull failed. Check your network and try again later.\n")


def install_dependencies() -> None:
    banner("Step 2: Install Python dependencies")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            check=True,
        )
        print("Python dependencies installed.\n")
    except subprocess.CalledProcessError:
        print("pip install failed. Check the error above.\n")


def predownload_model() -> None:
    banner("Step 3: Pre-download the embedding model (about 90 MB)")
    model_name = os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL)
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(model_name)
        dim = model.get_sentence_embedding_dimension()
        print(f"Model ready: {model_name} ({dim} dimensions).\n")
    except Exception as exc:  # noqa: BLE001
        print(f"Could not load {model_name}: {exc}")
        print("  Not fatal. The workshop texts ship pre-embedded in data/vector_cache.json,")
        print("  so you can still run every notebook. Try again on a better connection.\n")


def predownload_embedded() -> None:
    """Tier 2 needs a Weaviate binary. Fetch it now so it is not a conference download."""
    banner("Step 4: Pre-download Weaviate Embedded (tier 2 fallback, Mac and Linux)")
    if platform.system() == "Windows":
        print("Weaviate Embedded does not run on Windows. Skipping. Your fallback is tier 3.\n")
        return
    try:
        import weaviate

        client = weaviate.connect_to_embedded(
            version=WEAVIATE_VERSION,
            persistence_data_path=str(Path(".weaviate-embedded").resolve()),
            port=8079,
            grpc_port=50050,
        )
        try:
            ready = client.is_ready()
        finally:
            client.close()
        print(f"Embedded Weaviate started and stopped cleanly (ready={ready}).\n")
    except Exception as exc:  # noqa: BLE001
        print(f"Embedded Weaviate could not start: {exc}")
        print("  Not fatal if Docker works for you. Otherwise tier 3 is the floor.\n")


def verify() -> None:
    banner("Verification")
    issues: list[str] = []

    if not check_python():
        issues.append("Python 3.11+ required")

    if docker_available():
        result = subprocess.run(["docker", "image", "inspect", WEAVIATE_IMAGE], capture_output=True)
        if result.returncode == 0:
            print("  Docker + image:  OK (tier 1 available)")
        else:
            issues.append("Weaviate image not pulled yet (tier 1 not ready)")
            print("  Docker + image:  Docker runs, image MISSING")
    else:
        issues.append("Docker not available (tier 1 not ready; tiers 2 and 3 still work)")
        print("  Docker:          NOT AVAILABLE")

    try:
        import weaviate

        print(f"  weaviate-client: OK (v{weaviate.__version__})")
    except ImportError:
        issues.append("weaviate-client not installed")
        print("  weaviate-client: MISSING")

    try:
        import sentence_transformers  # noqa: F401

        print("  sentence-transformers: OK")
    except ImportError:
        issues.append(
            "sentence-transformers not installed (vector cache will cover the workshop texts)"
        )
        print("  sentence-transformers: MISSING")

    if Path("data/vector_cache.json").exists():
        print("  vector cache:    OK")
    else:
        issues.append("data/vector_cache.json missing (re-clone the repo)")
        print("  vector cache:    MISSING")

    if Path(".env").exists():
        from dotenv import load_dotenv

        load_dotenv()
        mode = os.getenv("WEAVIATE_MODE", "docker")
        print(f"  .env file:       OK (WEAVIATE_MODE={mode})")
        if mode == "cloud" and not (
            os.getenv("WEAVIATE_CLOUD_URL") and os.getenv("WEAVIATE_CLOUD_KEY")
        ):
            issues.append(
                "WEAVIATE_MODE=cloud but WEAVIATE_CLOUD_URL or WEAVIATE_CLOUD_KEY is empty"
            )
        if mode == "embedded" and platform.system() == "Windows":
            issues.append("WEAVIATE_MODE=embedded does not work on Windows; use docker or cloud")
    else:
        issues.append(".env file not found (run: cp .env.example .env)")
        print("  .env file:       NOT FOUND")

    print()
    if issues:
        print(f"Things to look at ({len(issues)}):")
        for item in issues:
            print(f"  - {item}")
        print("\nDocker problems are not fatal. See 'Fallback tiers' in the README.")
    else:
        print("All good. Open notebooks/0-setup.ipynb to confirm your tier.")


if __name__ == "__main__":
    print()
    print("ODSC AI West 2026 Workshop Setup")
    print("From Retrieval to Recall:")
    print("Building Governed Agentic Memory on Vector Databases")
    print()

    if "--verify" in sys.argv:
        verify()
        sys.exit(0)

    print("Run this at home before the workshop.\n")
    pull_image()
    install_dependencies()
    predownload_model()
    predownload_embedded()
    verify()
