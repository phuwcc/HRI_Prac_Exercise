"""ROS-independent bounded motion and recognition filtering."""
from dataclasses import dataclass
import math


@dataclass
class Settings:
    linear_speed: float = 0.08
    angular_speed: float = 0.4
    arc_duration: float = 3.0
    step_duration: float = 1.0
    confidence: float = 0.35
    stable_samples: int = 3
    timeout: float = 2.0

    def __post_init__(self):
        for name in ('linear_speed', 'angular_speed', 'arc_duration', 'step_duration', 'timeout'):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f'{name} must be finite and positive')
        if not 0 <= self.confidence <= 1 or self.stable_samples < 1:
            raise ValueError('Invalid confidence or stable_samples')
        if self.linear_speed > 0.2 or self.angular_speed > 1.0:
            raise ValueError('Speed exceeds coursework limits: 0.2 m/s, 1.0 rad/s')


class Controller:
    def __init__(self, settings):
        self.s = settings
        self.candidate = None
        self.count = 0
        self.latched = None
        self.active = None
        self.started = 0.0
        self.seen = float('-inf')

    def observe(self, emotion, confidence, captured_at, now):
        if (emotion not in ('happy', 'sad', 'neutral', 'angry', 'surprise', 'fear')
                or not math.isfinite(confidence) or confidence < self.s.confidence
                or now - captured_at > self.s.timeout):
            self.interrupt()
            return
        self.seen = captured_at
        if emotion == 'neutral':
            if self.active is not None:
                self.latched = None
            self.active = None
            self.count = self.count + 1 if self.candidate == 'neutral' else 1
            self.candidate = 'neutral'
            # Stop immediately, but a one-frame neutral flicker cannot rearm
            # and repeat a completed movement.
            if self.count >= self.s.stable_samples:
                self.latched = None
            return
        if self.candidate != emotion:
            if self.active is not None:
                self.latched = None
            self.active = None
            self.candidate, self.count = emotion, 1
        else:
            self.count += 1
        if self.count >= self.s.stable_samples and emotion != self.latched:
            self.active = self.latched = emotion
            self.started = now

    def interrupt(self):
        # An interrupted movement can be retried after three fresh detections.
        # A normally completed movement stays latched to avoid endless repeats.
        if self.active is not None:
            self.latched = None
        self.active = None
        self.candidate, self.count = None, 0

    def command(self, now):
        if now - self.seen > self.s.timeout:
            self.interrupt()
        if self.active is None:
            return 0.0, 0.0
        s = self.s
        actions = {
            'happy': (s.linear_speed, s.angular_speed, s.arc_duration),
            'sad': (s.linear_speed, -s.angular_speed, s.arc_duration),
            'angry': (-s.linear_speed, 0.0, s.step_duration),
            'fear': (s.linear_speed, 0.0, s.step_duration),
            'surprise': (0.0, s.angular_speed, 2 * math.pi / s.angular_speed),
        }
        linear, angular, duration = actions[self.active]
        if now - self.started >= duration:
            self.active = None
            return 0.0, 0.0
        return linear, angular
