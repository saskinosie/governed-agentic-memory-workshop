"""
Pre-download script for the ODSC AI West 2026 workshop.

From Retrieval to Recall: Building Governed Agentic Memory on Vector Databases

Run this at home BEFORE the workshop. Conference Wi-Fi will not reliably
support a room full of people downloading this at the same time.

Usage:
    python setup.py
"""

import os
import subprocess
import sys


WEAVIATE_IMAGE = "semitechnologies/weaviate:1.32.9"


def pull_image():
    print("=" * 60)
    print(f"Step 1: Pulling the Weaviate Docker image ({WEAVIATE_IMAGE})")
    print("=" * 60)
    try:
        subprocess.run(["docker", "pull", WEAVIATE_IMAGE], check=True)
        print("Docker image pulled successfully.\n")
    except FileNotFoundError:
        print("Docker not found. Install Docker Desktop first:")
        print("  https://docs.docker.com/get-started/get-docker/")
        print("If you cannot install Docker, see the Fallback Options")
        print("section of the README. You can still do the workshop.\n")
    except subprocess.CalledProcessError:
        print("Docker pull failed. Make sure Docker Desktop is running.")
        print("If it will not start, see Fallback Options in the README.\n")


def install_dependencies():
    print("=" * 60)
    print("Step 2: Installing Python dependencies")
    print("=" * 60)
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            check=True,
        )
        print("Python dependencies installed successfully.\n")
    except subprocess.CalledProcessError:
        print("pip install failed. Check the error above.\n")


def verify():
    print("=" * 60)
    print("Verification")
    print("=" * 60)

    errors = []

    try:
        result = subprocess.run(
            ["docker", "image", "inspect", WEAVIATE_IMAGE],
            capture_output=True,
        )
        if result.returncode == 0:
            print("  Weaviate image:  OK")
        else:
            errors.append("Weaviate image not pulled (fallback available)")
            print("  Weaviate image:  MISSING")
    except FileNotFoundError:
        errors.append("Docker not installed (fallback available)")
        print("  Docker:          NOT INSTALLED")

    try:
        import weaviate

        print(f"  weaviate-client: OK (v{weaviate.__version__})")
    except ImportError:
        errors.append("weaviate-client not installed")
        print("  weaviate-client: MISSING")

    try:
        import pydantic_ai  # noqa: F401

        print("  pydantic-ai:     OK")
    except ImportError:
        errors.append("pydantic-ai not installed")
        print("  pydantic-ai:     MISSING")

    try:
        import openai  # noqa: F401

        print("  openai:          OK")
    except ImportError:
        errors.append("openai not installed")
        print("  openai:          MISSING")

    if os.path.exists(".env"):
        from dotenv import load_dotenv

        load_dotenv()
        if os.getenv("OPENAI_API_KEY", "").startswith("sk-"):
            print("  .env file:       OK (OpenAI key set)")
        else:
            errors.append("OPENAI_API_KEY not set in .env")
            print("  .env file:       MISSING OpenAI key")
    else:
        errors.append(".env file not found")
        print("  .env file:       NOT FOUND (run: cp .env.example .env)")

    print()
    if errors:
        print(f"Issues found ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")
        print("\nPlease resolve these before the workshop.")
        print("Docker problems are not fatal. See Fallback Options in the README.")
    else:
        print("All good. You are ready for the workshop.")


if __name__ == "__main__":
    print()
    print("ODSC AI West 2026 Workshop Setup")
    print("From Retrieval to Recall:")
    print("Building Governed Agentic Memory on Vector Databases")
    print()
    print("Run this at home before the workshop.\n")

    pull_image()
    install_dependencies()
    verify()
