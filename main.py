"""
PRANAG-AI  —  Prompt Parser CLI

Reads input from:  input_folder/input.txt
Falls back to:     CLI arg  →  interactive input

Usage:
    python main.py                        # reads input_folder/input.txt
    python main.py "wheat for Jodhpur"    # CLI arg (override)
"""
import sys
import json
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s",
)

from search_engine.vector_store import populate
from orchestrator.workflow import run_pipeline

INPUT_FILE = os.path.join("input_folder", "input.txt")


def read_prompt_from_file() -> str | None:
    if not os.path.exists(INPUT_FILE):
        print(f"⚠️  {INPUT_FILE} not found.")
        return None
    # detect encoding — handles PowerShell UTF-16 and normal UTF-8
    for enc in ("utf-8-sig", "utf-16", "utf-8", "latin-1"):
        try:
            with open(INPUT_FILE, "r", encoding=enc) as f:
                prompt = f.read().strip()
            if prompt:
                print(f"   (encoding detected: {enc})")
                return prompt
        except (UnicodeDecodeError, UnicodeError):
            continue
    print(f"⚠️  Could not decode {INPUT_FILE}.")
    return None


def main():
    # Seed vector store on first run (no-op if already populated)
    print("🌱  Initialising vector store …")
    populate()

    # Priority: CLI arg > input_folder/input.txt > interactive input
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        print(f"📝  Using CLI argument as prompt.")
    else:
        prompt = read_prompt_from_file()
        if prompt:
            print(f"📂  Prompt read from {INPUT_FILE}")
        else:
            prompt = input("\nEnter your PRANAG prompt: ").strip()
            if not prompt:
                print("No prompt entered.  Exiting.")
                return

    print(f"\n🚀  Running pipeline for: '{prompt}'\n")
    result = run_pipeline(prompt)

    print("─" * 60)
    print("PIPELINE OUTPUT")
    print("─" * 60)
    print(json.dumps(result, indent=2))

    if result.get("error") and not result.get("spec"):
        print("\n⚠️  Pipeline could not produce a valid spec.")
        print(f"   Error: {result['error']}")
        sys.exit(1)
    else:
        print("\n✅  spec.json produced successfully.")


if __name__ == "__main__":
    main()
