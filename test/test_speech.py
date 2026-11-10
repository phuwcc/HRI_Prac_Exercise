"""Deterministic capture tests: no microphone, network or robot required."""
from pathlib import Path

import numpy as np
import pytest
import yaml

from ttbot4_seman_nav.audio_capture import UtteranceDetector, resample_for_whisper
from ttbot4_seman_nav.commands import CommandParser


@pytest.fixture
def parser():
    path = Path(__file__).resolve().parents[1] / 'config/regions_small_room.yaml'
    return CommandParser(yaml.safe_load(path.read_text())['regions'])


@pytest.mark.parametrize('text,expected', [
    ('Go to area A.', ['A']),
    ('Please go from room A to room B.', ['A', 'B']),
    ('Navigate to the laboratory.', ['B']),
    ('Move from the classroom via the corridor then to the lab.', ['A', 'C', 'B']),
    ('Go to area bee', ['B']),
    ('Go to room see', ['C']),
    ('Robot, stop please!', None),
    ('Cancel navigation', None),
    ('Đi đến phòng thí nghiệm', ['B']),
])
def test_english_routes(parser, text, expected):
    assert parser.parse(text) == expected


@pytest.mark.parametrize('text', [
    'Go to area Z', 'Go from A to Z', 'Go to A and Z',
    'Go to the unknown laboratory', 'Go forward', 'Hello there',
])
def test_unknown_english_routes_rejected(parser, text):
    with pytest.raises(ValueError):
        parser.parse(text)


def feed(detector, level, count):
    outputs = []
    for _ in range(count):
        audio = detector.feed(np.full(320, level, dtype=np.float32))
        if audio is not None:
            outputs.append(audio)
    return outputs


def test_keep_onset_and_end_on_silence():
    detector = UtteranceDetector(16000)
    assert not feed(detector, .001, 50)
    assert not feed(detector, .03, 30)
    outputs = feed(detector, .001, 40)
    assert len(outputs) == 1
    audio = outputs[0]
    assert audio[0] == pytest.approx(.001)  # pre-roll before the word onset
    assert np.count_nonzero(np.isclose(audio, .03)) == 30 * 320
    assert audio[-1] == pytest.approx(.001)  # short trailing silence
    assert not feed(detector, .001, 100)
    assert not feed(detector, .02, 20)
    assert len(feed(detector, .001, 40)) == 1  # next phrase is also captured


def test_background_noise_and_click_do_not_create_command():
    detector = UtteranceDetector(16000)
    assert not feed(detector, .01, 150)
    assert not feed(detector, .1, 1)
    assert not feed(detector, .01, 80)
    assert detector.threshold > .01


def test_max_duration_bounds_buffer():
    detector = UtteranceDetector(16000, max_seconds=2.)
    feed(detector, .001, 40)
    outputs = feed(detector, .04, 220)
    assert outputs
    assert all(len(audio) <= 32000 for audio in outputs)


def test_native_sample_rate_resampling():
    rate = 48000
    audio = np.sin(2 * np.pi * 440 * np.arange(rate) / rate).astype(np.float32)
    result = resample_for_whisper(audio, rate)
    assert result.shape == (16000,)
    assert result.dtype == np.float32
    assert np.sqrt(np.mean(result ** 2)) == pytest.approx(2 ** -.5, abs=.01)
    assert resample_for_whisper(result, 16000) is result
