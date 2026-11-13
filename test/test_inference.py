"""Check crop coordinates and that unverified frames never reach the model."""
from types import SimpleNamespace

import pytest

np = pytest.importorskip('numpy')
pytest.importorskip('cv2')
from ttbot4_face_emote.inference import FaceAnalyzer


def detection(x=0.25, y=0.25, w=0.5, h=0.5):
    return SimpleNamespace(location_data=SimpleNamespace(
        relative_bounding_box=SimpleNamespace(xmin=x, ymin=y, width=w, height=h),
        relative_keypoints=[]))


def analyzer_for(detections):
    analyzer = FaceAnalyzer.__new__(FaceAnalyzer)
    analyzer.detection_width, analyzer.min_face_size = 320, 30
    calls = []
    detector_inputs = []

    def process(rgb):
        detector_inputs.append(rgb)
        return SimpleNamespace(detections=detections)

    def classify(**kwargs):
        calls.append(kwargs)
        return [{'emotion': {'happy': 99.0, 'neutral': 1.0}}]

    analyzer.detector = SimpleNamespace(process=process)
    analyzer.deepface = SimpleNamespace(analyze=classify)
    return analyzer, calls, detector_inputs


def test_localize_small_but_classify_verified_full_resolution_crop():
    analyzer, calls, inputs = analyzer_for([detection()])
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:, :, 0] = 255
    results = analyzer.analyze(frame)
    assert inputs[0].shape == (240, 320, 3)
    assert list(inputs[0][0, 0]) == [0, 0, 255]  # BGR -> RGB for MediaPipe.
    assert results[0]['region'] == {'x': 160, 'y': 120, 'w': 320, 'h': 240}
    assert calls[0]['img_path'].shape == (224, 224, 3)
    assert calls[0]['detector_backend'] == 'skip'
    assert not calls[0]['align']
    assert frame.sum() == 480 * 640 * 255  # No overlays written onto camera frame.


@pytest.mark.parametrize('detections', [None, [], [detection(), detection()],
                                         [detection(w=0.01, h=0.01)],
                                         [detection(x=2.0)]])
def test_unverified_or_ambiguous_face_never_classifies_whole_image(detections):
    analyzer, calls, _ = analyzer_for(detections)
    assert analyzer.analyze(np.zeros((480, 640, 3), dtype=np.uint8)) == []
    assert not calls
