"""
server.py — Flask backend bridging the web UI to the FlashMind agent.
"""
import os

from flask import Flask, jsonify, request, send_from_directory

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from agent import FlashcardAgent

app = Flask(__name__, static_folder=".")

# Singleton agent (keeps memory across web chat turns)
_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = FlashcardAgent()
    return _agent


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    message = (request.json or {}).get("message", "").strip()
    if not message:
        return jsonify({"error": "Empty message"}), 400
    try:
        agent = get_agent()
        response = agent.chat(message, verbose=True)
        return jsonify({"response": response, "steps": list(agent.step_log),
                        "provider": agent.provider, "model": agent.model})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reset", methods=["POST"])
def reset():
    if _agent is not None:
        _agent.reset()
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"FlashMind running at http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
