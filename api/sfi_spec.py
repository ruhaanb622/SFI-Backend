"""SFI specification API.

Provides CRUD, bounded/deterministic search, visual part detection, stats, and
registers the integrated safety-hub resources on the same ``/api/sfi``
blueprint.
"""

from flask import Blueprint, g, jsonify, request
from flask_restful import Api, Resource
from sqlalchemy import func, or_

from __init__ import db
from api.authorize import token_required
from model.group import user_is_admin
from model.sfi_spec import SfiSpec


sfi_spec_api = Blueprint("sfi_spec_api", __name__, url_prefix="/api/sfi")
api = Api(sfi_spec_api)

MAX_QUERY_LENGTH = 300
MAX_SEARCH_RESULTS = 200
MAX_DETECT_KEYWORDS = 20
MAX_KEYWORD_LENGTH = 80


def _clean(value, max_len=MAX_QUERY_LENGTH):
    return str(value or "").strip()[:max_len]


def _parse_limit(default=100, maximum=MAX_SEARCH_RESULTS):
    raw = request.args.get("limit")
    if raw in (None, ""):
        return default, None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None, ({"error": "limit must be an integer"}, 400)
    return max(1, min(value, maximum)), None


def _ordered(query):
    return query.order_by(
        SfiSpec.spec_number.asc(),
        SfiSpec.product_name.asc(),
        SfiSpec.id.asc(),
    )


def _admin_required():
    if not user_is_admin(g.current_user):
        return {"error": "administrator permission required"}, 403
    return None


