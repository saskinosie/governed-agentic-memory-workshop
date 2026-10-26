"""
Pre-download script for the ODSC AI West 2026 workshop.

From Retrieval to Recall: Building Governed Agentic Memory on Vector Databases

Run this at home BEFORE the workshop. Conference Wi-Fi will not reliably
carry a room full of people downloading this at the same time.

Usage:
    python setup.py            # install, pull, pre-download, create .env, verify
    python setup.py --verify   # only report what is ready and which tier you are on; writes nothing
                               # to the repo (on the embedded tier it starts and stops Weaviate in a
                               # throwaway temp folder to prove it can run)

No API keys are needed. Everything runs locally.
"""
from __future__ import annotations  # so "Exception | None" below does not crash Python 3.9 before check_python() can speak


import os
import platform
import re
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


def install_dependencies() -> bool:
    banner("Step 2: Install Python dependencies")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            check=True,
        )
        print("Python dependencies installed.\n")
        return True
    except subprocess.CalledProcessError:
        print("pip install failed. Check the error above. The steps below will report what is missing.\n")
        return False


def load_env_file() -> str:
    """Read .env into the environment so EMBEDDING_MODEL and the tier settings apply to whatever
    runs next. Returns "loaded", "missing" or "no-dotenv". Never writes anything."""
    if not Path(".env").exists():
        return "missing"
    try:
        from dotenv import load_dotenv
    except ImportError:
        return "no-dotenv"
    load_dotenv()
    return "loaded"


def weaviate_running() -> bool:
    """Is a Weaviate answering on the configured local ports? The notebooks' connect_to_local() needs
    both the REST port and the gRPC port, so both are probed. (Tier 1 needs `docker compose up -d`.)"""
    import socket
    import urllib.request

    host = os.getenv("WEAVIATE_HOST", "localhost")
    port = os.getenv("WEAVIATE_PORT", "8080")
    try:
        grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))  # a bad value in .env means "not reachable"
        with urllib.request.urlopen(f"http://{host}:{port}/v1/.well-known/ready", timeout=2) as r:
            if r.status != 200:
                return False
        with socket.create_connection((host, grpc_port), timeout=2):
            return True
    except Exception:  # noqa: BLE001
        return False


def predownload_model() -> None:
    banner("Step 4: Pre-download the embedding model (about 90 MB)")
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


def embedded_already_running(port: str, grpc_port: str) -> str:
    """What is on the embedded ports right now. "ready" when a Weaviate answers ready on the REST port
    and something accepts connections on the gRPC port, which is the attendee's own notebook kernel
    holding its Embedded instance. "rest-only" when REST answers but gRPC does not, which the
    notebooks cannot use. "none" otherwise, and the probe decides."""
    import socket
    import urllib.request

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/.well-known/ready", timeout=2) as r:
            if r.status != 200:
                return "none"
    except Exception:  # noqa: BLE001
        return "none"
    try:
        with socket.create_connection(("127.0.0.1", int(grpc_port)), timeout=2):
            return "ready"
    except OSError:
        return "rest-only"


def embedded_probe(persistence_path: Path) -> tuple[bool, Exception | None]:
    """Start Weaviate Embedded with the same ports memory/connect.py uses, ask it if it is ready,
    stop it. Returns (ready, None) when it started, or (False, exc) when it did not. Used by the
    pre-download step (on the real data path) and by --verify (on a throwaway temp path, so verify
    never touches the repo), so both report the same truth about tier 2."""
    # The embedded binary writes its startup log to stderr. Park stderr on /dev/null for the
    # probe so the verify report stays readable; any failure comes back as the exception.
    sys.stderr.flush()
    saved_stderr = os.dup(2)
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, 2)
        try:
            import weaviate

            client = weaviate.connect_to_embedded(
                version=WEAVIATE_VERSION,
                persistence_data_path=str(persistence_path),
                port=int(os.getenv("WEAVIATE_EMBEDDED_PORT", "8079")),
                grpc_port=int(os.getenv("WEAVIATE_EMBEDDED_GRPC_PORT", "50050")),
            )
            try:
                return bool(client.is_ready()), None
            finally:
                client.close()
        except Exception as exc:  # noqa: BLE001
            return False, exc
    finally:
        os.dup2(saved_stderr, 2)
        os.close(saved_stderr)
        os.close(devnull)


