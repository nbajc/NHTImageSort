import os
import shutil
import base64
import argparse
import requests
import json
from pathlib import Path

# Ollama API settings
OLLAMA_API_URL = "http://localhost:11434/api/generate"

def get_image_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

class DescriberAgent:
    def __init__(self, model_name="llava"):
        self.model_name = model_name

    def describe(self, image_path):
        prompt = (
            "Describe this image in detail. Focus on the main subjects, actions, setting, and objects present. "
            "IMPORTANT ANATOMICAL TERMINOLOGY: Always use the word 'penis' instead of 'cock'. If there is an 'erection', describe it as an 'erected penis'."
        )

        try:
            base64_image = get_image_base64(image_path)
            
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "images": [base64_image],
                "stream": False
            }
            
            response = requests.post(OLLAMA_API_URL, json=payload)
            response.raise_for_status()
            
            result = response.json()
            return result.get("response", "").strip()
            
        except requests.exceptions.RequestException as e:
            print(f"[DescriberAgent] Error communicating with Ollama: {e}")
            return None
        except Exception as e:
            print(f"[DescriberAgent] Error processing {image_path}: {e}")
            return None

class SorterAgent:
    def __init__(self, model_name="llama3", categories=None):
        self.model_name = model_name
        self.categories = categories or []

    def sort(self, description):
        if not description or not self.categories:
            return None

        categories_str = ", ".join([f'"{c}"' for c in self.categories])
        
        # Strict prompt to force the LLM to only output the category name
        prompt = (
            f"You are an image categorization assistant.\n"
            f"IMPORTANT TERMINOLOGY: Treat 'cock' as synonymous with 'penis', and 'erection' as 'erected penis'.\n\n"
            f"Here is an image description:\n'{description}'\n\n"
            f"Based ONLY on this description, which of these exact categories does it fit best? "
            f"Categories: [{categories_str}].\n"
            f"If none fit perfectly, pick the closest one. "
            f"Respond with EXACTLY the matching category name and NOTHING else. Do not use quotes or punctuation."
        )
        
        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False
            }
            
            response = requests.post(OLLAMA_API_URL, json=payload)
            response.raise_for_status()
            
            result = response.json()
            category = result.get("response", "").strip().strip('"\'')
            
            # Simple fuzzy match in case the model hallucinates surrounding text
            for valid_cat in self.categories:
                if valid_cat.lower() in category.lower():
                    return valid_cat
                    
            return None
            
        except requests.exceptions.RequestException as e:
            print(f"[SorterAgent] Error communicating with Ollama: {e}")
            return None
        except Exception as e:
            print(f"[SorterAgent] Error sorting description: {e}")
            return None

def process_images(source_dir, target_dir, categories, vision_model, text_model, extensions, dry_run=False):
    if not os.path.exists(source_dir):
        print(f"Error: Source directory not found: {source_dir}")
        return

    if not dry_run and not os.path.exists(target_dir):
        os.makedirs(target_dir)

    print(f"Initializing agents (Vision: {vision_model}, Text: {text_model})...")
    describer = DescriberAgent(model_name=vision_model)
    sorter = SorterAgent(model_name=text_model, categories=categories)
    
    exts = tuple(f".{ext.lower()}" for ext in extensions)

    for root, _, files in os.walk(source_dir):
        for file in files:
            if file.lower().endswith(exts):
                full_path = os.path.join(root, file)
                print(f"\n--- Processing: {full_path} ---")
                
                # 1. Describe Image
                print("Generating description...")
                description = describer.describe(full_path)
                
                if not description:
                    print("Failed to generate description. Skipping.")
                    continue
                    
                print(f"Description: {description[:100]}...") # Print snippet
                
                # 2. Sort Image
                print("Determining category...")
                category = sorter.sort(description)
                
                if not category:
                    print("Failed to determine a matching category. Skipping.")
                    continue
                    
                print(f"Assigned Category: '{category}'")
                
                # 3. Move Image
                # Target path is like: target_dir / category / filename
                category_dir = os.path.join(target_dir, category)
                target_path = os.path.join(category_dir, file)
                
                if not dry_run:
                    try:
                        if not os.path.exists(category_dir):
                            os.makedirs(category_dir)
                            
                        # Handle duplicate filenames in target
                        if os.path.exists(target_path):
                            base, extension = os.path.splitext(file)
                            counter = 1
                            while os.path.exists(target_path):
                                target_path = os.path.join(category_dir, f"{base}_{counter}{extension}")
                                counter += 1
                                
                        shutil.move(full_path, target_path)
                        print(f"Moved to: {target_path}")
                        
                        # Optionally save the description along with it
                        desc_path = os.path.splitext(target_path)[0] + ".txt"
                        with open(desc_path, "w", encoding="utf-8") as f:
                            f.write(description)
                            
                    except Exception as e:
                        print(f"Failed to move {full_path}: {e}")
                else:
                    print(f"[Dry Run] Would move to: {target_path}")
                    print(f"[Dry Run] Would save description to .txt alongside the image.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multiagent Image Sorter using local Ollama models.")
    parser.add_argument("--source", required=True, help="Source directory containing images.")
    parser.add_argument("--target", required=True, help="Target root directory to move sorted images to.")
    parser.add_argument("--categories", nargs="+", required=True, help="List of categories/folders to sort into.")
    parser.add_argument("--vision-model", default="llava", help="Ollama model to use for image description (default: llava).")
    parser.add_argument("--text-model", default="llama3", help="Ollama model to use for sorting logic (default: llama3).")
    parser.add_argument("--extensions", nargs="+", default=["jpg", "jpeg", "png", "webp"], help="List of image file extensions to process.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate the sorting process without moving files.")
    
    args = parser.parse_args()
    
    process_images(
        source_dir=args.source,
        target_dir=args.target,
        categories=args.categories,
        vision_model=args.vision_model,
        text_model=args.text_model,
        extensions=args.extensions,
        dry_run=args.dry_run
    )
