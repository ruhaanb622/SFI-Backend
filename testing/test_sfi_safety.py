"""Lightweight smoke tests for the integrated SFI safety hub.

Run from the repository root with:
    python -m unittest testing.test_sfi_safety

These tests avoid production data and focus on route registration and pure input
helpers so they can run without seeding the SFI database.
"""

import unittest
from unittest.mock import patch

from flask import Flask

from api.sfi_safety import LEARNING_MODULES, _parse_iso_date, _qr_secret, _tokenize
from api.sfi_spec import sfi_spec_api


class SfiSafetyHelperTests(unittest.TestCase):
    def test_tokenize_normalizes_plain_language(self):
        self.assertEqual(
            _tokenize("Fire suit / Drag-Racing 3.2A"),
            ["fire", "suit", "drag", "racing", "3.2a"],
        )

    def test_iso_date_validation(self):
        self.assertEqual(_parse_iso_date("2026-09-04"), "2026-09-04")
        self.assertEqual(_parse_iso_date(""), "")
        with self.assertRaises(ValueError):
            _parse_iso_date("09/04/2026")

    def test_qr_secret_requires_server_secret(self):
        with patch.dict("os.environ", {"SFI_QR_SECRET": "short"}, clear=False):
            self.assertIsNone(_qr_secret())
        with patch.dict("os.environ", {"SFI_QR_SECRET": "x" * 32}, clear=False):
            self.assertEqual(_qr_secret(), "x" * 32)

    def test_learning_module_ids_are_unique(self):
        module_ids = [module["id"] for module in LEARNING_MODULES]
        self.assertEqual(len(module_ids), len(set(module_ids)))
        self.assertGreaterEqual(len(module_ids), 4)


class SfiSafetyRouteTests(unittest.TestCase):
    def test_safety_hub_routes_register_on_existing_blueprint(self):
        app = Flask(__name__)
        app.register_blueprint(sfi_spec_api)
        paths = {str(rule) for rule in app.url_map.iter_rules()}

        expected = {
            "/api/sfi/specs",
            "/api/sfi/specs/search",
            "/api/sfi/compass",
            "/api/sfi/participation/issue",
            "/api/sfi/participation/verify",
            "/api/sfi/inspections",
            "/api/sfi/timeline",
            "/api/sfi/manufacturer-reviews",
            "/api/sfi/manufacturer-reviews/<int:review_id>",
            "/api/sfi/learning/modules",
            "/api/sfi/learning/progress",
        }
        self.assertTrue(expected.issubset(paths), expected - paths)


if __name__ == "__main__":
    unittest.main()
