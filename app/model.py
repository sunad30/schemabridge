"""Supervised column classifier trained from versioned synthetic aliases and value profiles."""

import json
import re
from functools import lru_cache
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from scipy.sparse import hstack, csr_matrix
from scipy.optimize import linear_sum_assignment
from .schema import FIELDS, convert

ROOT = Path(__file__).resolve().parents[1]
FEATURE_NAMES = list(FIELDS)


def profile(values):
    nonempty = [v.strip() for v in values if v.strip()]
    rates = []
    for field in FEATURE_NAMES:
        passes = 0
        for v in nonempty:
            try:
                convert(v, field)
                passes += 1
            except ValueError:
                pass
        rates.append(passes / max(1, len(nonempty)))
    return rates


def normalize(header):
    return re.sub(r"[_-]+", " ", header.lower())


class Mapper:
    def __init__(self):
        training = json.loads((ROOT / "samples/training.json").read_text())
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True)
        text = self.vectorizer.fit_transform([normalize(x["header"]) for x in training])
        features = hstack([text, csr_matrix([profile(x["values"]) for x in training])])
        self.classifier = LogisticRegression(C=8, max_iter=1500, random_state=42)
        self.classifier.fit(features, [x["field"] for x in training])
        self.classes = list(self.classifier.classes_)

    def propose(self, headers, rows):
        vectors = self.vectorizer.transform([normalize(h) for h in headers])
        profiles = [profile([r[h] for r in rows]) for h in headers]
        probabilities = self.classifier.predict_proba(hstack([vectors, csr_matrix(profiles)]))
        # Dummy targets let every source abstain; real targets are one-to-one.
        cost = np.full((len(headers), len(self.classes) + len(headers)), -0.35)
        for i, probs in enumerate(probabilities):
            ranked = sorted(probs, reverse=True)
            if ranked[0] - ranked[1] >= 0.08:
                cost[i, : len(self.classes)] = -probs
        source_indices, target_indices = linear_sum_assignment(cost)
        assigned = {
            int(i): self.classes[j] if j < len(self.classes) and probabilities[i, j] >= 0.35 else None
            for i, j in zip(source_indices, target_indices)
        }
        suggestions = []
        for i, h in enumerate(headers):
            order = np.argsort(probabilities[i])[::-1][:3]
            suggestions.append(
                {
                    "source": h,
                    "target": assigned.get(i),
                    "candidates": [
                        {"field": self.classes[j], "score": round(float(probabilities[i, j]), 4)}
                        for j in order
                    ],
                    "profile": dict(zip(FEATURE_NAMES, profiles[i])),
                    "samples": [r[h] for r in rows[:3]],
                    "reason": "Learned header patterns + value compatibility; global one-to-one assignment. Scores are not calibrated confidence.",
                }
            )
        return suggestions


@lru_cache(maxsize=1)
def mapper():
    return Mapper()
