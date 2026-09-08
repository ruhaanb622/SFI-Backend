"""
SFI Part Classifier — ML model for identifying SFI spec categories
from free-text part descriptions.

Uses TF-IDF vectorization + LinearSVC to classify racing safety parts
into their corresponding SFI specification numbers and categories.

Training data comes from sfi_specs.json (136 entries), augmented with
synonyms, keyword extraction, and partial-phrase variants.
"""

import json
import os
import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder


class SfiClassifier:
    """Singleton ML classifier for SFI part identification."""

    _instance = None

    SYNONYMS = {
        "helmet": ["Flame Resistant Motorsports Helmets", "Youth Full Face Helmets", "Motorsports Helmet"],
        "suit": ["Driver Suits", "Advanced Driver Suits", "Abrasion Resistant Driver/Rider Suits"],
        "gloves": ["Driver Accessories"],
        "shoes": ["Driver Accessories"],
        "harness": ["Driver Restraint Assemblies", "Stock Car Driver Restraint Assemblies", "Advanced Motorsport Driver Restraint Assemblies"],
        "restraint": ["Driver Restraint Assemblies", "Head and Neck Restraint Systems"],
        "hans": ["Head and Neck Restraint Systems"],
        "fuel cell": ["Crash Resistant Fuel Cells", "Polymer (Foam-Filled) Fuel Cells", "Competition Fuel Cell Bladder"],
        "roll cage": ["Funny Car Roll Cage", "Altered Car Roll Cage", "Driver Roll Cage"],
        "bellhousing": ["Containment Bellhousing for SFI 1.1 & 1.2 Clutch Assemblies", "Containment Bellhousing for SFI Clutch Assemblies"],
        "clutch": ["Replacement Flywheels and Clutch Assemblies", "Multiple Disc Clutch Assemblies"],
        "flywheel": ["Replacement Flywheels and Clutch Assemblies"],
        "flexplate": ["Automatic Transmission Flexplates", "High Horsepower Automatic Transmission Flexplates"],
        "transmission": ["Automatic Transmission Shields (Flexible Type)", "Automatic Transmission Shields (Rigid Type)", "Automatic Transmission Flexplates"],
        "supercharger": ["Supercharger Restraint Devices", "Screw-Type Supercharger Restraint Devices", "Screw-Type Superchargers", "Supercharger Pressure Relief Assemblies"],
        "blower": ["Supercharger Restraint Devices", "Centrifugal Supercharger Blankets"],
        "turbo": ["Turbochargers"],
        "turbocharger": ["Turbochargers"],
        "wheel": ["Drag Race Drive Wheels", "Drag Race Front Wheels", "Stock Car Steel Wheels", "Alloy Stock Car Wheels"],
        "fire": ["On Board Fire Suppression Systems", "Driver Suits"],
        "extinguisher": ["On Board Fire Suppression Systems"],
        "seat": ["Stock Car Type Racing Seats (Custom)", "Racing Seats (Standard)"],
        "window net": ["Window Nets"],
        "net": ["Window Nets", "Roll Cage Nets"],
        "driveshaft": ["Drive Shafts"],
        "drive shaft": ["Drive Shafts"],
        "damper": ["Crankshaft Hub Harmonic Dampers"],
        "harmonic balancer": ["Crankshaft Hub Harmonic Dampers"],
        "steering": ["Steering Wheel Quick Disconnect/Release"],
        "quick release": ["Steering Wheel Quick Disconnect/Release"],
        "wing": ["Top Fuel Rear Wing", "Top Fuel Front Wing"],
        "spoiler": ["Top Fuel Rear Wing"],
        "padding": ["Roll Bar Padding", "Impact Padding"],
        "blanket": ["Tractor Blankets", "Manifold Blankets", "Engine Blankets – Rear", "Centrifugal Supercharger Blankets"],
        "tether": ["NASCAR-Type Tethers"],
        "chassis": ["Full Bodied Car Tube Chassis"],
        "dragster": ["Rear Engine Dragster", "Front Engine Dragster"],
        "funny car": ["Nitro Fuel Funny Car Chassis", "Funny Car Roll Cage"],
        "boat": ["Drag Boat Capsule Shell Material", "Drag Boat Capsule Canopy Material", "Drag Boat Capsule Roll Cage"],
        "tractor": ["Tractor Blankets", "Driver Roll Cage for Use on Tractors"],
        "apron": ["Fueler Apron"],
        "coating": ["Non Flammable, Thermal Barrier / Fire Extinguishing Coatings"],
        "valve cover": ["Containment Valve Covers/Valve Cover Shields"],
        "shift boot": ["Shift Boot Covers"],
        "chest protector": ["Go-Kart Chest Protector (Youth Driver)"],
        "kart": ["Go-Kart Chest Protector (Youth Driver)"],
        "carbon fiber": ["NASCAR Dashboard and Other Carbon Fiber Components"],
        "spacer": ["Stock Car Wheel Spacers"],
    }

    def __init__(self):
        self.spec_pipeline = None
        self.category_pipeline = None
        self.spec_encoder = LabelEncoder()
        self.category_encoder = LabelEncoder()
        self.specs_data = []
        self.spec_lookup = {}
        self.trained = False
        self.accuracy = 0.0
        self.n_samples = 0

    def _load_data(self):
        json_path = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "greppers", "_data", "sfi_specs.json"
        )
        if not os.path.exists(json_path):
            json_path = os.path.join(
                os.path.dirname(__file__), "..",
                "sfi_specs.json"
            )
        if not os.path.exists(json_path):
            print("[SFI Classifier] WARNING: sfi_specs.json not found")
            return

        with open(json_path, "r", encoding="utf-8") as f:
            self.specs_data = json.load(f)

        for entry in self.specs_data:
            for i, spec_num in enumerate(entry.get("spec_numbers", [])):
                self.spec_lookup[spec_num] = {
                    "product_name": entry.get("product_name", ""),
                    "category": entry.get("category", ""),
                    "subcategory": entry.get("subcategory", ""),
                    "spec_pdf": entry["spec_pdfs"][i] if i < len(entry.get("spec_pdfs", [])) else "",
                    "manufacturer_pdf": entry["manufacturer_pdfs"][i] if i < len(entry.get("manufacturer_pdfs", [])) else "",
                }

    def _augment_data(self):
        texts = []
        spec_labels = []
        category_labels = []

        for entry in self.specs_data:
            name = entry.get("product_name", "")
            category = entry.get("category", "")
            spec_nums = entry.get("spec_numbers", [])
            if not spec_nums:
                continue
            spec_num = spec_nums[0]

            # Full product name
            texts.append(name)
            spec_labels.append(spec_num)
            category_labels.append(category)

            # Lowercase variant
            texts.append(name.lower())
            spec_labels.append(spec_num)
            category_labels.append(category)

            # Individual significant words (skip short/common words)
            stopwords = {"for", "and", "the", "with", "or", "a", "an", "to", "of", "in", "on", "&"}
            words = [w for w in re.split(r'[\s,;/()–—\-]+', name) if len(w) > 2 and w.lower() not in stopwords]
            for word in words:
                texts.append(word.lower())
                spec_labels.append(spec_num)
                category_labels.append(category)

            # Bigrams from product name
            if len(words) >= 2:
                for j in range(len(words) - 1):
                    bigram = f"{words[j]} {words[j+1]}".lower()
                    texts.append(bigram)
                    spec_labels.append(spec_num)
                    category_labels.append(category)

            # Name without parenthetical content
            clean_name = re.sub(r'\([^)]*\)', '', name).strip()
            if clean_name != name and clean_name:
                texts.append(clean_name.lower())
                spec_labels.append(spec_num)
                category_labels.append(category)

        # Add synonym-based training samples
        for synonym, product_names in self.SYNONYMS.items():
            for pname in product_names:
                matched = None
                for entry in self.specs_data:
                    if pname.lower() in entry.get("product_name", "").lower():
                        spec_nums = entry.get("spec_numbers", [])
                        if spec_nums:
                            matched = (spec_nums[0], entry.get("category", ""))
                            break
                if matched:
                    texts.append(synonym)
                    spec_labels.append(matched[0])
                    category_labels.append(matched[1])

        return texts, spec_labels, category_labels

    def _train(self):
        if not self.specs_data:
            return

        texts, spec_labels, category_labels = self._augment_data()
        self.n_samples = len(texts)

        # Encode labels
        spec_encoded = self.spec_encoder.fit_transform(spec_labels)
        category_encoded = self.category_encoder.fit_transform(category_labels)

        # Spec number classifier pipeline
        self.spec_pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(
                ngram_range=(1, 3),
                max_features=5000,
                sublinear_tf=True,
                analyzer='char_wb',
                min_df=1,
            )),
            ('clf', LinearSVC(
                max_iter=10000,
                C=1.0,
                class_weight='balanced',
            ))
        ])
        self.spec_pipeline.fit(texts, spec_encoded)

        # Category classifier pipeline
        self.category_pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(
                ngram_range=(1, 2),
                max_features=3000,
                sublinear_tf=True,
                min_df=1,
            )),
            ('clf', LinearSVC(
                max_iter=10000,
                C=1.0,
                class_weight='balanced',
            ))
        ])
        self.category_pipeline.fit(texts, category_encoded)

        # Calculate training accuracy
        spec_pred = self.spec_pipeline.predict(texts)
        self.accuracy = float(np.mean(spec_pred == spec_encoded))
        self.trained = True
        print(f"[SFI Classifier] Trained on {self.n_samples} samples, accuracy: {self.accuracy:.1%}")

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._load_data()
            cls._instance._train()
        return cls._instance

    def predict(self, description, top_n=10):
        if not self.trained:
            return {"error": "Model not trained", "predictions": []}

        texts = [description]

        # Get spec predictions with decision function scores
        spec_scores = self.spec_pipeline.decision_function(texts)[0]
        if spec_scores.ndim == 0:
            spec_scores = np.array([spec_scores])

        # Softmax for confidence
        exp_scores = np.exp(spec_scores - np.max(spec_scores))
        spec_probs = exp_scores / exp_scores.sum()

        # Get category prediction
        cat_scores = self.category_pipeline.decision_function(texts)[0]
        if cat_scores.ndim == 0:
            cat_scores = np.array([cat_scores])
        cat_exp = np.exp(cat_scores - np.max(cat_scores))
        cat_probs = cat_exp / cat_exp.sum()

        cat_idx = np.argmax(cat_probs)
        predicted_category = self.category_encoder.inverse_transform([cat_idx])[0]
        category_confidence = float(cat_probs[cat_idx])

        # Top N spec predictions
        top_indices = np.argsort(spec_probs)[::-1][:top_n]
        predictions = []
        seen_specs = set()
        for idx in top_indices:
            spec_num = self.spec_encoder.inverse_transform([idx])[0]
            if spec_num in seen_specs:
                continue
            seen_specs.add(spec_num)

            info = self.spec_lookup.get(spec_num, {})
            predictions.append({
                "spec_number": spec_num,
                "product_name": info.get("product_name", "Unknown"),
                "category": info.get("category", "Unknown"),
                "subcategory": info.get("subcategory", ""),
                "confidence": round(float(spec_probs[idx]), 4),
                "spec_pdf": info.get("spec_pdf", ""),
                "manufacturer_pdf": info.get("manufacturer_pdf", ""),
            })

        return {
            "input_text": description,
            "predicted_category": predicted_category,
            "category_confidence": round(category_confidence, 4),
            "predictions": predictions,
            "count": len(predictions),
        }

    def get_status(self):
        return {
            "trained": self.trained,
            "accuracy": round(self.accuracy, 4),
            "training_samples": self.n_samples,
            "spec_classes": len(self.spec_encoder.classes_) if self.trained else 0,
            "category_classes": len(self.category_encoder.classes_) if self.trained else 0,
            "categories": list(self.category_encoder.classes_) if self.trained else [],
        }


def initSfiClassifier():
    SfiClassifier.get_instance()
