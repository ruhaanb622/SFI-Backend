"""
SFI Spec Model — stores parsed SFI Foundation specification data.

Each row represents one spec entry (e.g., SFI Spec 1.1 for
"Replacement Flywheels and Clutch Assemblies" under Auto Racing).

Data is loaded from _data/sfi_specs.json which is produced by
scripts/extract_sfi_specs.py in the greppers frontend repo.
"""

import json
import os
from __init__ import app, db


class SfiSpec(db.Model):
    """SQLAlchemy model for the sfi_specs table."""
    __tablename__ = 'sfi_specs'

    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    subcategory = db.Column(db.String(100), default='')
    spec_number = db.Column(db.String(20), nullable=False)
    spec_pdf = db.Column(db.String(255), default='')
    manufacturer_pdf = db.Column(db.String(255), default='')
    products_pdf = db.Column(db.String(255), default='')
    effective_date = db.Column(db.String(50), default='')

    def to_dict(self):
        """Convert this spec to a JSON-serializable dictionary."""
        return {
            "id": self.id,
            "product_name": self.product_name,
            "category": self.category,
            "subcategory": self.subcategory,
            "spec_number": self.spec_number,
            "spec_pdf": self.spec_pdf,
            "manufacturer_pdf": self.manufacturer_pdf,
            "products_pdf": self.products_pdf,
            "effective_date": self.effective_date,
        }


def initSfiSpecs():
    """Load SFI specs from the extracted JSON into the database.

    Clears existing data and re-imports so the DB always matches
    the latest extraction. Safe to call on every server start.
    """
    # Path to the JSON produced by extract_sfi_specs.py
    json_path = os.path.join(
        os.path.dirname(__file__), "..", "..",
        "greppers", "_data", "sfi_specs.json"
    )

    if not os.path.exists(json_path):
        print(f"[SFI] WARNING: {json_path} not found — skipping spec import")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        specs_data = json.load(f)

    # Clear old data
    db.session.query(SfiSpec).delete()

    count = 0
    for entry in specs_data:
        # Each entry can have multiple spec numbers — create one row per spec
        for i, spec_num in enumerate(entry.get("spec_numbers", [])):
            spec = SfiSpec(
                product_name=entry.get("product_name", ""),
                category=entry.get("category", ""),
                subcategory=entry.get("subcategory", ""),
                spec_number=spec_num,
                spec_pdf=entry["spec_pdfs"][i] if i < len(entry.get("spec_pdfs", [])) else "",
                manufacturer_pdf=entry["manufacturer_pdfs"][i] if i < len(entry.get("manufacturer_pdfs", [])) else "",
                products_pdf=entry["products_pdfs"][i] if i < len(entry.get("products_pdfs", [])) else "",
                effective_date=entry.get("effective_date", ""),
            )
            db.session.add(spec)
            count += 1

    db.session.commit()
    print(f"[SFI] Loaded {count} specs into database")
