"""Opt-in ROS transport and independent capture/inference regression test."""
import os
import threading
import time

import pytest

pytestmark = pytest.mark.skipif(os.environ.get('FACE_EMOTE_ROS_TEST') != '1',
                                reason='Set FACE_EMOTE_ROS_TEST=1 in a sourced ROS environment')


def test_cmd_vel_capture_responsiveness_and_stale_inference_stop(monkeypatch):
    rclpy = pytest.importorskip('rclpy')
    cv2 = pytest.importorskip('cv2')
    np = pytest.importorskip('numpy')
    from geometry_msgs.msg import Twist
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.signals import SignalHandlerOptions
    import ttbot4_face_emote.node as implementation

    state = {'emotion': 'happy', 'released': False, 'reads': 0, 'slow': False}
    inference_started, release_inference = threading.Event(), threading.Event()

    class Camera:
        def __init__(self, *args):
            pass

        def isOpened(self):
            return True

        def set(self, *args):
            return True

        def read(self):
            time.sleep(0.01)
            state['reads'] += 1
            return True, np.zeros((120, 160, 3), dtype=np.uint8)

        def release(self):
            state['released'] = True

    class Analyzer:
        def __init__(self, *args):
            pass

        def close(self):
            pass

        def analyze(self, frame):
            if state['slow']:
                inference_started.set()
                release_inference.wait(5)
            emotion = state['emotion']
            if emotion is None:
                return []
            return [{'region': {'x': 10, 'y': 10, 'w': 60, 'h': 60},
                     'emotion': {emotion: 99.0, 'disgust': 1.0}}]

    monkeypatch.setattr(implementation, 'FaceAnalyzer', Analyzer)
    monkeypatch.setattr(cv2, 'VideoCapture', Camera)
    rclpy.init(args=['--ros-args', '-p', 'show_camera:=false',
                     '-p', 'inference_period:=0.05', '-p', 'timeout:=0.6',
                     '-p', 'cmd_vel_topic:=/face_emote_test/cmd_vel'],
               signal_handler_options=SignalHandlerOptions.NO)
    node = implementation.FaceEmoteNode()
    observer = rclpy.create_node('face_emote_test_observer')
    received = []
    subscription = observer.create_subscription(
        Twist, '/face_emote_test/cmd_vel',
        lambda msg: received.append((msg.linear.x, msg.angular.z)), 10)
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    executor.add_node(observer)

    def until(predicate, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            executor.spin_once(timeout_sec=0.02)
            if predicate():
                return
        pytest.fail(f'Timed out; received {received[-10:]}')

    try:
        until(lambda: any(v > 0 and w > 0 for v, w in received))
        state['slow'] = True
        until(inference_started.is_set)
        before = state['reads']
        until(lambda: state['reads'] >= before + 10)
        # Preview reads the same newest-frame slot even while inference blocks.
        assert time.monotonic() - node.frames.snapshot()[2] < 0.15
        received.clear()
        until(lambda: bool(received) and received[-1] == (0.0, 0.0))
        assert node.controller.active is None
        assert not release_inference.is_set()
        state['slow'] = False
        release_inference.set()
        # Stable Neutral rearms, then a new Happy action must still work.
        state['emotion'] = 'neutral'
        until(lambda: node.controller.latched is None)
        state['emotion'] = 'happy'
        received.clear()
        until(lambda: any(v > 0 and w > 0 for v, w in received))
        state['emotion'] = None
        received.clear()
        until(lambda: bool(received) and received[-1] == (0.0, 0.0))
        assert node.controller.active is None
        node.close()
        assert state['released']
    finally:
        release_inference.set()
        node.close()
        executor.shutdown()
        observer.destroy_subscription(subscription)
        observer.destroy_node()
        node.destroy_node()
        rclpy.shutdown()
