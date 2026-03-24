import os
import sqlite3
import base64
import random
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "nexus_catalog.db")
BASE_DIR = Path(__file__).parent.absolute()

def make_thumbnail_b64(image_path: Path) -> str:
    try:
        from PIL import Image
        import io
        img = Image.open(image_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.thumbnail((400, 400))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=70)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()[:50_000]).decode()

def seed():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS images (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name     TEXT,
            original_path TEXT,
            new_path      TEXT,
            category      TEXT,
            description   TEXT,
            project_tag   TEXT
        )
    ''')
    
    # clear db for fresh demo run
    c.execute("DELETE FROM images")
    
    dirs = [BASE_DIR / "test_images", BASE_DIR / "sorted_images"]
    categories = ["Interior", "Exterior", "Residential", "Hospitality", "Institutional"]
    
    count = 0
    for d in dirs:
        if not d.exists(): continue
        for root, _, files in os.walk(d):
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')) and file != "placeholder.txt":
                    filepath = Path(root) / file
                    cat = random.choice(categories)
                    desc = f"Demo image automatically ingested from local repository folder."
                    
                    c.execute(
                        "INSERT INTO images (file_name, original_path, new_path, category, description, project_tag) VALUES (?,?,?,?,?,?)",
                        (file, str(filepath), str(filepath), cat, desc, "demo"),
                    )
                    count += 1
                    print(f"Ingested {file} into {cat}")
                    
    conn.commit()
    conn.close()
    print(f"Seeded {count} images from local folders into catalog.")

if __name__ == "__main__":
    seed()
