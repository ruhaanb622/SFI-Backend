# SFI Safety Hub

This branch extends the existing SFI specification and user-gear stack rather than creating a separate application.

## Features

- **Spec Compass** — explainable, intent-based matching against the existing SFI specification database.
- **QR Participation Checker** — short-lived signed event/gear manifests with live gear-status re-checking at verification time.
- **Trackside Inspector Mode** — permission-gated inspection checklist records for existing gear.
- **Gear Timeline** — certification, moderation, inspection, and follow-up events in chronological order.
- **Manufacturer Review Portal** — evidence submissions with reviewer decisions and notes.
- **Safety Learning Hub** — public learning modules with authenticated per-user completion progress.

## Deployment configuration

Set a strong server-only environment variable before enabling participation credentials:

```bash
SFI_QR_SECRET=<random secret of at least 24 characters>
```

Do not expose this value in the frontend or Jekyll configuration. The API deliberately returns `503` for credential issue/verification when a sufficiently long secret is not configured.

The new persistence models are imported through `api.sfi_spec` before the application's existing `db.create_all()` startup path runs, so fresh installations create the new tables with the rest of the SQLAlchemy models. Existing production databases should continue to use the repository's Flask-Migrate/Alembic workflow when schema changes are promoted.

## API surface

| Endpoint | Method | Authentication | Purpose |
| --- | --- | --- | --- |
| `/api/sfi/compass` | POST | Public | Rank likely specs and explain match reasons |
| `/api/sfi/participation/issue` | POST | Signed-in user | Sign an event/gear manifest |
| `/api/sfi/participation/verify` | POST | Public | Verify signature and current gear status |
| `/api/sfi/inspections` | GET | Signed-in user/reviewer | Read inspection history in allowed scope |
| `/api/sfi/inspections` | POST | `can_approve_gear` | Record a trackside inspection |
| `/api/sfi/timeline` | GET | Signed-in user/reviewer | Read gear lifecycle events |
| `/api/sfi/manufacturer-reviews` | GET/POST | Signed-in user | Track or submit evidence reviews |
| `/api/sfi/manufacturer-reviews/<id>` | PATCH | `can_approve_gear` | Record a review decision |
| `/api/sfi/learning/modules` | GET | Public | Read curated learning modules |
| `/api/sfi/learning/progress` | GET/PUT | Signed-in user | Read or update personal progress |

The existing `/api/sfi/specs`, `/api/sfi/specs/search`, and `/api/sfi/detect` flows remain in place. Search/detection inputs and result counts are now bounded and ordered deterministically, while specification mutations require an administrator.

## Safety semantics

Safety Hub is a workflow aid, not an independent certification authority. In particular:

- Compass results identify likely specifications; users still need to confirm applicability against official SFI and event requirements.
- A valid participation signature proves that this application issued the manifest. It does not itself establish event eligibility.
- `eligible` reflects current application gear moderation status for a complete manifest, not compliance with every sanctioning-body rule.
- Timeline follow-up dates are planning reminders and are not an official recertification determination.

## Smoke test

From the backend repository root:

```bash
python -m unittest testing.test_sfi_safety
```

The smoke suite checks helper validation, server-secret handling, learning-module IDs, and registration of the new routes on the existing `/api/sfi` blueprint without requiring seeded production data.
