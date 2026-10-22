"""Temporal filtering and dynamic wave detection in normalized image coordinates."""

from collections import deque


class GestureFilter:
    def __init__(self, confirm_frames=5):
        if isinstance(confirm_frames, bool) or not isinstance(confirm_frames, int) or confirm_frames < 1:
            raise ValueError('confirm_frames must be a positive integer')
        self.confirm_frames = confirm_frames
        self.candidate = None
        self.count = 0

    def update(self, gesture):
        if gesture != self.candidate:
            self.candidate, self.count = gesture, 0
        self.count = min(self.count + 1, self.confirm_frames) if gesture != 'None' else 0
        if gesture in ('Open_Palm', 'Closed_Fist', 'None'):
            return gesture
        return gesture if self.count >= self.confirm_frames else 'None'


class WaveDetector:
    """Require lateral travel in both directions; a stationary palm is not a wave."""

    def __init__(self, window=1.5, amplitude=0.08):
        self.window = window
        self.amplitude = amplitude
        self.samples = deque()

    def update(self, gesture, wrist_x, now):
        if gesture != 'Open_Palm':
            self.samples.clear()
            return False
        self.samples.append((now, wrist_x))
        while self.samples and now - self.samples[0][0] > self.window:
            self.samples.popleft()
        anchor = self.samples[0][1]
        direction = 0
        reversals = 0
        for _, x in self.samples:
            delta = x - anchor
            if abs(delta) < self.amplitude:
                continue
            next_direction = 1 if delta > 0 else -1
            if direction and next_direction != direction:
                reversals += 1
            direction, anchor = next_direction, x
        return reversals >= 2
