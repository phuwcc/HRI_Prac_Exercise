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


class EmotionSmoother:
    """Validate each frame; optional EMA (disabled at zero) never spans lost faces."""
    def __init__(self, confidence=0.35, margin=0.0, time_constant=0.0, max_gap=0.7):
        if (not 0 <= confidence <= 1 or not 0 <= margin <= 1
                or not math.isfinite(time_constant) or time_constant < 0
                or not math.isfinite(max_gap) or max_gap <= 0):
            raise ValueError('Invalid smoothing settings')
        self.confidence, self.margin = confidence, margin
        self.time_constant, self.max_gap = time_constant, max_gap
        self.reset()

    def reset(self):
        self.scores = None
        self.timestamp = None
        self.region = None

    def update(self, results, captured_at):
        emotion, confidence, region = parse_result(results)
        if emotion is None:
            self.reset()
            return None, 0.0, None
        result = results[0] if isinstance(results, list) else results
        scores = {key: float(value) / 100 for key, value in result['emotion'].items()}
        if (any(not math.isfinite(v) or v < 0 for v in scores.values())
                or sum(scores.values()) <= 0):
            self.reset()
            return None, 0.0, None
        total = sum(scores.values())
        scores = {k: v / total for k, v in scores.items()}
        # Reset when another face occupies a different part of the image.
        same_face = self.region is not None and self.overlap(self.region, region) >= 0.25
        if (self.time_constant == 0 or self.scores is None or not same_face or captured_at <= self.timestamp
                or captured_at - self.timestamp > self.max_gap):
            self.scores = scores
        else:
            alpha = 1 - math.exp(-(captured_at - self.timestamp) / self.time_constant)
            self.scores = {k: (1-alpha) * self.scores.get(k, 0) + alpha * scores.get(k, 0)
                           for k in self.scores.keys() | scores.keys()}
        self.timestamp, self.region = captured_at, dict(region)
        ranked = sorted(self.scores.items(), key=lambda item: item[1], reverse=True)
        best, probability = ranked[0]
        runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
        if (probability < self.confidence or probability <= runner_up
                or probability - runner_up < self.margin):
            return None, probability, region
        return best, probability, region

    @staticmethod
    def overlap(a, b):
        left, top = max(a['x'], b['x']), max(a['y'], b['y'])
        right = min(a['x']+a['w'], b['x']+b['w'])
        bottom = min(a['y']+a['h'], b['y']+b['h'])
        intersection = max(0, right-left) * max(0, bottom-top)
        union = a['w']*a['h'] + b['w']*b['h'] - intersection
        return intersection / union if union > 0 else 0.0
