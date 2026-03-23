import os
import threading
import shutil
import sqlite3
import hashlib
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from agents import DescriberAgent, SorterAgent

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# --- DYNAMIC PATH SETUP ---
# This finds the folder where app.py lives (the root of your repo)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Define cloud-friendly paths
DB_PATH = os.path.join(BASE_DIR, 'nexus_catalog.db')
# These match the folders you created in GitHub
DEFAULT_SOURCE = os.path.join(BASE_DIR, 'test_images')
DEFAULT_TARGET = os.path.join(BASE_DIR, 'sorted_images')

# Ensure directories exist so the app doesn't crash on startup
os.makedirs(DEFAULT_SOURCE, exist_ok=True)
os.makedirs(DEFAULT_TARGET, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT, original_path TEXT, new_path TEXT,
            category TEXT, description TEXT, project_tag TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Global state to keep track of sorting progress
job_state = {
    "status": "idle", "current_file": None, "description": None,
    "category": None, "processed": 0, "total": 0, "results": [], "error": None
}

def sort_images_worker(source_dir, target_dir, categories, vision_model, text_model, extensions, dry_run, project_tag):
    global job_state
    try:
        # Check if source exists; if user left it blank, use our DEFAULT_SOURCE
        effective_source = source_dir if source_dir and os.path.exists(source_dir) else DEFAULT_SOURCE
        effective_target = target_dir if target_dir else DEFAULT_TARGET

        if not os.path.exists(effective_source):
            job_state["error"] = f"Source directory not found: {effective_source}"
            job_state["status"] = "error"
            return

        os.makedirs(effective_target, exist_ok=True)

        job_state["status"] = "running"
        job_state["results"] = []
        
        describer = DescriberAgent(model_name=vision_model)
        sorter = SorterAgent(model_name=text_model, categories=categories)
        exts = tuple(f".{ext.lower()}" for ext in extensions)

        # Count files
        total_files = sum(1 for root, _, files in os.walk(effective_source) for f in files if f.lower().endswith(exts))
        job_state["total"] = total_files
        job_state["processed"] = 0

        for root, _, files in os.walk(effective_source):
            for file in files:
                if file.lower().endswith(exts):
                    full_path = os.path.join(root, file)
                    job_state["current_file"] = file
                    
                    description = describer.describe(full_path)
                    if not description: continue
                        
                    category = sorter.sort(description)
                    if not category: continue
                    
                    # Target Logic
                    category_dir = os.path.join(effective_target, category)
                    os.makedirs(category_dir, exist_ok=True)
                    target_path = os.path.join(category_dir, file)
                    
                    if not dry_run:
                        shutil.copy2(full_path, target_path)
                        # DB Update
                        conn = sqlite3.connect(DB_PATH)
                        c = conn.cursor()
                        c.execute("INSERT INTO images (file_name, original_path, new_path, category, description) VALUES (?,?,?,?,?)",
                                 (file, full_path, target_path, category, description))
                        conn.commit()
                        conn.close()

                    job_state["results"].append({"file": file, "category": category})
                    job_state["processed"] += 1

        job_state["status"] = "completed"
    except Exception as e:
        job_state["status"] = "error"
        job_state["error"] = str(e)

@app.route("/api/status", methods=["GET"])
def get_status(): return jsonify(job_state)

@app.route("/api/start", methods=["POST"])
def start_sorting():
    global job_state
    data = request.json
    # If the user input is a C:\ path, we override it with our Cloud path
    source = data.get("source")
    if source and ":" in source: source = DEFAULT_SOURCE
    
    target = data.get("target")
    if target and ":" in target: target = DEFAULT_TARGET

    thread = threading.Thread(target=sort_images_worker, args=(source, target, data.get("categories", []), 
                              data.get("vision_model"), data.get("text_model"), ["jpg","png"], False, ""))
    thread.start()
    return jsonify({"message": "Job started using cloud paths"})

# ... (Keep your other API routes like /api/search exactly as they were) ...

if __name__ == '__main__':
    # Force Railway to recognize the port
    raw_port = os.environ.get("PORT", 5000)
    port = int(raw_port)
    
    # We MUST use the dynamic port variable here
    print(f"Starting server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
