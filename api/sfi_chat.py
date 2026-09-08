"""
SFI Chatbot API — Gemini-powered assistant for SFI spec questions.

Endpoints:
    POST /api/sfi/chat — send a message, get a contextual response
"""

from flask import Blueprint, request, jsonify
from flask_restful import Api, Resource
from __init__ import app, db
from model.sfi_spec import SfiSpec
import requests as http_requests

sfi_chat_api = Blueprint('sfi_chat_api', __name__, url_prefix='/api/sfi')
api = Api(sfi_chat_api)

# Build a compact spec summary for the system prompt (cached once)
_spec_context_cache = None

def _build_spec_context():
    global _spec_context_cache
    if _spec_context_cache:
        return _spec_context_cache

    try:
        specs = SfiSpec.query.all()
        lines = []
        for s in specs:
            lines.append(f"SFI {s.spec_number}: {s.product_name} [{s.category}]")
        _spec_context_cache = "\n".join(lines)
    except Exception:
        _spec_context_cache = ""
    return _spec_context_cache


SYSTEM_PROMPT = """\
You are the SFI Safety Specs Assistant, an expert on SFI Foundation motorsport safety specifications.
You help users find the right safety spec for their car parts, understand certification requirements,
and navigate the SFI spec database. Be concise, friendly, and accurate.

If a user asks about a specific part, match it to the most relevant SFI spec(s).
If you're unsure, say so — never fabricate spec numbers.

Here is the full SFI spec database for reference:
{specs}

Key categories: Auto Racing, Drag Racing, Boat Racing, Personal Protective Gear/Restraints/Nets,
Chassis, Fuel Related, Tractor Pulling. Each spec has a number (e.g. SFI 1.1), product name,
category, and links to PDF documentation on sfifoundation.com.

Keep answers short (2-4 sentences) unless the user asks for detail.\
"""


class SfiChatAPI:

    class _Chat(Resource):
        """POST /api/sfi/chat"""

        def post(self):
            api_key = app.config.get('GEMINI_API_KEY')
            server = app.config.get('GEMINI_SERVER')

            if not api_key or not server:
                return {"error": "Gemini API not configured"}, 503

            body = request.get_json()
            if not body or not body.get('message', '').strip():
                return {"error": "Missing 'message' field"}, 400

            user_message = body['message'].strip()
            history = body.get('history', [])

            # Build conversation contents for Gemini
            spec_context = _build_spec_context()
            system_text = SYSTEM_PROMPT.format(specs=spec_context)

            contents = []

            # System context as a user turn
            contents.append({
                "role": "user",
                "parts": [{"text": system_text}]
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "Understood. I'm the SFI Safety Specs Assistant. How can I help you with motorsport safety specifications?"}]
            })

            # Conversation history
            for msg in history[-10:]:  # keep last 10 turns
                role = "user" if msg.get("role") == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": msg.get("text", "")}]
                })

            # Current user message
            contents.append({
                "role": "user",
                "parts": [{"text": user_message}]
            })

            # Send the key as a header so it never appears in a logged URL.
            payload = {"contents": contents}

            try:
                resp = http_requests.post(
                    server,
                    headers={
                        "Content-Type": "application/json",
                        "x-goog-api-key": api_key,
                    },
                    json=payload,
                    timeout=30
                )

                if resp.status_code != 200:
                    return {"error": f"Gemini API returned {resp.status_code}"}, 502

                result = resp.json()
                reply = result["candidates"][0]["content"]["parts"][0]["text"]
                return jsonify({"reply": reply})

            except http_requests.Timeout:
                return {"error": "Gemini API timed out"}, 504
            except Exception as e:
                return {"error": str(e)}, 500

    api.add_resource(_Chat, '/chat')
