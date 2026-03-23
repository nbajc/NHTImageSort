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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

def init_db():
    # Database is stored in a local SQLite file
    conn = sqlite3.connect('nexus_catalog.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT,
            original_path TEXT,
            new_path TEXT,
            category TEXT,
            description TEXT,
            project_tag TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Initialize the DB before the server starts
init_db()

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({"status": "idle"})

# Add your other routes here (e.g., /api/start, /api/search)

if __name__ == '__main__':
    # Railway often requires 0.0.0.0 to expose the port
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

# Global state to keep track of sorting progress
job_state = {
    "status": "idle", # idle, running, completed, error
    "current_file": None,
    "description": None,
    "category": None,
    "processed": 0,
    "total": 0,
    "results": [],
    "error": None
}

def sort_images_worker(source_dir, target_dir, categories, vision_model, text_model, extensions, dry_run, project_tag):
    global job_state
    
    try:
        if not os.path.exists(source_dir):
            job_state["error"] = f"Source directory not found: {source_dir}"
            job_state["status"] = "error"
            return

        if not dry_run and not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        job_state["status"] = "running"
        job_state["results"] = []
        job_state["current_file"] = "Initializing agents..."
        
        describer = DescriberAgent(model_name=vision_model)
        sorter = SorterAgent(model_name=text_model, categories=categories)
        
        exts = tuple(f".{ext.lower()}" for ext in extensions)

        # Count total files
        total_files = 0
        for root, _, files in os.walk(source_dir):
            for file in files:
                if file.lower().endswith(exts):
                    total_files += 1
                    
        job_state["total"] = total_files
        job_state["processed"] = 0

        for root, _, files in os.walk(source_dir):
            if job_state["status"] != "running": # Handle manual stop if needed later
                break
                
            for file in files:
                if file.lower().endswith(exts):
                    full_path = os.path.join(root, file)
                    
                    job_state["current_file"] = file
                    job_state["description"] = "Generating description..."
                    job_state["category"] = None
                    
                    # 1. Describe Image
                    description = describer.describe(full_path)
                    
                    if not description:
                        job_state["description"] = "Failed to describe."
                        job_state["processed"] += 1
                        continue
                        
                    if project_tag:
                        description += f"\n\n#{project_tag.strip()}"
                        
                    job_state["description"] = description
                    
                    # 2. Sort Image
                    job_state["category"] = "Determining category..."
                    category = sorter.sort(description)
                    
                    if not category:
                        job_state["category"] = "Failed to sort."
                        job_state["processed"] += 1
                        continue
                        
                    job_state["category"] = category
                    
                    # 3. Move Image
                    project_dir = os.path.join(target_dir, project_tag) if project_tag else target_dir
                    category_dir = os.path.join(project_dir, category)
                    target_path = os.path.join(category_dir, file)
                    
                    moved = False
                    if not dry_run:
                        try:
                            if not os.path.exists(category_dir):
                                os.makedirs(category_dir, exist_ok=True)
                                
                            if os.path.exists(target_path):
                                base, extension = os.path.splitext(file)
                                counter = 1
                                while os.path.exists(target_path):
                                    target_path = os.path.join(category_dir, f"{base}_{counter}{extension}")
                                    counter += 1
                                    
                            shutil.copy2(full_path, target_path) # Changed to copy for safety by default during API runs, or can configure to move
                            
                            desc_path = os.path.splitext(target_path)[0] + ".txt"
                            with open(desc_path, "w", encoding="utf-8") as f:
                                f.write(description)
                            moved = True
                        except Exception as e:
                            print(f"Error copying {file}: {e}")
                    else:
                        moved = True
                    
                    if moved:
                        if not dry_run:
                            try:
                                conn = sqlite3.connect('nexus_catalog.db')
                                c = conn.cursor()
                                c.execute("SELECT id FROM images WHERE original_path=?", (full_path,))
                                row = c.fetchone()
                                if row:
                                    c.execute("""UPDATE images SET new_path=?, category=?, description=?, project_tag=? WHERE id=?""",
                                              (target_path, category, description, project_tag, row[0]))
                                else:
                                    c.execute("""INSERT INTO images (file_name, original_path, new_path, category, description, project_tag) 
                                                 VALUES (?, ?, ?, ?, ?, ?)""", 
                                              (file, full_path, target_path, category, description, project_tag))
                                conn.commit()
                                conn.close()
                            except Exception as e:
                                print(f"DB Error: {e}")

                        job_state["results"].append({
                            "file": file,
                            "original_path": full_path,
                            "new_path": target_path,
                            "category": category,
                            "description": description
                        })
                        
                    job_state["processed"] += 1

        job_state["status"] = "completed"
        job_state["current_file"] = None
        
    except Exception as e:
        job_state["status"] = "error"
        job_state["error"] = str(e)


@app.route("/api/status", methods=["GET"])
def get_status():
    return jsonify(job_state)


@app.route("/api/start", methods=["POST"])
def start_sorting():
    global job_state
    
    if job_state["status"] == "running":
        return jsonify({"error": "A job is already running."}), 400
        
    data = request.json
    source_dir = data.get("source")
    target_dir = data.get("target")
    categories = data.get("categories", [])
    vision_model = data.get("vision_model", "llava")
    text_model = data.get("text_model", "llama3")
    extensions = data.get("extensions", ["jpg", "jpeg", "png", "webp"])
    dry_run = data.get("dry_run", False)
    project_tag = data.get("project_tag", "")
    
    if not source_dir or not target_dir or not categories:
        return jsonify({"error": "Missing required fields: source, target, categories"}), 400
        
    job_state = {
        "status": "starting",
        "current_file": None,
        "description": None,
        "category": None,
        "processed": 0,
        "total": 0,
        "results": [],
        "error": None
    }
    
    # Start thread
    thread = threading.Thread(
        target=sort_images_worker,
        args=(source_dir, target_dir, categories, vision_model, text_model, extensions, dry_run, project_tag)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({"message": "Job started successfully"})

@app.route("/api/results", methods=["GET"])
def get_results():
    if job_state["status"] != "completed":
        return jsonify({"error": "No completed job results available yet."}), 400
    return jsonify({"results": job_state["results"]})

@app.route("/api/search", methods=["GET"])
def search_db():
    query = request.args.get("q", "")
    try:
        conn = sqlite3.connect('nexus_catalog.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        if query:
            search_term = f"%{query}%"
            c.execute("""
                SELECT * FROM images 
                WHERE file_name LIKE ? OR category LIKE ? OR description LIKE ? OR project_tag LIKE ?
                ORDER BY id DESC
            """, (search_term, search_term, search_term, search_term))
        else:
            c.execute("SELECT * FROM images ORDER BY id DESC LIMIT 100")
            
        rows = c.fetchall()
        results = []
        for r in rows:
            results.append({
                "id": r["id"],
                "file": r["file_name"],
                "original_path": r["original_path"],
                "new_path": r["new_path"],
                "category": r["category"],
                "description": r["description"],
                "project_tag": r["project_tag"]
            })
        conn.close()
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/image", methods=["GET"])
def get_image():
    image_path = request.args.get("path")
    if not image_path or not os.path.exists(image_path):
        return jsonify({"error": "Image not found"}), 404
    return send_file(image_path)

@app.route("/api/update_item", methods=["POST"])
def update_item():
    data = request.json
    file_path = data.get("path")
    new_description = data.get("description")
    
    if not file_path or not new_description:
        return jsonify({"error": "Missing path or description"}), 400
        
    try:
        desc_path = os.path.splitext(file_path)[0] + ".txt"
        with open(desc_path, "w", encoding="utf-8") as f:
            f.write(new_description)
            
        import re
        tags = re.findall(r'#([^\s#]+)', new_description)
        conn = sqlite3.connect('nexus_catalog.db')
        c = conn.cursor()
        
        c.execute("SELECT project_tag FROM images WHERE new_path=? OR original_path=? OR file_name=?", (file_path, file_path, file_path))
        row = c.fetchone()
        
        return_tags = None
        if row:
            existing_tags = set([t.strip() for t in str(row[0] or "").split(",") if t.strip()])
            new_tags = set(tags)
            merged_tags = existing_tags.union(new_tags)
            if merged_tags:
                tag_str = ", ".join(sorted(merged_tags))
                c.execute("UPDATE images SET description=?, project_tag=? WHERE new_path=? OR original_path=? OR file_name=?", (new_description, tag_str, file_path, file_path, file_path))
                return_tags = tag_str
            else:
                c.execute("UPDATE images SET description=? WHERE new_path=? OR original_path=? OR file_name=?", (new_description, file_path, file_path, file_path))
        else:
            if tags:
                tag_str = ", ".join(tags)
                c.execute("UPDATE images SET description=?, project_tag=? WHERE new_path=? OR original_path=? OR file_name=?", (new_description, tag_str, file_path, file_path, file_path))
                return_tags = tag_str
            else:
                c.execute("UPDATE images SET description=? WHERE new_path=? OR original_path=? OR file_name=?", (new_description, file_path, file_path, file_path))
            
        conn.commit()
        conn.close()
        
        return jsonify({"message": "Description updated", "project_tag": return_tags})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/delete_item", methods=["POST"])
def delete_item():
    data = request.json
    file_path = data.get("path")
    
    if not file_path:
        return jsonify({"error": "Missing path"}), 400
        
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            
        desc_path = os.path.splitext(file_path)[0] + ".txt"
        if os.path.exists(desc_path):
            os.remove(desc_path)
            
        conn = sqlite3.connect('nexus_catalog.db')
        c = conn.cursor()
        c.execute("DELETE FROM images WHERE new_path=?", (file_path,))
        conn.commit()
        conn.close()
            
        return jsonify({"message": "File and description deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/delete_folder", methods=["POST"])
def delete_folder():
    data = request.json
    folder_path = data.get("path")
    
    if not folder_path:
        return jsonify({"error": "Missing path"}), 400
        
    try:
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            shutil.rmtree(folder_path)
            
            like_path = os.path.join(folder_path, "") + "%"
            conn = sqlite3.connect('nexus_catalog.db')
            c = conn.cursor()
            c.execute("DELETE FROM images WHERE new_path LIKE ?", (like_path,))
            conn.commit()
            conn.close()
            
            return jsonify({"message": "Folder deleted"})
        return jsonify({"error": "Directory not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/remove_doubles", methods=["POST"])
def remove_doubles():
    try:
        conn = sqlite3.connect('nexus_catalog.db')
        c = conn.cursor()
        c.execute("SELECT id, new_path FROM images")
        rows = c.fetchall()
        
        seen_hashes = {}
        removed_count = 0
        
        for row in rows:
            img_id = row[0]
            new_path = row[1]
            
            if not new_path or not os.path.exists(new_path):
                continue
                
            hasher = hashlib.md5()
            with open(new_path, 'rb') as f:
                hasher.update(f.read())
            file_hash = hasher.hexdigest()
            
            if file_hash in seen_hashes:
                preserved_path = seen_hashes[file_hash]
                
                # Only delete the physical file if it's a completely different copy on the disk
                if new_path != preserved_path:
                    try:
                        os.remove(new_path)
                    except Exception as e:
                        print(f"Failed to delete duplicate image {new_path}: {e}")
                        
                    desc_path = os.path.splitext(new_path)[0] + ".txt"
                    if os.path.exists(desc_path):
                        try:
                            os.remove(desc_path)
                        except Exception as e:
                            print(f"Failed to delete description for {desc_path}: {e}")
                
                c.execute("DELETE FROM images WHERE id=?", (img_id,))
                removed_count += 1
            else:
                seen_hashes[file_hash] = new_path
                
        conn.commit()
        conn.close()
        
        return jsonify({"message": f"Successfully cleared {removed_count} exact duplicate images from your catalog!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)