class SfiSpecAPI:
    """API resources for SFI spec CRUD, search, detection, and stats."""

    class _Search(Resource):
        """GET /api/sfi/specs/search?q=<keyword>&category=<name>&limit=<n>."""

        def get(self):
            query = _clean(request.args.get("q"))
            category = _clean(request.args.get("category"), 120)
            if not query:
                return {"error": "Missing 'q' query parameter"}, 400

            limit, error = _parse_limit(default=100)
            if error:
                return error

            keyword = f"%{query}%"
            q = SfiSpec.query.filter(or_(
                SfiSpec.product_name.ilike(keyword),
                SfiSpec.spec_number.ilike(keyword),
                SfiSpec.category.ilike(keyword),
                SfiSpec.subcategory.ilike(keyword),
            ))
            if category:
                q = q.filter(SfiSpec.category.ilike(f"%{category}%"))

            results = _ordered(q).limit(limit).all()
            return jsonify([spec.to_dict() for spec in results])

    class _ListCreate(Resource):
        """GET /api/sfi/specs and POST /api/sfi/specs."""

        def get(self):
            category = _clean(request.args.get("category"), 120)
            q = SfiSpec.query
            if category:
                q = q.filter(SfiSpec.category.ilike(f"%{category}%"))
            q = _ordered(q)

            raw_limit = request.args.get("limit")
            if raw_limit not in (None, ""):
                limit, error = _parse_limit(default=MAX_SEARCH_RESULTS)
                if error:
                    return error
                q = q.limit(limit)

            return jsonify([spec.to_dict() for spec in q.all()])

        @token_required()
        def post(self):
            error = _admin_required()
            if error:
                return error

            data = request.get_json(silent=True) or {}
            required = ["product_name", "category", "spec_number"]
            missing = [field for field in required if not _clean(data.get(field))]
            if missing:
                return {"error": f"Missing required fields: {', '.join(missing)}"}, 400

            spec = SfiSpec(
                product_name=_clean(data.get("product_name"), 255),
                category=_clean(data.get("category"), 120),
                subcategory=_clean(data.get("subcategory"), 120),
                spec_number=_clean(data.get("spec_number"), 80),
                spec_pdf=_clean(data.get("spec_pdf"), 1000),
                manufacturer_pdf=_clean(data.get("manufacturer_pdf"), 1000),
                products_pdf=_clean(data.get("products_pdf"), 1000),
                effective_date=_clean(data.get("effective_date"), 40),
            )
            db.session.add(spec)
            db.session.commit()
            return spec.to_dict(), 201

    class _DetailUpdateDelete(Resource):
        """Single-spec operations by ID."""

        def get(self, id):
            spec = SfiSpec.query.get(id)
            if not spec:
                return {"error": "Spec not found"}, 404
            return jsonify(spec.to_dict())

        @token_required()
        def put(self, id):
            error = _admin_required()
            if error:
                return error

            spec = SfiSpec.query.get(id)
            if not spec:
                return {"error": "Spec not found"}, 404

            data = request.get_json(silent=True) or {}
            if not data:
                return {"error": "Missing JSON body"}, 400

            field_lengths = {
                "product_name": 255,
                "category": 120,
                "subcategory": 120,
                "spec_number": 80,
                "spec_pdf": 1000,
                "manufacturer_pdf": 1000,
                "products_pdf": 1000,
                "effective_date": 40,
            }
            for field, max_len in field_lengths.items():
                if field in data:
                    setattr(spec, field, _clean(data.get(field), max_len))

            if not spec.product_name or not spec.category or not spec.spec_number:
                return {"error": "product_name, category, and spec_number cannot be empty"}, 400

            db.session.commit()
            return jsonify(spec.to_dict())

        @token_required()
        def delete(self, id):
            error = _admin_required()
            if error:
                return error

            spec = SfiSpec.query.get(id)
            if not spec:
                return {"error": "Spec not found"}, 404

            db.session.delete(spec)
            db.session.commit()
            return {"message": "Spec deleted"}, 200

    class _Categories(Resource):
        def get(self):
            rows = (
                SfiSpec.query.with_entities(SfiSpec.category)
                .filter(SfiSpec.category.isnot(None))
                .distinct()
                .order_by(SfiSpec.category.asc())
                .all()
            )
            return jsonify([row.category for row in rows if row.category])

    class _Detect(Resource):
        """POST /api/sfi/detect with a keyword string or keyword array."""

        def post(self):
            mode = _clean(request.args.get("mode"), 20).lower()
            data = request.get_json(silent=True) or {}
            if "keywords" not in data:
                return {"error": "Missing 'keywords' in request body"}, 400

            raw_keywords = data.get("keywords")
            if mode == "ml":
                from model.sfi_classifier import SfiClassifier

                if isinstance(raw_keywords, list):
                    raw_keywords = ", ".join(
                        _clean(item, MAX_KEYWORD_LENGTH)
                        for item in raw_keywords[:MAX_DETECT_KEYWORDS]
                        if _clean(item, MAX_KEYWORD_LENGTH)
                    )
                raw_keywords = _clean(raw_keywords, MAX_QUERY_LENGTH)
                if not raw_keywords:
                    return {"error": "Empty keywords"}, 400
                classifier = SfiClassifier.get_instance()
                return jsonify(classifier.predict(raw_keywords))

            if isinstance(raw_keywords, str):
                keywords = [
                    _clean(item, MAX_KEYWORD_LENGTH)
                    for item in raw_keywords.split(",")
                    if _clean(item, MAX_KEYWORD_LENGTH)
                ]
            elif isinstance(raw_keywords, list):
                keywords = [
                    _clean(item, MAX_KEYWORD_LENGTH)
                    for item in raw_keywords
                    if _clean(item, MAX_KEYWORD_LENGTH)
                ]
            else:
                return {"error": "keywords must be a string or list"}, 400

            keywords = list(dict.fromkeys(keywords))[:MAX_DETECT_KEYWORDS]
            if not keywords:
                return {"error": "Empty keywords"}, 400

            filters = []
            for keyword in keywords:
                like = f"%{keyword}%"
                filters.extend([
                    SfiSpec.product_name.ilike(like),
                    SfiSpec.spec_number.ilike(like),
                    SfiSpec.category.ilike(like),
                    SfiSpec.subcategory.ilike(like),
                ])

            limit, error = _parse_limit(default=100)
            if error:
                return error

            results = _ordered(SfiSpec.query.filter(or_(*filters))).limit(MAX_SEARCH_RESULTS).all()
            scored = []
            for spec in results:
                haystack = " ".join([
                    spec.product_name or "",
                    spec.spec_number or "",
                    spec.category or "",
                    spec.subcategory or "",
                ]).lower()
                score = sum(1 for keyword in keywords if keyword.lower() in haystack)
                scored.append((score, spec))

            scored.sort(key=lambda item: (
                -item[0],
                (item[1].spec_number or "").lower(),
                (item[1].product_name or "").lower(),
            ))
            scored = scored[:limit]

            return jsonify({
                "keywords_used": keywords,
                "results": [spec.to_dict() for _, spec in scored],
                "count": len(scored),
            })

    class _Stats(Resource):
        def get(self):
            total = SfiSpec.query.count()
            categories = (
                SfiSpec.query.with_entities(SfiSpec.category)
                .filter(SfiSpec.category.isnot(None))
                .distinct()
                .count()
            )
            subcategories = (
                SfiSpec.query.with_entities(SfiSpec.subcategory)
                .filter(SfiSpec.subcategory.isnot(None), SfiSpec.subcategory != "")
                .distinct()
                .count()
            )
            breakdown = (
                db.session.query(SfiSpec.category, func.count(SfiSpec.id))
                .group_by(SfiSpec.category)
                .order_by(SfiSpec.category.asc())
                .all()
            )
            return jsonify({
                "total_specs": total,
                "total_categories": categories,
                "total_subcategories": subcategories,
                "by_category": {category: count for category, count in breakdown if category},
            })

    api.add_resource(_Search, "/specs/search")
    api.add_resource(_ListCreate, "/specs")
    api.add_resource(_DetailUpdateDelete, "/specs/<int:id>")
    api.add_resource(_Categories, "/categories")
    api.add_resource(_Detect, "/detect")
    api.add_resource(_Stats, "/stats")


# Import after the base API/model definitions to avoid circular imports.
from api.sfi_safety import register_sfi_safety_resources  # noqa: E402

register_sfi_safety_resources(api)