def predownload_embedded() -> None:
    """Tier 2 needs a Weaviate binary. Fetch it now so it is not a conference download."""
    banner("Step 5: Pre-download Weaviate Embedded (tier 2 fallback, Mac and Linux)")
    if platform.system() == "Windows":
        print("Weaviate Embedded does not run on Windows. Skipping. Your fallback is tier 3.\n")
        return
    ready, exc = embedded_probe(Path(".weaviate-embedded").resolve())  # the real tier 2 data path
    if exc is not None:
        print(f"Embedded Weaviate could not start: {exc}")
        print("  Not fatal if Docker works for you. Otherwise tier 3 is the floor.\n")
    elif ready:
        print("Embedded Weaviate started, answered ready, and stopped cleanly.\n")
    else:
        print("Embedded Weaviate started but never became ready, so tier 2 is not usable as it stands.")
        print("  Check that nothing else holds its ports (8079 and 50050 by default).")
        print("  Not fatal if Docker works for you. Otherwise tier 3 is the floor.\n")


def ensure_env_file() -> None:
    """Create .env from .env.example if it is missing. Only in the full run; --verify never writes."""
    banner("Step 3: Create .env")
    if Path(".env").exists():
        print(".env already exists. Left as is.\n")
    elif Path(".env.example").exists():
        Path(".env").write_text(Path(".env.example").read_text())
        print("Created .env from .env.example. The defaults are right for Docker.\n")
    else:
        print(".env.example is missing; re-clone the repo.\n")


