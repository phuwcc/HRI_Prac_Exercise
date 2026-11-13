import threading

import pytest

from ttbot4_face_emote.camera import LatestFrame
from ttbot4_face_emote.vision import EmotionSmoother


def face(happy=95, sad=3, neutral=2, x=10):
    return [{'region': {'x': x, 'y': 10, 'w': 80, 'h': 80},
             'emotion': {'happy': happy, 'sad': sad, 'neutral': neutral}}]


def test_latest_frame_drops_backlog_and_wakes_consumers():
    frames = LatestFrame()
    frames.put('old', 1)
    frames.put('newest', 2)
    assert frames.after(0) == (2, 'newest', 2)
    assert frames.after(2, timeout=0) is None
    thread = threading.Thread(target=lambda: frames.put('next', 3))
    thread.start()
    assert frames.after(2)[1] == 'next'
    thread.join()
    frames.close()
    assert frames.after(0) is None


def test_optional_smoothing_still_filters_single_label_spike():
    smoother = EmotionSmoother(time_constant=0.25)
    for i in range(10):
        assert smoother.update(face(), i * 0.1)[0] == 'happy'
    assert smoother.update(face(1, 98, 1), 1.0)[0] == 'happy'
    # Sustained new expression must eventually replace the old one.
    for i in range(11, 21):
        result = smoother.update(face(1, 98, 1), i * 0.1)
    assert result[0] == 'sad'


def test_ambiguous_scores_never_request_motion():
    smoother = EmotionSmoother(confidence=0.5, margin=0.12)
    assert smoother.update(face(53, 46, 1), 0)[0] is None


@pytest.mark.parametrize('boundary', ['no_face', 'multiple_faces', 'new_face', 'time_gap'])
def test_old_expression_cannot_bleed_across_face_or_time_boundary(boundary):
    smoother = EmotionSmoother()
    smoother.update(face(), 0)
    next_time, next_face = 0.1, face(1, 98, 1)
    if boundary == 'no_face':
        assert smoother.update([], 0.05)[0] is None
    elif boundary == 'multiple_faces':
        assert smoother.update(face() + face(x=300), 0.05)[0] is None
    elif boundary == 'new_face':
        next_face = face(1, 98, 1, x=300)
    else:
        next_time = 2
    assert smoother.update(next_face, next_time)[0] == 'sad'


def test_filter_rejects_nonfinite_scores_and_does_not_drop_disgust():
    smoother = EmotionSmoother()
    assert smoother.update(face(90, float('nan'), 10), 0)[0] is None
    sample = face()
    sample[0]['emotion'] = {'disgust': 99, 'happy': 1}
    assert smoother.update(sample, 1)[0] == 'disgust'


@pytest.mark.parametrize('emotion', ['happy', 'sad', 'angry', 'surprise', 'fear'])
def test_default_pipeline_triggers_on_exactly_third_modest_confidence_frame(emotion):
    from ttbot4_face_emote.controller import Controller, Settings
    smoother = EmotionSmoother()
    controller = Controller(Settings())
    # Earlier strong predictions must not delay a new raw three-frame sequence.
    for t in (0, 0.1, 0.2):
        label, score, _ = smoother.update(face(neutral=98, happy=1, sad=1), t)
        controller.observe(label, score, t, t)
    for i, t in enumerate((0.3, 0.4, 0.5), 1):
        sample = face()
        sample[0]['emotion'] = {emotion: 36, 'neutral': 34, 'disgust': 30}
        label, score, _ = smoother.update(sample, t)
        assert label == emotion
        controller.observe(label, score, t, t)
        assert controller.count == i
        if i < 3:
            assert controller.command(t) == (0, 0)
        else:
            assert controller.command(t) != (0, 0)


def test_default_pipeline_rejects_exact_ties_and_below_threshold():
    smoother = EmotionSmoother()
    assert smoother.update(face(50, 50, 0), 0)[0] is None
    assert smoother.update(face(34, 33, 33), 0.1)[0] is None


def test_one_raw_spike_does_not_pass_three_frame_controller_confirmation():
    from ttbot4_face_emote.controller import Controller, Settings
    smoother = EmotionSmoother()
    controller = Controller(Settings())
    for t, result in ((0, face()), (0.1, face(1, 98, 1)), (0.2, face())):
        label, score, _ = smoother.update(result, t)
        controller.observe(label, score, t, t)
        assert controller.command(t) == (0, 0)
