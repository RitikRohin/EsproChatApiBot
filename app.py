from flask import Flask, request, jsonify
import os, secrets, json
from datetime import datetime, timedelta
import g4f

app = Flask(__name__)
KEY_FILE = "keys.json"

def load_keys():
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "r") as f:
            return json.load(f)
    return {}

def save_keys(keys):
    with open(KEY_FILE, "w") as f:
        json.dump(keys, f, indent=2)

def cleanup_expired_keys():
    keys = load_keys()
    now = datetime.utcnow()
    updated = {k:v for k,v in keys.items() if datetime.fromisoformat(v["expiry"])>now}
    if len(updated)!=len(keys):
        save_keys(updated)
    return updated

def generate_key(days=30):
    key = secrets.token_urlsafe(32)
    expiry = (datetime.utcnow() + timedelta(days=days)).isoformat()
    keys = load_keys()
    keys[key] = {"expiry": expiry}
    save_keys(keys)
    return key, expiry

def check_key(auth):
    keys = cleanup_expired_keys()
    if not auth.startswith("Bearer "):
        return False
    token = auth.split(" ")[1]
    if token not in keys:
        return False
    expiry = datetime.fromisoformat(keys[token]["expiry"])
    return datetime.utcnow() <= expiry

@app.route("/")
def home():
    return jsonify({"message": "G4F API running on Heroku", "endpoints": ["/gen_key", "/v1/chat/completions"]})

@app.route("/gen_key", methods=["POST"])
def gen_key():
    key, expiry = generate_key(30)
    return jsonify({"key": key, "expiry": expiry})

@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    auth = request.headers.get("Authorization", "")
    if not check_key(auth):
        return jsonify({"error": "Invalid or expired API key"}), 401

    data = request.json
    messages = data.get("messages", [])
    model = data.get("model", "gpt-4o-mini")
    try:
        response = g4f.ChatCompletion.create(model=model, messages=messages)
        return jsonify({"choices":[{"message":{"role":"assistant","content":response}}]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
