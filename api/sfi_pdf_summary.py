"""
=============================================================================
SFI PDF SUMMARY API - Gemini-backed PDF Summarization
=============================================================================
Summarizes SFI motorsport safety documents using Google's Gemini API. The
frontend extracts the PDF text client-side and posts it here; this endpoint
proxies the summarization request through the backend so the Gemini API key
is never exposed to the browser.

SETUP REQUIRED:
1. Get an API key from: https://aistudio.google.com/app/apikey
2. Add to your .env file:
   GEMINI_API_KEY=your_key_here
   GEMINI_SERVER=https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent

ENDPOINTS PROVIDED:
- POST /api/sfi/pdf-summary  - Summarize extracted PDF text

AUTHENTICATION:
All endpoints require authentication via token (uses @token_required decorator).

DEFAULT BEHAVIOR:
- Produces a one-line TL;DR plus 4-6 bullet points of key facts
- Overly long text is truncated to ~30000 chars before sending to Gemini
- 90 second timeout for API requests

RESPONSE FORMAT:
    Success: { "success": true, "summary": "generated summary", "filename": "doc.pdf" }
    Error:   { "message": "error description", "error_code": 500 }

ERROR CODES:
- 400: Bad request (missing text field or invalid input)
- 429: Rate limit exceeded
- 500: Server error or API configuration issue
- 503: Gemini API temporarily unavailable
=============================================================================
"""
from __init__ import app
from flask import Blueprint, request, jsonify, current_app, g
from flask_restful import Api, Resource
import requests
from api.authorize import token_required

# =============================================================================
# BLUEPRINT SETUP
# =============================================================================

sfi_pdf_summary_api = Blueprint('sfi_pdf_summary_api', __name__, url_prefix='/api')
api = Api(sfi_pdf_summary_api)

# =============================================================================
# ENDPOINTS
# =============================================================================

class SfiPdfSummaryAPI:
    class _Summarize(Resource):
        """
        PDF summarization endpoint - POST /api/sfi/pdf-summary
        Summarizes extracted SFI document text via the Gemini API.
        """
        @token_required()
        def post(self):
            """
            Summarize the supplied PDF text.

            Expected JSON body:
            {
                "filename": "spec_38.1.pdf",
                "text": "Extracted PDF text..."
            }

            Returns:
                JSON summary response from Gemini API or error message
            """
            current_user = g.current_user
            body = request.get_json()

            # Validate request body
            if not body:
                return {'message': 'Request body is required'}, 400

            text = body.get('text', '')
            if not text:
                return {'message': 'Text field is required'}, 400

            filename = body.get('filename', 'document')

            # Truncate overly long text before building the payload
            if len(text) > 30000:
                text = text[:30000]

            # Get configuration
            api_key = app.config.get('GEMINI_API_KEY')
            server = app.config.get('GEMINI_SERVER')

            if not api_key:
                return {'message': 'Gemini API key not configured'}, 500

            if not server:
                return {'message': 'Gemini server not configured'}, 500

            # Pass the API key via header (never embed it in the URL, so it
            # cannot leak into request logs or error details).
            endpoint = server

            # Summarization prompt
            prompt = (
                f"You are summarizing an SFI motorsport safety document. "
                f"Provide a one-line TL;DR, then 4-6 concise bullet points of the "
                f"key facts (spec numbers, dates, scope, who is affected). "
                f"Document name: {filename}."
            )

            # Prepare the request payload for Gemini API
            payload = {
                "contents": [{
                    "parts": [{
                        "text": f"{prompt}\n\n{text}"
                    }]
                }]
            }

            # Log the request for auditing purposes
            current_app.logger.info(f"User {current_user.uid} requested PDF summary for {filename}")

            try:
                # Log without the endpoint/key (avoid leaking secrets to logs)
                current_app.logger.info("Making request to Gemini API")

                # Make request to Gemini API. The key is sent as a header so it
                # never appears in any logged URL.
                response = requests.post(
                    endpoint,
                    headers={
                        'Content-Type': 'application/json',
                        'x-goog-api-key': api_key,
                    },
                    json=payload,
                    timeout=90  # 90 second timeout
                )

                # Check if the request was successful
                if response.status_code != 200:
                    error_details = {
                        'status_code': response.status_code,
                        'response_text': response.text,
                    }
                    current_app.logger.error(f"Gemini API error: {error_details}")

                    # Handle specific error codes
                    if response.status_code == 503:
                        return {
                            'message': 'Gemini API is temporarily unavailable (503). Please try again later.',
                            'error_code': 503,
                            'details': 'The service may be overloaded or under maintenance.'
                        }, 503
                    elif response.status_code == 429:
                        return {
                            'message': 'Rate limit exceeded. Please try again later.',
                            'error_code': 429
                        }, 429
                    elif response.status_code == 400:
                        return {
                            'message': 'Bad request to Gemini API. Please check your input.',
                            'error_code': 400,
                            'details': response.text
                        }, 400
                    else:
                        return {
                            'message': f'Gemini API error: {response.status_code}',
                            'error_code': response.status_code,
                            'details': response.text
                        }, 500

                # Parse the response
                result = response.json()

                # Extract the generated text
                try:
                    generated_text = result['candidates'][0]['content']['parts'][0]['text']
                    return {
                        'success': True,
                        'summary': generated_text,
                        'filename': filename
                    }
                except (KeyError, IndexError) as e:
                    current_app.logger.error(f"Error parsing Gemini response: {e}")
                    return {
                        'success': False,
                        'message': 'Error parsing Gemini API response',
                        'raw_response': result
                    }, 500

            except requests.RequestException as e:
                current_app.logger.error(f"Error communicating with Gemini API: {e}")
                return {'message': f'Error communicating with Gemini API: {str(e)}'}, 500
            except Exception as e:
                current_app.logger.error(f"Unexpected error in PDF summary API: {e}")
                return {'message': f'Unexpected error: {str(e)}'}, 500

    # Register all endpoints
    api.add_resource(_Summarize, '/sfi/pdf-summary')  # PDF summarization endpoint
