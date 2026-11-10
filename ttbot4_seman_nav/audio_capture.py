"""Streaming energy-based utterance detection, independent of ROS and PortAudio."""
from collections import deque

import numpy as np


class UtteranceDetector:
    """Keep the word onset and end a phrase after sustained silence.

    Call once per fixed-size mono frame. Calibrate in silence first. The noise
    floor then follows quiet frames only, so speech cannot raise the threshold.
    """

    def __init__(self, sample_rate, frame_seconds=.02, min_rms=.006,
                 silence_seconds=.8, min_speech_seconds=.24,
                 max_seconds=8., pre_roll_seconds=.3, calibration_seconds=.6):
        if not (sample_rate > 0 and frame_seconds > 0 and min_rms > 0
                and silence_seconds > 0 and min_speech_seconds > 0
                and max_seconds > silence_seconds + min_speech_seconds
                and pre_roll_seconds >= 0 and calibration_seconds >= 0):
            raise ValueError('Invalid voice detection timing or threshold')
        self.sample_rate = sample_rate
        self.min_rms = min_rms
        self.silence_frames = max(1, round(silence_seconds / frame_seconds))
        self.min_speech_frames = max(2, round(min_speech_seconds / frame_seconds))
        self.max_frames = max(1, round(max_seconds / frame_seconds))
        self.calibration_frames = round(calibration_seconds / frame_seconds)
        self.pre_roll = deque(maxlen=max(2, round(pre_roll_seconds / frame_seconds)))
        self.noise_levels = []
        self.noise_floor = 0.
        self.frames = []
        self.speech_frames = 0
        self.quiet_frames = 0
        self.onset_frames = 0

    @property
    def threshold(self):
        return max(self.min_rms, self.noise_floor * 3.)

    def feed(self, frame):
        frame = np.asarray(frame, dtype=np.float32).reshape(-1).copy()
        rms = float(np.sqrt(np.mean(frame ** 2)))
        if self.calibration_frames:
            self.noise_levels.append(rms)
            self.calibration_frames -= 1
            if not self.calibration_frames:
                self.noise_floor = float(np.median(self.noise_levels))
            return None

        voiced = rms >= self.threshold
        if not self.frames:
            self.pre_roll.append(frame)
            self.onset_frames = self.onset_frames + 1 if voiced else 0
            if self.onset_frames >= 2:
                self.frames = list(self.pre_roll)
                self.pre_roll.clear()
                self.speech_frames = self.onset_frames
                self.quiet_frames = 0
            elif not voiced:
                self.noise_floor = .99 * self.noise_floor + .01 * rms
            return None

        self.frames.append(frame)
        self.speech_frames += int(voiced)
        self.quiet_frames = 0 if voiced else self.quiet_frames + 1
        if self.quiet_frames < self.silence_frames and len(self.frames) < self.max_frames:
            return None

        # Retain a short tail, rather than passing all trailing silence to Whisper.
        tail = max(0, self.quiet_frames - 5)
        frames = self.frames[:-tail] if tail else self.frames
        audio = np.concatenate(frames) if self.speech_frames >= self.min_speech_frames else None
        self.frames = []
        self.speech_frames = self.quiet_frames = self.onset_frames = 0
        return audio


def resample_for_whisper(audio, sample_rate):
    """Convert the device's native mono sample rate to Whisper's 16 kHz input."""
    audio = np.asarray(audio, dtype=np.float32)
    if sample_rate == 16000:
        return audio
    # PortAudio devices need not support 16 kHz. Use a proper anti-aliasing filter.
    from scipy.signal import resample_poly
    from math import gcd
    divisor = gcd(int(sample_rate), 16000)
    return resample_poly(audio, 16000 // divisor, int(sample_rate) // divisor).astype(np.float32)
