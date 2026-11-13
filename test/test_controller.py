import math
import pytest
from ttbot4_face_emote.controller import Controller, Settings
from ttbot4_face_emote.vision import parse_result


def ready(emotion, **kwargs):
    c = Controller(Settings(**kwargs))
    for i in range(3):
        c.observe(emotion, 0.9, i * 0.1, i * 0.1)
    return c


@pytest.mark.parametrize('emotion,v,w', [
    ('happy', 1, 1), ('sad', 1, -1), ('neutral', 0, 0),
    ('angry', -1, 0), ('surprise', 0, 1), ('fear', 1, 0)])
def test_six_actions(emotion, v, w):
    linear, angular = ready(emotion).command(0.2)
    assert linear == pytest.approx(v * 0.08)
    assert angular == pytest.approx(w * 0.4)


def test_stability_and_low_confidence():
    c = Controller(Settings())
    c.observe('happy', 0.9, 0, 0)
    assert c.command(0) == (0, 0)
    c.observe('happy', 0.1, 0.1, 0.1)
    assert c.count == 0


@pytest.mark.parametrize('emotion,confidence', [(None, 0), ('disgust', 0.99),
                                               ('happy', 0.1), ('happy', float('nan'))])
def test_invalid_immediately_stops(emotion, confidence):
    c = ready('happy')
    c.observe(emotion, confidence, 0.3, 0.3)
    assert c.command(0.3) == (0, 0)


def test_timeout_and_stale_inference():
    c = ready('happy')
    assert c.command(2.3) == (0, 0)
    for _ in range(3):
        c.observe('fear', 0.9, 0.3, 3)
    assert c.command(3) == (0, 0)


def test_bounded_step_and_neutral_rearms():
    c = ready('fear')
    assert c.command(1.21) == (0, 0)
    for t in (1.3, 1.4, 1.5):
        c.observe('fear', 0.9, t, t)
    assert c.command(1.5) == (0, 0)
    for t in (1.55, 1.6, 1.65):
        c.observe('neutral', 0.9, t, t)
    for t in (1.7, 1.8, 1.9):
        c.observe('fear', 0.9, t, t)
    assert c.command(1.9)[0] > 0


def test_turn_one_nominal_revolution():
    c = ready('surprise')
    end = 0.2 + 2 * math.pi / c.s.angular_speed
    for i in range(1, 160):
        t = 0.2 + i * 0.1
        c.observe('surprise', 0.9, t, t)
        v, w = c.command(t)
        assert v == 0
        assert w == (0.4 if t < end else 0)


def test_neutral_and_expression_change_interrupt():
    c = ready('happy')
    c.observe('sad', 0.9, 0.3, 0.3)
    assert c.command(0.3) == (0, 0)
    c.observe('sad', 0.9, 0.4, 0.4)
    c.observe('sad', 0.9, 0.5, 0.5)
    assert c.command(0.5)[1] < 0
    c.observe('neutral', 0.9, 0.6, 0.6)
    assert c.command(0.6) == (0, 0)


@pytest.mark.parametrize('kwargs', [{'angular_speed': 0}, {'timeout': -1},
                                   {'linear_speed': float('nan')},
                                   {'linear_speed': 0.3}, {'stable_samples': 0}])
def test_invalid_settings(kwargs):
    with pytest.raises(ValueError):
        Settings(**kwargs)


def test_parse_deepface():
    face = {'region': {'x': 1, 'y': 2, 'w': 30, 'h': 40},
            'emotion': {'happy': 90, 'sad': 10}}
    assert parse_result([face])[:2] == ('happy', 0.9)
    assert parse_result(face)[:2] == ('happy', 0.9)
    assert parse_result([])[0] is None
    assert parse_result([face, face])[0] is None
    assert parse_result({'emotion': {'happy': 100}})[0] is None


def test_single_neutral_flicker_stops_but_does_not_rearm():
    c = ready('fear')
    assert c.command(1.21) == (0, 0)  # Completed, rather than interrupted.
    c.observe('neutral', 0.9, 1.3, 1.3)
    assert c.command(1.3) == (0, 0)
    for t in (1.4, 1.5, 1.6):
        c.observe('fear', 0.9, t, t)
    assert c.command(1.6) == (0, 0)
    assert c.latched == 'fear'


@pytest.mark.parametrize('interruption', ['invalid', 'timeout', 'neutral', 'other_label'])
def test_interrupted_action_retries_after_exactly_three_fresh_samples(interruption):
    c = ready('happy')
    assert c.command(0.2) != (0, 0)
    if interruption == 'timeout':
        assert c.command(2.3) == (0, 0)
        start = 2.4
    else:
        label = {'invalid': None, 'neutral': 'neutral', 'other_label': 'sad'}[interruption]
        c.observe(label, 0.9, 0.3, 0.3)
        assert c.command(0.3) == (0, 0)
        start = 0.4
    for i in range(3):
        t = start + i * 0.1
        c.observe('happy', 0.36, t, t)
        assert (c.command(t) != (0, 0)) == (i == 2)
