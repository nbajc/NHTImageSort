import os
import base64
import requests
import json
import re
import shutil
import argparse
from pathlib import Path

# ── Mode switch ───────────────────────────────────────────────────────────────
# Local (default): USE_CLOUD=false  →  Ollama LLaVA + Llama3
# Cloud demo:      USE_CLOUD=true   →  OpenAI GPT-4o-mini
USE_CLOUD      = os.getenv("USE_CLOUD", "false").lower() == "true"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OLLAMA_API_URL = os.getenv("OLLAMA_URL", "http://localhost:11434") + "/api/generate"


def get_image_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ── Describer Agent ───────────────────────────────────────────────────────────

class DescriberAgent:
    """
    Describes an image in architectural terms.
    Local mode:  Ollama LLaVA
    Cloud mode:  OpenAI GPT-4o-mini vision
    """

    def __init__(self, model_name="llava"):
        self.model_name = model_name

    def describe(self, image_path: str) -> str | None:
        if USE_CLOUD:
            return self._describe_openai(image_path)
        return self._describe_ollama(image_path)

    def _describe_ollama(self, image_path: str) -> str | None:
        prompt = (
            "You are an architectural image analyst. "
            "Describe this image in 2-3 sentences focusing on: "
            "spatial quality, materials, lighting, building type, and program. "
            "Be specific and professional."
        )
        try:
            b64 = get_image_base64(image_path)
            resp = requests.post(
                OLLAMA_API_URL,
                json={"model": self.model_name, "prompt": prompt, "images": [b64], "stream": False},
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except requests.exceptions.RequestException as e:
            print(f"[DescriberAgent/Ollama] Error: {e}")
            return None
        except Exception as e:
            print(f"[DescriberAgent/Ollama] Error processing {image_path}: {e}")
            return None

    def _describe_openai(self, image_path: str) -> str | None:
        if not OPENAI_API_KEY:
            print("[DescriberAgent/OpenAI] No OPENAI_API_KEY set")
            return None
        try:
            b64 = get_image_base64(image_path)
            ext = Path(image_path).suffix.lower().lstrip(".")
            mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                    "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")

            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "max_tokens": 200,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "You are an architectural image analyst. "
                                    "Describe this image in 2-3 sentences focusing on: "
                                    "spatial quality, materials, lighting, building type, and program. "
                                    "Be specific and professional."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime};base64,{b64}",
                                    "detail": "low",
                                },
                            },
                        ],
                    }],
                },
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"[DescriberAgent/OpenAI] Error: {e}")
            return None


# ── Sorter Agent ──────────────────────────────────────────────────────────────

class SorterAgent:
    """
    Classifies a description into a category.
    Local mode:  Ollama Llama3
    Cloud mode:  OpenAI GPT-4o-mini text
    """

    def __init__(self, model_name="llama3", categories=None):
        self.model_name = model_name
        self.categories = categories or []

    def sort(self, description: str) -> str | None:
        if not description or not self.categories:
            return None
        if USE_CLOUD:
            return self._sort_openai(description)
        return self._sort_ollama(description)

    def _build_prompt(self, description: str) -> str:
        cats = ", ".join(f'"{c}"' for c in self.categories)
        return (
            f"You are an image categorization assistant for an architecture firm.\n\n"
            f"Image description:\n'{description}'\n\n"
            f"Which of these exact categories fits best? [{cats}]\n"
            f"Pick the closest one if none fit perfectly.\n"
            f"Respond with EXACTLY the category name and NOTHING else."
        )

    def _sort_ollama(self, description: str) -> str | None:
        try:
            resp = requests.post(
                OLLAMA_API_URL,
                json={"model": self.model_name, "prompt": self._build_prompt(description), "stream": False},
                timeout=30,
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "").strip().strip('"\'')
            for cat in self.categories:
                if cat.lower() in raw.lower():
                    return cat
            return None
        except Exception as e:
            print(f"[SorterAgent/Ollama] Error: {e}")
            return None

    def _sort_openai(self, description: str) -> str | None:
        if not OPENAI_API_KEY:
            return None
        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "max_tokens": 20,
                    "messages": [{"role": "user", "content": self._build_prompt(description)}],
                },
                timeout=15,
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip().strip('"\'')
            for cat in self.categories:
                if cat.lower() in raw.lower():
                    return cat
            return None
        except Exception as e:
            print(f"[SorterAgent/OpenAI] Error: {e}")
            return None


# ── CLI entry point (unchanged from original) ─────────────────────────────────

def process_images(source_dir, target_dir, categories, vision_model, text_model, extensions, dry_run=False):
    if not os.path.exists(source_dir):
        print(f"Error: Source directory not found: {source_dir}")
        return

    if not dry_run and not os.path.exists(target_dir):
        os.makedirs(target_dir)

    print(f"Initializing agents (Vision: {vision_model}, Text: {text_model}, Cloud: {USE_CLOUD})...")
    describer = DescriberAgent(model_name=vision_model)
    sorter = SorterAgent(model_name=text_model, categories=categories)

    exts = tuple(f".{ext.lower()}" for ext in extensions)

    for root, _, files in os.walk(source_dir):
        for file in files:
            if file.lower().endswith(exts):
                full_path = os.path.join(root, file)
                print(f"\n--- Processing: {full_path} ---")

                description = describer.describe(full_path)
                if not description:
                    print("Failed to generate description. Skipping.")
                    continue
                print(f"Description: {description[:100]}...")

                category = sorter.sort(description)
                if not category:
                    print("Failed to determine category. Skipping.")
                    continue
                print(f"Category: '{category}'")

                category_dir = os.path.join(target_dir, category)
                target_path = os.path.join(category_dir, file)

                if not dry_run:
                    try:
                        os.makedirs(category_dir, exist_ok=True)
                        if os.path.exists(target_path):
                            base, ext2 = os.path.splitext(file)
                            counter = 1
                            while os.path.exists(target_path):
                                target_path = os.path.join(category_dir, f"{base}_{counter}{ext2}")
                                counter += 1
                        shutil.move(full_path, target_path)
                        with open(os.path.splitext(target_path)[0] + ".txt", "w") as f:
                            f.write(description)
                        print(f"Moved to: {target_path}")
                    except Exception as e:
                        print(f"Failed to move {full_path}: {e}")
                else:
                    print(f"[Dry Run] Would move to: {target_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multiagent Image Sorter.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--categories", nargs="+", required=True)
    parser.add_argument("--vision-model", default="llava")
    parser.add_argument("--text-model", default="llama3")
    parser.add_argument("--extensions", nargs="+", default=["jpg", "jpeg", "png", "webp"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    process_images(
        source_dir=args.source,
        target_dir=args.target,
        categories=args.categories,
        vision_model=args.vision_model,
        text_model=args.text_model,
        extensions=args.extensions,
        dry_run=args.dry_run,
    )