def verify(require_running: bool = True) -> bool:
    """Report what is ready. Returns True when nothing needs attention, so callers can exit non-zero.

    require_running: on the docker tier, treat a stopped Weaviate container as a blocker. True for
    --verify, which attendees run to confirm the notebooks can run right now. False at the end of
    the full setup, which never starts the container itself (README step 4 does), so a stopped
    container there is an instruction, not a failure."""
    banner("Verification")
    issues: list[str] = []  # blockers: the configured tier or the notebooks cannot run
    notes: list[str] = []  # worth knowing, not blocking: the vector cache covers these
    env_status = load_env_file()  # first, so EMBEDDING_MODEL and WEAVIATE_MODE below are the configured ones
    mode = os.getenv("WEAVIATE_MODE", "docker").strip().lower() or "docker"  # same rule as memory/connect.py

    if not check_python():
        issues.append("Python 3.11+ required")

    # Docker only matters on tier 1. On embedded or cloud a missing Docker is information, not a problem.
    docker_needed = mode == "docker"
    if docker_available():
        result = subprocess.run(["docker", "image", "inspect", WEAVIATE_IMAGE], capture_output=True)
        if result.returncode == 0:
            print("  Docker + image:  OK (tier 1 available)")
            if docker_needed:
                if weaviate_running():
                    print("  Weaviate:        running (tier 1 ready)")
                elif require_running:
                    issues.append("Weaviate is not running (tier 1 not ready). Run: docker compose up -d, then verify again")
                    print("  Weaviate:        NOT RUNNING")
                else:
                    print("  Weaviate:        not running yet. Before notebook 0: docker compose up -d")
        elif docker_needed:
            issues.append("Weaviate image not pulled yet (tier 1 not ready)")
            print("  Docker + image:  Docker runs, image MISSING")
        else:
            print(f"  Docker + image:  Docker runs, image not pulled (not needed on tier {mode})")
    elif docker_needed:
        issues.append("Docker not available (tier 1 not ready; set WEAVIATE_MODE=embedded or cloud)")
        print("  Docker:          NOT AVAILABLE")
    else:
        print(f"  Docker:          not available (not needed on tier {mode})")

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

    if mode == "embedded":
        # weaviate-client 4.23 (weaviate/embedded.py) uses XDG_CACHE_HOME itself as the binary folder
        # when it is set. Other versions put a weaviate-embedded/ folder under it. Look in both.
        xdg = os.environ.get("XDG_CACHE_HOME")
        cache_dirs = [Path(xdg), Path(xdg) / "weaviate-embedded"] if xdg else [Path.home() / ".cache/weaviate-embedded"]
        binaries = [b for d in cache_dirs for b in d.glob(f"weaviate-v{WEAVIATE_VERSION}-*")]
        embedded_port = os.getenv("WEAVIATE_EMBEDDED_PORT", "8079")
        embedded_grpc = os.getenv("WEAVIATE_EMBEDDED_GRPC_PORT", "50050")
        bad_ports = [
            f"{name}={value!r}" for name, value in (("WEAVIATE_EMBEDDED_PORT", embedded_port), ("WEAVIATE_EMBEDDED_GRPC_PORT", embedded_grpc))
            if not (value.isdigit() and 1 <= int(value) <= 65535)
        ]
        if bad_ports:
            issues.append("not a valid port number: " + ", ".join(bad_ports) + " (fix it in .env or unset it)")
            print("  Weaviate Embedded: port setting INVALID (" + ", ".join(bad_ports) + ")")
            running = "invalid"
        else:
            running = embedded_already_running(embedded_port, embedded_grpc) if binaries else "none"
        if running == "invalid":
            pass
        elif running == "ready":
            # The attendee's own notebook has Embedded up on both ports. That IS tier 2 ready;
            # starting a second instance here would only collide with it.
            print(f"  Weaviate Embedded: already running on ports {embedded_port} and {embedded_grpc} (tier 2 ready)")
        elif running == "rest-only":
            issues.append(
                f"a Weaviate answers on port {embedded_port} but nothing listens on gRPC port {embedded_grpc}; "
                "the notebooks need both. Stop that instance, or set WEAVIATE_EMBEDDED_GRPC_PORT to match it"
            )
            print(f"  Weaviate Embedded: REST on {embedded_port} but no gRPC on {embedded_grpc} (tier 2 not ready)")
        elif binaries:
            print(f"  Weaviate Embedded: binary cached (v{WEAVIATE_VERSION}), starting it to check...")
            import shutil
            import tempfile

            scratch = tempfile.mkdtemp(prefix="weaviate-verify-")  # never the repo's .weaviate-embedded
            try:
                ready, exc = embedded_probe(Path(scratch))
            finally:
                shutil.rmtree(scratch, ignore_errors=True)
            if exc is not None:
                issues.append(
                    f"Weaviate Embedded could not start: {type(exc).__name__}. Is something else on ports "
                    f"{os.getenv('WEAVIATE_EMBEDDED_PORT', '8079')} and {os.getenv('WEAVIATE_EMBEDDED_GRPC_PORT', '50050')}? "
                    "Otherwise set WEAVIATE_MODE=docker or cloud"
                )
                print("  Weaviate Embedded: binary cached but it did NOT START (tier 2 not ready)")
            elif ready:
                print("  Weaviate Embedded: OK (started and ready, tier 2 ready)")
            else:
                issues.append("Weaviate Embedded started but never became ready (tier 2 not ready); set WEAVIATE_MODE=docker or cloud")
                print("  Weaviate Embedded: started but NOT READY (tier 2 not ready)")
        else:
            issues.append(
                f"Weaviate Embedded v{WEAVIATE_VERSION} binary not cached (run setup.py without --verify "
                "on a good connection, or it downloads on first connect)"
            )
            print("  Weaviate Embedded: binary NOT CACHED")

    model_name = os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL)
    try:
        from huggingface_hub import snapshot_download

        snapshot_download(model_name, local_files_only=True)  # raises if not in the local cache
        print(f"  embedding model: OK (cached: {model_name})")
    except Exception:  # noqa: BLE001  (missing package, or model not cached)
        notes.append(
            f"embedding model {model_name} not cached. Every shipped text is in data/vector_cache.json, "
            "so the notebooks run without it; only sentences you type yourself need the model. "
            "Run setup.py without --verify on a good connection to fetch it."
        )
        print("  embedding model: not cached (vector cache covers the workshop texts)")

    if Path("data/vector_cache.json").exists():
        print("  vector cache:    OK")
    else:
        issues.append("data/vector_cache.json missing (re-clone the repo)")
        print("  vector cache:    MISSING")

    if env_status == "loaded":
        print(f"  .env file:       OK (WEAVIATE_MODE={mode})")
        if mode not in ("docker", "embedded", "cloud"):
            issues.append(f"WEAVIATE_MODE={mode!r} is not one of docker, embedded, cloud")
        if mode == "cloud" and not (
            os.getenv("WEAVIATE_CLOUD_URL", "").strip() and os.getenv("WEAVIATE_CLOUD_KEY", "").strip()
        ):  # same .strip() as memory/connect.py
            issues.append("WEAVIATE_MODE=cloud but WEAVIATE_CLOUD_URL or WEAVIATE_CLOUD_KEY is empty")
        if mode == "cloud" and os.getenv("WEAVIATE_CLOUD_URL", "").strip() and os.getenv("WEAVIATE_CLOUD_KEY", "").strip():
            try:
                import weaviate
                from weaviate.classes.init import Auth

                cloud = weaviate.connect_to_weaviate_cloud(
                    cluster_url=os.getenv("WEAVIATE_CLOUD_URL", "").strip(),
                    auth_credentials=Auth.api_key(os.getenv("WEAVIATE_CLOUD_KEY", "").strip()),
                )
                try:
                    reachable = cloud.is_ready()
                finally:
                    cloud.close()
                if reachable:
                    print("  Weaviate Cloud:  reachable (tier 3 ready)")
                else:
                    issues.append("Weaviate Cloud answered but is not ready; try again in a minute")
                    print("  Weaviate Cloud:  not ready")
            except Exception as exc:  # noqa: BLE001  (bad URL, bad key, no network, client missing)
                issues.append(f"could not connect to Weaviate Cloud with the configured URL and key: {type(exc).__name__}")
                print("  Weaviate Cloud:  NOT REACHABLE")
        if mode == "cloud":
            # Same cleaning rule as memory/connect.py handle(): letters and digits only, nothing else survives.
            clean = re.sub(r"[^A-Za-z0-9]", "", os.getenv("ATTENDEE_HANDLE", ""))
            if clean and not clean[0].isalpha():
                clean = "A" + clean
            if clean:
                print(f"  attendee handle: OK (your collection will be {clean[:1].upper() + clean[1:]}_MemoryRecord)")
            else:
                issues.append("WEAVIATE_MODE=cloud needs ATTENDEE_HANDLE in .env (letters and digits)")
        if mode == "embedded" and platform.system() == "Windows":
            issues.append("WEAVIATE_MODE=embedded does not work on Windows; use docker or cloud")
    elif env_status == "no-dotenv":
        issues.append("python-dotenv not installed (run: pip install -r requirements.txt)")
        print("  .env file:       present, but python-dotenv is MISSING so it cannot be read")
    else:
        issues.append(".env file not found (run: python setup.py, or cp .env.example .env)")
        print("  .env file:       NOT FOUND")

    print()
    if notes:
        print(f"Worth knowing, not blocking ({len(notes)}):")
        for item in notes:
            print(f"  - {item}")
        print()
    if issues:
        print(f"Things to look at ({len(issues)}):")
        for item in issues:
            print(f"  - {item}")
        print("\nDocker problems are not fatal. See 'Fallback tiers' in the README.")
        return False
    if mode == "docker" and not weaviate_running():
        print("All good. Start Weaviate with `docker compose up -d`, then open notebooks/0-prep-run.ipynb.")
    else:
        print("All good. Open notebooks/0-prep-run.ipynb and run it top to bottom.")
    return True


if __name__ == "__main__":
    print()
    print("ODSC AI West 2026 Workshop Setup")
    print("From Retrieval to Recall:")
    print("Building Governed Agentic Memory on Vector Databases")
    print()

    if "--verify" in sys.argv:
        sys.exit(0 if verify(require_running=True) else 1)

    print("Run this at home before the workshop.\n")
    if not check_python():
        print("\nInstall Python 3.11 or newer, then run this again.")
        sys.exit(1)
    pull_image()
    installed = install_dependencies()
    ensure_env_file()
    load_env_file()  # so EMBEDDING_MODEL and the tier set in .env apply to the steps below
    predownload_model()
    predownload_embedded()
    ready = verify(require_running=False)  # this script does not start the container; README step 4 does
    if not installed:
        print("\nSetup is NOT complete: the dependency install failed. Fix that and run this again.")
    if not (installed and ready):
        sys.exit(1)
