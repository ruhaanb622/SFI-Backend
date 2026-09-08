# SFI Foundation Prototype Backend

This repository contains the Flask API backend for the Greppers SFI Foundation capstone prototype. It supports the SFI frontend with specification search, machine-learning classification, chatbot responses, authentication, and user gear tracking.

The prototype is meant to show how SFI Foundation's public standards and PDF resources could become easier to search, update, and personalize. It is not a production replacement for the official SFI Foundation website.

## Backend Role

The Flask backend provides:

- SFI specification database import and API access.
- Spec search, category, stats, create, edit, and delete endpoints.
- Text-based ML classifier for matching part descriptions to SFI specs.
- Gemini-backed chatbot endpoint for SFI spec questions.
- User authentication and current-user lookup through the existing starter auth system.
- Authenticated "My Gear" storage for user safety equipment.

## Important Files

| Path | Purpose |
| --- | --- |
| `main.py` | Registers Flask blueprints, including all SFI APIs. |
| `api/sfi_spec.py` | SFI spec list/search/CRUD/categories/detect/stats endpoints. |
| `api/sfi_classifier.py` | ML text classifier endpoints. |
| `api/sfi_chat.py` | Gemini-backed chatbot endpoint. |
| `api/user_gear.py` | Authenticated user gear CRUD endpoints. |
| `model/sfi_spec.py` | SQLAlchemy model for SFI specs and import from frontend JSON. |
| `model/sfi_classifier.py` | TF-IDF plus LinearSVC classifier for part/spec prediction. |
| `model/user_gear.py` | SQLAlchemy model for user equipment tracking. |
| `__init__.py` | Flask app setup, CORS, environment config, and database configuration. |

## SFI API Endpoints

Implemented endpoints:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/sfi/specs` | List all specs, with optional `?category=` filter. |
| `POST` | `/api/sfi/specs` | Create a new spec record. Currently not admin-protected. |
| `GET` | `/api/sfi/specs/search?q=...` | Keyword search across spec number, product name, category, and subcategory. |
| `GET` | `/api/sfi/specs/<id>` | Get one spec by ID. |
| `PUT` | `/api/sfi/specs/<id>` | Update one spec by ID. Currently not admin-protected. |
| `DELETE` | `/api/sfi/specs/<id>` | Delete one spec by ID. Currently not admin-protected. |
| `GET` | `/api/sfi/categories` | Return distinct SFI spec categories. |
| `GET` | `/api/sfi/stats` | Return total specs, categories, subcategories, and category counts. |
| `POST` | `/api/sfi/classify` | Classify a free-text part description into likely SFI specs. |
| `GET` | `/api/sfi/classifier/status` | Return classifier training/status metadata. |
| `POST` | `/api/sfi/chat` | Send a chatbot message and receive a Gemini-generated response. |
| `GET` | `/api/sfi/gear` | List current authenticated user's gear. |
| `POST` | `/api/sfi/gear` | Add gear for the current authenticated user. |
| `DELETE` | `/api/sfi/gear/<id>` | Delete one current-user gear item. |

Partially implemented or prototype-only behavior:

- `POST /api/sfi/detect` exists, but it is keyword-based. It is separate from the browser-side detector in the frontend.
- Standalone admin/group endpoints expected by the frontend `/admin/` page are not implemented yet.

## Data Flow

The SFI spec source data lives in the frontend repo:

```text
../greppers/_data/sfi_specs.json
```

`model/sfi_spec.py` imports that JSON into the backend database. `model/sfi_classifier.py` also trains from the same JSON file.

Expected local repo layout:

```text
greppers/
  greppers/   # frontend repo
  flask/      # this backend repo
```

If the frontend repo is not beside this backend repo, SFI spec import and classifier training may fail unless the path logic is updated.

## Local Setup

Create and activate a Python virtual environment:

```bash
python -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a local `.env` file. At minimum, include auth defaults and Gemini settings if the chatbot should work:

```env
DEFAULT_PASSWORD='password'
ADMIN_USER='Admin Name'
ADMIN_UID='admin'
ADMIN_PASSWORD='password'
ADMIN_PFP='default.png'

USER_NAME='User Name'
USER_UID='user'
USER_PASSWORD='password'
USER_PFP='default.png'

GEMINI_API_KEY='your-key-here'
GEMINI_SERVER='https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent'
```

Initialize or refresh the database:

```bash
python scripts/db_init.py
```

Run the backend:

```bash
python main.py
```

The expected local backend base URL is:

```text
http://localhost:8423
```

## Frontend Integration

The companion frontend expects the backend at:

- Local: `http://localhost:8423`
- Deployed: `https://greppers-be.opencodingsociety.com`

The frontend pages that depend on this backend include:

- `/sfi-specs/` for specs, stats, classifier, and spec CRUD.
- `/quiz/` for authenticated gear sync.
- `/login/` and `/signup/` for auth.
- Site-wide chatbot widget for `/api/sfi/chat`.
- `/admin/`, although the required admin endpoints are currently missing.

CORS settings in `__init__.py` include local frontend ports and Open Coding Society domains. If testing from a new origin, update `allowed_origins`.

## Known Gaps

- No implemented admin/group endpoints for the standalone frontend `/admin/` page.
- Spec create, update, and delete endpoints are not currently restricted to admin users.
- Gear API does not support pending, approved, rejected, owner metadata, reviewer notes, or all-user admin views.
- Chatbot does not read PDFs or crawl the website. It only receives compact spec rows from the database.
- No PDF extraction, summarization, vector search, or RAG layer exists yet.
- `/api/sfi/detect` is keyword-based and separate from the frontend's TensorFlow.js image detector.
- There are no focused automated tests for the SFI API endpoints yet.

## Future Roadmap

- Add admin-auth-protected SFI management endpoints.
- Implement `/api/sfi/me`, `/api/sfi/users`, `/api/sfi/groups`, `/api/sfi/gear/pending`, and `/api/sfi/gear/all` or update the frontend admin page to use existing APIs.
- Extend `UserGear` with status, source, owner/admin review fields, reviewer notes, and timestamps.
- Add a PDF ingestion pipeline that downloads or reads SFI PDFs, extracts text, chunks/indexes content, and exposes summary/search endpoints.
- Upgrade the chatbot to retrieve from specs, site pages, and PDF chunks before calling Gemini.
- Add route/API tests for SFI specs, classifier, chat error handling, and gear CRUD.

## Handoff Checklist

Before continuing backend work:

- Confirm `../greppers/_data/sfi_specs.json` exists and is current.
- Run `python scripts/db_init.py`.
- Start the backend and test `GET /api/sfi/specs`.
- Test `GET /api/sfi/classifier/status` to confirm the classifier trained.
- Configure `GEMINI_API_KEY` before testing `POST /api/sfi/chat`.
- Treat the `/admin/` frontend as unfinished until the backend admin endpoints and permission checks are added.
