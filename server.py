#!/usr/bin/env python3
import http.server
from flask import Flask, jsonify, request
import psycopg2
import os
import shutil
from handler import Handler

app = Flask(__name__)

def connect_db():
 return psycopg2.connect(dbname="basedb", user="nikola", host="localhost")

@app.route("/api/v1/dirs", methods=["GET"])
def dirs():
 conn = connect_db()
 cur = conn.cursor()
 cur.execute("SELECT var_name, path, title, description FROM dirs")
 rows = cur.fetchall()
 cur.close()
 conn.close()
 return jsonify([{"var_name": r[0], "path": r[1], "title": r[2], "description": r[3]} for r in rows])

@app.route("/api/v1/dirs", methods=["POST"])
def create_dir():
 data = request.get_json() or {}
 var_name = data.get("var_name")
 title = data.get("title", var_name)  # Default to var_name if title not provided
 description = data.get("description", "")
 dirpath = data.get("dirpath", "")  # Optional subdirectory under /base
 if not var_name:
  return jsonify({"error": "var_name is required"}), 400

 # Construct the path
 base_path = "/base"
 path = os.path.join(base_path, dirpath).replace("\\", "/")
 # Create the directory
 try:
  os.makedirs(path, exist_ok=True)  # Creates parent dirs if needed, skips if exists
 except Exception as e:
  return jsonify({"error": f"Failed to create directory: {str(e)}"}), 500

 # Insert into database
 try:
  conn = connect_db()
  cur = conn.cursor()
  cur.execute("SELECT 1 FROM dirs WHERE var_name = %s", (var_name.upper(),))
  if (cur.fetchone()):
   return jsonify({"error": f"var_name '{var_name}' already exists"}), 409
  cur.execute("SELECT var_name FROM dirs WHERE path = %s", (path,))
  existing = cur.fetchone()
  if existing:
   return jsonify({"error": f"path '{path}' is already mapped to var_name '{existing[0]}'"}), 409
  cur.execute(
   "INSERT INTO dirs (var_name, path, title, description) VALUES (%s, %s, %s, %s) ON CONFLICT (var_name) DO NOTHING",
   (var_name.upper(), path, title, description)  # Uppercase var_name for consistency
  )
  conn.commit()
 except psycopg2.Error as e:
  conn.rollback()
  return jsonify({"error": f"Database error: {str(e)}"}), 500
 finally:
  cur.close()
  conn.close()
 return jsonify({"var_name": var_name, "path": path, "title": title, "description": description}), 201

@app.route("/api/v1/dirs/<var_name>", methods=["DELETE"])
def delete_dir(var_name):
 mode = request.args.get("mode", "fail")  # Default to "fail" if not provided
 if mode not in ["fail", "non_recursive", "recursive"]:
  return jsonify({"error": f"Invalid mode '{mode}'. Use 'fail', 'non_recursive', or 'recursive'"}), 400

 try:
  conn = connect_db()
  # Fetch the path from the database
  try:
   cur = conn.cursor()
   cur.execute("SELECT path FROM dirs WHERE var_name = %s", (var_name.upper(),))
   result = cur.fetchone()
   if not result:
    return jsonify({"error": f"var_name '{var_name}' not found"}), 404
   path = result[0]
  except psycopg2.Error as e:
   return jsonify({"error": f"Database error: {str(e)}"}), 500

  # Handle directory deletion based on mode
  try:
   if os.path.exists(path):
    if mode == "fail":
     if os.listdir(path):  # Check if directory is non-empty
      return jsonify({"error": f"Directory '{path}' is not empty"}), 409
     os.rmdir(path)  # Only works on empty dirs
    elif mode == "non_recursive":
     for item in os.listdir(path):
      item_path = os.path.join(path, item)
      if os.path.isdir(item_path):
       return jsonify({"error": f"Directory '{path}' contains subdirectories"}), 409
      os.unlink(item_path)  # Delete files only
     os.rmdir(path)  # Remove the now-empty dir
    elif mode == "recursive":
        shutil.rmtree(path)  # Delete everything recursively
   # If dir doesn’t exist, proceed to DB cleanup
  except Exception as e:
   return jsonify({"error": f"Failed to delete directory: {str(e)}"}), 500

  # Delete from database
  try:
   cur.execute("DELETE FROM dirs WHERE var_name = %s", (var_name.upper(),))
   if mode == "recursive":
    # Delete any entries with paths starting with this path
    cur.execute("DELETE FROM dirs WHERE path LIKE %s", (f"{path}/%",))
   conn.commit()
  except psycopg2.Error as e:
   conn.rollback()
   return jsonify({"error": f"Database error: {str(e)}"}), 500
  return jsonify({"message": f"Deleted '{var_name}' and its path '{path}'"}), 200
 finally:
  cur.close()
  conn.close()

@app.route("/api/v1/path/<var_name>", methods=["GET"])
def path(var_name):
 conn = connect_db()
 cur = conn.cursor()
 cur.execute("SELECT path FROM dirs WHERE var_name = %s", (var_name,))
 result = cur.fetchone()
 cur.close()
 conn.close()
 path = result[0] if result else None
 return jsonify({"path": path}) if path else ("Not found", 404)

if __name__ == "__main__":
 os.chdir("/opt/desktop-buttons")
 server = http.server.HTTPServer(("", 8000), Handler)
 server.app = app
 print("Serving on http://localhost:8000")
 server.serve_forever()
