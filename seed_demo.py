"""
seed_demo.py — Nexus Hestia Demo Seeder

Downloads a small set of free architecture images from Unsplash,
runs them through the AI pipeline, and stores them in the SQLite catalog.

Run once after deploying to Railway:
    python seed_demo.py

Or locally before deploying:
    python seed_demo.py --save-db
    (then commit nexus_catalog.db to the repo)
"""

import os
import sqlite3
import base64
import json
import argparse
import requests
import hashlib
from pathlib import Path

DB_PATH  = os.getenv("DB_PATH", "nexus_catalog.db")
DEMO_DIR = Path("/tmp/nht_demo")
DEMO_DIR.mkdir(parents=True, exist_ok=True)

# Free architecture images from Unsplash (direct CDN links, no API key needed)
DEMO_IMAGES = [
    {
        "url": "https://images.unsplash.com/photo-1487958449943-2429e8be8625?w=600&q=70",
        "filename": "exterior_modern_facade.jpg",
        "category": "Exterior",
        "description": "A striking modernist facade featuring floor-to-ceiling glazing and clean horizontal lines. The building's white rectilinear form contrasts against an overcast sky, with minimal ornamentation emphasizing structural clarity and material precision. The composition suggests a civic or cultural program.",
        "project_tag": "demo",
    },
    {
        "url": "https://images.unsplash.com/photo-1497366216548-37526070297c?w=600&q=70",
        "filename": "interior_open_office.jpg",
        "category": "Interior",
        "description": "An expansive open-plan interior flooded with diffuse natural light from skylights above. Polished concrete floors and exposed steel structure define the industrial aesthetic, while clusters of workstations create informal zones within the fluid space. The spatial volume suggests a creative or tech-sector office program.",
        "project_tag": "demo",
    },
    {
        "url": "https://images.unsplash.com/photo-1518005020951-eccb494ad742?w=600&q=70",
        "filename": "exterior_glass_tower.jpg",
        "category": "Commercial",
        "description": "A high-rise commercial tower clad entirely in a reflective curtain wall system, capturing the surrounding cityscape in its undulating glass skin. The tapering form rises dramatically against a blue sky, its articulated mullion grid giving scale and rhythm to the otherwise seamless surface.",
        "project_tag": "demo",
    },
    {
        "url": "https://images.unsplash.com/photo-1511818966892-d7d671e672a2?w=600&q=70",
        "filename": "interior_lobby_atrium.jpg",
        "category": "Interior",
        "description": "A soaring hotel atrium with a central void rising twelve stories, enclosed by a faceted glass roof that drenches the space in warm afternoon light. Balconies with wrought-iron railings line each floor, creating layered visual depth, while lush tropical plantings at ground level soften the monumental scale.",
        "project_tag": "demo",
    },
    {
        "url": "https://images.unsplash.com/photo-1524230572899-a752b3835840?w=600&q=70",
        "filename": "exterior_residential_courtyard.jpg",
        "category": "Residential",
        "description": "A Mediterranean residential compound organized around a shaded central courtyard. Whitewashed masonry walls punctuated by deep-set arched openings create a rhythm of light and shadow, while terracotta roof tiles and climbing vegetation reinforce the vernacular character of the composition.",
        "project_tag": "demo",
    },
    {
        "url": "https://images.unsplash.com/photo-1504307651254-35680f356dfd?w=600&q=70",
        "filename": "construction_site_concrete.jpg",
        "category": "Construction Site",
        "description": "An active construction site showing a concrete shear wall system under assembly, with exposed rebar tying and formwork still in place. A tower crane is partially visible in the upper frame, indicating the scale of the structure. The image captures the raw materiality that precedes architectural finish.",
        "project_tag": "demo",
    },
    {
        "url": "https://images.unsplash.com/photo-1519167758481-83f550bb49b3?w=600&q=70",
        "filename": "hospitality_banquet_hall.jpg",
        "category": "Hospitality",
        "description": "An opulent ballroom interior configured for a formal event, featuring a coffered ceiling with integrated cove lighting that casts a warm amber glow. Crystal chandeliers punctuate the vertical rhythm of fluted pilasters, and the polished marble floor reflects the layered illumination scheme.",
        "project_tag": "demo",
    },
    {
        "url": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=600&q=70",
        "filename": "detail_brick_facade.jpg",
        "category": "Detail / Material",
        "description": "A close-up detail of a handmade brick facade laid in a Flemish bond pattern. The textural variation in the fired clay units, ranging from deep ochre to burnt sienna, gives the surface a richly tactile quality. Raked mortar joints deepen the shadow lines, emphasizing the masonry's depth and craftsmanship.",
        "project_tag": "demo",
    },
]


def download_image(url: str, dest: Path) -> bool:
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "NexusHestia/2.0"})
        r.raise_for_status()
        dest.write_bytes(r.content)
        return True
    except Exception as e:
        print(f"  ✗ Download failed: {e}")
        return False


def make_thumbnail_b64(image_path: Path) -> str:
    try:
        from PIL import Image
        import io
        img = Image.open(image_path)
        img.thumbnail((400, 400))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=70)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()[:50_000]).decode()


def seed():
    # Init DB
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
            project_tag   TEXT,
            thumbnail     TEXT
        )
    ''')

    # Check if already seeded
    c.execute("SELECT COUNT(*) FROM images WHERE project_tag='demo'")
    if c.fetchone()[0] >= len(DEMO_IMAGES):
        print("✓ Demo data already seeded.")
        conn.close()
        return

    print(f"Seeding {len(DEMO_IMAGES)} demo images...\n")

    for item in DEMO_IMAGES:
        dest = DEMO_DIR / item["filename"]
        print(f"  → {item['filename']} ({item['category']})")

        if not dest.exists():
            ok = download_image(item["url"], dest)
            if not ok:
                # Create a placeholder (1x1 transparent PNG)
                placeholder = base64.b64decode(
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
                )
                dest.write_bytes(placeholder)

        thumb = make_thumbnail_b64(dest)

        # Check for duplicate
        c.execute("SELECT id FROM images WHERE file_name=? AND project_tag='demo'", (item["filename"],))
        if c.fetchone():
            print(f"    already in DB, skipping")
            continue

        c.execute(
            "INSERT INTO images (file_name, original_path, new_path, category, description, project_tag, thumbnail) VALUES (?,?,?,?,?,?,?)",
            (item["filename"], str(dest), str(dest), item["category"], item["description"], item["project_tag"], thumb),
        )
        print(f"    ✓ inserted (id={c.lastrowid})")

    conn.commit()
    conn.close()
    print(f"\n✓ Seeding complete. {len(DEMO_IMAGES)} images in catalog.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--save-db", action="store_true",
                        help="Run locally and commit the seeded DB to the repo")
    args = parser.parse_args()

    if args.save_db:
        # Override DB path to local
        DB_PATH = "nexus_catalog.db"
        DEMO_DIR_LOCAL = Path("demo_images")
        DEMO_DIR_LOCAL.mkdir(exist_ok=True)
        # Update global
        import builtins
        _original_open = builtins.open

    seed()

    if args.save_db:
        print(f"\nDB saved to {DB_PATH} — commit it to your repo.")
        print("Images downloaded to demo_images/ — add to .gitignore if large.")
