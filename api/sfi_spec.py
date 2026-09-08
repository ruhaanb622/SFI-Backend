"""
SFI Spec API — full CRUD, search, visual part detection, and stats
for the SFI Foundation web modernization project.

Endpoints:
    GET    /api/sfi/specs              — list all specs (optional ?category= filter)
    POST   /api/sfi/specs              — create a new spec (admin)
    GET    /api/sfi/specs/search       — keyword search (?q=)
    GET    /api/sfi/specs/<int:id>     — get a single spec by ID
    PUT    /api/sfi/specs/<int:id>     — update an existing spec (admin)
    DELETE /api/sfi/specs/<int:id>     — delete a spec (admin)
    GET    /api/sfi/categories         — distinct category list
    POST   /api/sfi/detect             — visual part detector
    GET    /api/sfi/stats              — dashboard summary stats
"""

from flask import Blueprint, request, jsonify
from flask_restful import Api, Resource
from sqlalchemy import or_, func
from __init__ import db
from model.sfi_spec import SfiSpec

sfi_spec_api = Blueprint('sfi_spec_api', __name__, url_prefix='/api/sfi')
api = Api(sfi_spec_api)


class SfiSpecAPI:
    """API resources for SFI spec CRUD, search, detection, and stats."""

    # ── Search ─────────────────────────────────────────────

    class _Search(Resource):
        """GET /api/sfi/specs/search?q=<keyword>"""
        def get(self):
            query = request.args.get('q', '').strip()
            if not query:
                return {"error": "Missing 'q' query parameter"}, 400

            keyword = f"%{query}%"
            results = SfiSpec.query.filter(
                (SfiSpec.product_name.ilike(keyword)) |
                (SfiSpec.spec_number.ilike(keyword)) |
                (SfiSpec.category.ilike(keyword)) |
                (SfiSpec.subcategory.ilike(keyword))
            ).all()

            return jsonify([spec.to_dict() for spec in results])

    # ── List (GET) + Create (POST) on /specs ───────────────

    class _ListCreate(Resource):
        """GET  /api/sfi/specs?category=<name>  — list specs
           POST /api/sfi/specs                  — create a spec
        """
        def get(self):
            category = request.args.get('category', '').strip()
            if category:
                results = SfiSpec.query.filter(
                    SfiSpec.category.ilike(f"%{category}%")
                ).all()
            else:
                results = SfiSpec.query.all()
            return jsonify([spec.to_dict() for spec in results])

        def post(self):
            data = request.get_json()
            if not data:
                return {"error": "Missing JSON body"}, 400

            required = ['product_name', 'category', 'spec_number']
            missing = [f for f in required if not data.get(f)]
            if missing:
                return {"error": f"Missing required fields: {', '.join(missing)}"}, 400

            spec = SfiSpec(
                product_name=data['product_name'],
                category=data['category'],
                subcategory=data.get('subcategory', ''),
                spec_number=data['spec_number'],
                spec_pdf=data.get('spec_pdf', ''),
                manufacturer_pdf=data.get('manufacturer_pdf', ''),
                products_pdf=data.get('products_pdf', ''),
                effective_date=data.get('effective_date', ''),
            )
            db.session.add(spec)
            db.session.commit()
            return spec.to_dict(), 201

    # ── Detail (GET) + Update (PUT) + Delete (DELETE) on /specs/<id>

    class _DetailUpdateDelete(Resource):
        """Single-spec operations by ID."""
        def get(self, id):
            spec = SfiSpec.query.get(id)
            if not spec:
                return {"error": "Spec not found"}, 404
            return jsonify(spec.to_dict())

        def put(self, id):
            spec = SfiSpec.query.get(id)
            if not spec:
                return {"error": "Spec not found"}, 404

            data = request.get_json()
            if not data:
                return {"error": "Missing JSON body"}, 400

            for field in ['product_name', 'category', 'subcategory',
                          'spec_number', 'spec_pdf', 'manufacturer_pdf',
                          'products_pdf', 'effective_date']:
                if field in data:
                    setattr(spec, field, data[field])

            db.session.commit()
            return jsonify(spec.to_dict())

        def delete(self, id):
            spec = SfiSpec.query.get(id)
            if not spec:
                return {"error": "Spec not found"}, 404

            db.session.delete(spec)
            db.session.commit()
            return {"message": "Spec deleted"}, 200

    # ── Categories ─────────────────────────────────────────

    class _Categories(Resource):
        """GET /api/sfi/categories"""
        def get(self):
            rows = SfiSpec.query.with_entities(
                SfiSpec.category
            ).distinct().all()
            return jsonify([row.category for row in rows])

    # ── Visual Part Detector ───────────────────────────────

    class _Detect(Resource):
        """POST /api/sfi/detect

        Accepts {"keywords": "helmet, fire"} or {"keywords": ["helmet","fire"]}.
        The frontend sends keywords extracted from a captured car-part
        image and this returns the most relevant specs ranked by match score.
        """
        def post(self):
            # ML mode: route through SfiClassifier if ?mode=ml
            mode = request.args.get('mode', '').strip().lower()
            if mode == 'ml':
                from model.sfi_classifier import SfiClassifier
                data = request.get_json()
                if not data or 'keywords' not in data:
                    return {"error": "Missing 'keywords' in request body"}, 400
                keywords = data['keywords']
                if isinstance(keywords, list):
                    keywords = ', '.join(keywords)
                classifier = SfiClassifier.get_instance()
                return jsonify(classifier.predict(keywords.strip()))

            data = request.get_json()
            if not data or 'keywords' not in data:
                return {"error": "Missing 'keywords' in request body"}, 400

            keywords = data['keywords']
            if isinstance(keywords, str):
                keywords = [k.strip() for k in keywords.split(',') if k.strip()]
            if not keywords:
                return {"error": "Empty keywords"}, 400

            # Build OR filter across all keyword terms
            filters = []
            for kw in keywords:
                like = f"%{kw}%"
                filters.append(SfiSpec.product_name.ilike(like))
                filters.append(SfiSpec.spec_number.ilike(like))
                filters.append(SfiSpec.category.ilike(like))
                filters.append(SfiSpec.subcategory.ilike(like))

            results = SfiSpec.query.filter(or_(*filters)).all()

            # Score results by how many keywords matched
            scored = []
            for spec in results:
                haystack = f"{spec.product_name} {spec.spec_number} {spec.category} {spec.subcategory}".lower()
                score = sum(1 for kw in keywords if kw.lower() in haystack)
                scored.append((score, spec))
            scored.sort(key=lambda x: x[0], reverse=True)

            return jsonify({
                "keywords_used": keywords,
                "results": [s.to_dict() for _, s in scored],
                "count": len(scored),
            })

    # ── Stats / Dashboard ─────────────────────────────────

    class _Stats(Resource):
        """GET /api/sfi/stats — summary counts for the admin dashboard."""
        def get(self):
            total = SfiSpec.query.count()
            categories = SfiSpec.query.with_entities(
                SfiSpec.category
            ).distinct().count()
            subcategories = SfiSpec.query.with_entities(
                SfiSpec.subcategory
            ).distinct().count()

            breakdown = db.session.query(
                SfiSpec.category, func.count(SfiSpec.id)
            ).group_by(SfiSpec.category).all()

            return jsonify({
                "total_specs": total,
                "total_categories": categories,
                "total_subcategories": subcategories,
                "by_category": {cat: cnt for cat, cnt in breakdown},
            })

    # ── Register all routes ────────────────────────────────
    api.add_resource(_Search, '/specs/search')
    api.add_resource(_ListCreate, '/specs')
    api.add_resource(_DetailUpdateDelete, '/specs/<int:id>')
    api.add_resource(_Categories, '/categories')
    api.add_resource(_Detect, '/detect')
    api.add_resource(_Stats, '/stats')
