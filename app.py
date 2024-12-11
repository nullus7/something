import os
import psycopg2
from flask import Flask, request, jsonify
from psycopg2 import sql
import time

app = Flask(__name__)

# Database connection setup
# Correctly fetch the DATABASE_URL environment variable
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:iCjjjBFSqvSGPIGNWMreFQBpFKifJngN@junction.proxy.rlwy.net:53974/railway")

# Establish database connection
try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # Create main table if it doesn't exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS statuses (
        id SERIAL PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL,
        timestamp BIGINT NOT NULL,
        key TEXT NOT NULL
    )
    """)
    
    # Create new table for keys and user IDs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS keys_table (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        key TEXT NOT NULL UNIQUE,
        is_active BOOLEAN DEFAULT TRUE
    )
    """)
    conn.commit()
except Exception as e:
    print(f"Error connecting to the database: {e}")
    conn = None

@app.route("/")
def home():
    if conn:
        return "Welcome to the Status Logger API!"
    else:
        return "Database connection not established. Please check your configuration."

@app.errorhandler(Exception)
def handle_exception(e):
    return jsonify({"error": "An internal error occurred", "details": str(e)}), 500

@app.route("/log_status/<key>", methods=["POST"])
def log_status(key):
    if not conn:
        return jsonify({"error": "Database connection not established"}), 500

    try:
        data = request.get_json()
        username = data.get("username")
        status = data.get("status")
        timestamp = data.get("timestamp")

        # Validate input
        if not username or not status or not timestamp:
            return jsonify({"error": "Invalid data"}), 400

        # Check if the provided key exists and is active in the keys_table
        cursor.execute("SELECT key FROM keys_table WHERE key = %s AND is_active = TRUE", (key,))
        key_result = cursor.fetchone()

        if not key_result:
            return jsonify({"error": "Invalid or inactive key."}), 403

        # Insert or update the user's status
        cursor.execute("""
        INSERT INTO statuses (username, status, timestamp, key)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (username) DO UPDATE
        SET status = EXCLUDED.status, timestamp = EXCLUDED.timestamp, key = EXCLUDED.key
        """, (username, status, timestamp, key))
        conn.commit()

        return jsonify({"message": "Status logged successfully"}), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "An error occurred"}), 500

@app.route("/store_key", methods=["POST"])
def store_key():
    if not conn:
        return jsonify({"error": "Database connection not established"}), 500

    try:
        data = request.get_json()
        user_id = data.get("user_id")
        key = data.get("key")

        # Validate input
        if not user_id or not key:
            return jsonify({"error": "Invalid data"}), 400

        # Insert the key and user_id into the keys_table
        cursor.execute("""
        INSERT INTO keys_table (user_id, key, is_active)
        VALUES (%s, %s, TRUE)
        ON CONFLICT (key) DO NOTHING
        """, (user_id, key))
        conn.commit()

        return jsonify({"message": "Key stored successfully"}), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "An error occurred"}), 500

@app.route("/check_status/<username>", methods=["GET"])
def check_status(username):
    if not conn:
        return jsonify({"error": "Database connection not established"}), 500

    try:
        # Query the latest status of the user
        cursor.execute(
            sql.SQL("SELECT timestamp, key FROM statuses WHERE username = %s ORDER BY id DESC LIMIT 1"),
            (username,)
        )
        result = cursor.fetchone()

        if result:
            last_timestamp, key = result
            current_time = int(time.time())

            # Check if the user is online or offline
            if current_time - last_timestamp < 5:
                return jsonify({"username": username, "status": "online", "key": key}), 200
            else:
                return jsonify({"username": username, "status": "offline", "key": key}), 200
        else:
            return jsonify({"error": "User not found"}), 404

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "An error occurred"}), 500

@app.route("/health", methods=["GET"])
def health_check():
    try:
        if conn:
            cursor.execute("SELECT 1")
            return jsonify({"status": "healthy"}), 200
        else:
            return jsonify({"status": "unhealthy", "error": "No database connection"}), 500
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
