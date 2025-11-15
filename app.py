import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# -----------------------------
# Load environment variables
# -----------------------------
load_dotenv()  # For local development only

# -----------------------------
# Cloud MySQL Config (Railway)
# -----------------------------
DB_CONFIG = {
    "host": os.environ["MYSQLHOST"],          # Railway host
    "user": os.environ["MYSQLUSER"],          # Railway DB user
    "password": os.environ["MYSQLPASSWORD"],  # Railway DB password
    "database": os.environ["MYSQLDATABASE"],  # Railway DB name
    "port": int(os.environ.get("MYSQLPORT", 3306))
}

# -----------------------------
# Upload settings
# -----------------------------
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(os.getcwd(), "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_EXT = {"pdf", "png", "jpg", "jpeg"}

# -----------------------------
# Flask app setup
# -----------------------------
app = Flask(__name__)
CORS(app)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

def get_conn():
    """Connect to Railway Cloud MySQL"""
    return mysql.connector.connect(**DB_CONFIG)

def row_to_dict(row, cols):
    return {col: row[idx] for idx, col in enumerate(cols)}

# -----------------------------
# ROUTES
# -----------------------------
@app.route("/vendors", methods=["GET"])
def get_vendors():
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vendors")
        cols = [c[0] for c in cursor.description]
        rows = cursor.fetchall()
        return jsonify([row_to_dict(r, cols) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/vendors/<pan>", methods=["GET"])
def get_vendor(pan):
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vendors WHERE PAN=%s", (pan,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "Vendor not found"}), 404
        cols = [c[0] for c in cursor.description]
        return jsonify(row_to_dict(row, cols))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/vendors", methods=["POST"])
def create_vendor():
    data = dict(request.form) or (request.get_json() if request.is_json else {})
    pan = data.get("PAN")
    if not pan:
        return jsonify({"error": "PAN is required"}), 400

    # Handle files
    file_fields = [
        "Photo","Signature","PAN_Card","GST_Certificate","MSME_Certificate",
        "Bank_Proof","Cancelled_Cheque","Incorporation_Deed","Address_Proof"
    ]
    saved = {}
    for fkey in file_fields:
        if fkey in request.files:
            f = request.files[fkey]
            if f and allowed_file(f.filename):
                filename = secure_filename(f"{pan}_{fkey}_{f.filename}")
                f.save(os.path.join(UPLOAD_DIR, filename))
                saved[fkey] = filename
            else:
                return jsonify({"error": f"Invalid file for {fkey}"}), 400
    data.update(saved)

    columns = list(data.keys())
    vals = list(data.values())
    if "PAN" not in columns:
        columns.append("PAN")
        vals.append(pan)

    placeholders = ", ".join(["%s"] * len(vals))
    colnames = ", ".join(columns)

    try:
        conn = get_conn()
        cursor = conn.cursor()
        sql = f"INSERT INTO vendors ({colnames}) VALUES ({placeholders})"
        cursor.execute(sql, tuple(vals))
        conn.commit()
        return jsonify({"message": "Vendor created", "PAN": pan}), 201
    except mysql.connector.IntegrityError as e:
        return jsonify({"error": "PAN already exists", "detail": str(e)}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/vendors/<pan>", methods=["PUT"])
def update_vendor(pan):
    data = dict(request.form) or (request.get_json() if request.is_json else {})
    if not data:
        return jsonify({"error": "No payload provided"}), 400

    file_fields = [
        "Photo","Signature","PAN_Card","GST_Certificate","MSME_Certificate",
        "Bank_Proof","Cancelled_Cheque","Incorporation_Deed","Address_Proof"
    ]
    saved = {}
    for fkey in file_fields:
        if fkey in request.files:
            f = request.files[fkey]
            if f and allowed_file(f.filename):
                filename = secure_filename(f"{pan}_{fkey}_{f.filename}")
                f.save(os.path.join(UPLOAD_DIR, filename))
                saved[fkey] = filename
            else:
                return jsonify({"error": f"Invalid file for {fkey}"}), 400
    data.update(saved)

    sets = ", ".join([f"{k}=%s" for k in data.keys()])
    vals = list(data.values()) + [pan]
    try:
        conn = get_conn()
        cursor = conn.cursor()
        sql = f"UPDATE vendors SET {sets} WHERE PAN=%s"
        cursor.execute(sql, tuple(vals))
        conn.commit()
        return jsonify({"message": "Updated", "rows": cursor.rowcount})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/vendors/<pan>", methods=["DELETE"])
def delete_vendor(pan):
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM vendors WHERE PAN=%s", (pan,))
        conn.commit()
        return jsonify({"deleted": cursor.rowcount})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/uploads/<filename>", methods=["GET"])
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)

# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
