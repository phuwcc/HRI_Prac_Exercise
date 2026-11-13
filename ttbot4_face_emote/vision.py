"""Translate DeepFace results; ambiguous/missing faces never request motion."""
import math


def parse_result(results):
    if isinstance(results, dict):
        results = [results]
    if len(results) != 1:
        return None, 0.0, None
    result = results[0]
    region = result.get('region', {})
    if region.get('w', 0) <= 0 or region.get('h', 0) <= 0:
        return None, 0.0, None
    scores = result.get('emotion', {})
    if not scores:
        return None, 0.0, None
    emotion = max(scores, key=scores.get)
    confidence = float(scores[emotion]) / 100.0
    if not math.isfinite(confidence) or not 0 <= confidence <= 1:
        return None, 0.0, None
    return emotion, confidence, region
