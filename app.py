import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import mysql.connector
from werkzeug.utils import secure_filename

# -----------------------------------------
# MySQL Config (Back4App will inject ENV)
# -----------------------------------------
DB_CONFIG = {
    "host": os.environ.get("MYSQLHOST"),
    "user": os.environ.get("MYSQLUSER"),
    "password": os.environ.get("MYSQLPASSWORD"),
    "database": os.environ.get("MYSQLDATABASE"),
    "port": int(os.environ.get("MYSQLPORT", 3306))
}

# -----------------------------------------
# Upload Directory
# -----------------------------------------
UPLOAD_DIR = "/app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXT = {"pdf", "png", "jpg", "jpeg"}

# -----------------------------------------
# Flask App
# -----------------------------------------
app = Flask(__name__)
CORS(app)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def get_conn():
    """Create MySQL connection with strong error output"""
    try:
        if not DB_CONFIG["host"]:
            raise Exception("Missing MySQL ENV variables")

        return mysql.connector.connect(**DB_CONFIG)

    except Exception as e:
        print("DB CONNECTION FAILED:", e)
        raise


def row_to_dict(row, cols):
    return {col: row[i] for i, col in enumerate(cols)}


# -----------------------------------------
# ROUTES
# -----------------------------------------

@app.route("/vendors", methods=["GET"])
def get_vendors():
    conn = cursor = None
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
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route("/vendors/<pan>", methods=["GET"])
def get_vendor(pan):
    conn = cursor = None
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vendors WHERE PAN = %s", (pan,))
        row = cursor.fetchone()

        if not row:
            return jsonify({"error": "Vendor not found"}), 404

        cols = [c[0] for c in cursor.description]
        return jsonify(row_to_dict(row, cols))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route("/vendors", methods=["POST"])
def create_vendor():
    data = dict(request.form) or (request.get_json() if request.is_json else {})
    pan = data.get("PAN")

    if not pan:
        return jsonify({"error": "PAN is required"}), 400

    # File handling
    file_fields = [
        "Photo", "Signature", "PAN_Card", "GST_Certificate", "MSME_Certificate",
        "Bank_Proof", "Cancelled_Cheque", "Incorporation_Deed", "Address_Proof"
    ]

    saved = {}

    for fkey in file_fields:
        if fkey in request.files:
            file = request.files[fkey]
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{pan}_{fkey}_{file.filename}")
                file.save(os.path.join(UPLOAD_DIR, filename))
                saved[fkey] = filename
            else:
                return jsonify({"error": f"Invalid file for {fkey}"}), 400

    data.update(saved)

    columns = list(data.keys())
    values = list(data.values())
    placeholders = ", ".join(["%s"] * len(values))
    colnames = ", ".join(columns)

    conn = cursor = None

    try:
        conn = get_conn()
        cursor = conn.cursor()
        sql = f"INSERT INTO vendors ({colnames}) VALUES ({placeholders})"
        cursor.execute(sql, tuple(values))
        conn.commit()
        return jsonify({"message": "Vendor created", "PAN": pan}), 201
    except mysql.connector.IntegrityError:
        return jsonify({"error": "PAN already exists"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route("/vendors/<pan>", methods=["PUT"])
def update_vendor(pan):
    data = dict(request.form) or (request.get_json() if request.is_json else {})

    if not data:
        return jsonify({"error": "No input provided"}), 400

    file_fields = [
        "Photo", "Signature", "PAN_Card", "GST_Certificate", "MSME_Certificate",
        "Bank_Proof", "Cancelled_Cheque", "Incorporation_Deed", "Address_Proof"
    ]

    saved = {}

    for fkey in file_fields:
        if fkey in request.files:
            file = request.files[fkey]
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{pan}_{fkey}_{file.filename}")
                file.save(os.path.join(UPLOAD_DIR, filename))
                saved[fkey] = filename
            else:
                return jsonify({"error": f"Invalid file for {fkey}"}), 400

    data.update(saved)

    set_clause = ", ".join([f"{k}=%s" for k in data])
    values = list(data.values()) + [pan]

    conn = cursor = None

    try:
        conn = get_conn()
        cursor = conn.cursor()
        sql = f"UPDATE vendors SET {set_clause} WHERE PAN=%s"
        cursor.execute(sql, tuple(values))
        conn.commit()
        return jsonify({"message": "Updated", "rows": cursor.rowcount})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route("/vendors/<pan>", methods=["DELETE"])
def delete_vendor(pan):
    conn = cursor = None
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM vendors WHERE PAN=%s", (pan,))
        conn.commit()
        return jsonify({"deleted": cursor.rowcount})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route("/uploads/<filename>")
def serve_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


# -----------------------------------------
# Back4App runs on PORT=8080 always
# -----------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
