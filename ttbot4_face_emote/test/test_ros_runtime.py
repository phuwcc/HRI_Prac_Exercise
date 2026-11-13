"""Opt-in transport test with real ROS 2, synthetic webcam/model (no weights)."""
import os
import sys
import time
import types

import pytest

pytestmark = pytest.mark.skipif(os.environ.get('FACE_EMOTE_ROS_TEST') != '1',
                                reason='Set FACE_EMOTE_ROS_TEST=1 in a sourced ROS environment')


def test_cmd_vel_transport_and_stop(monkeypatch):
    rclpy = pytest.importorskip('rclpy')
    cv2 = pytest.importorskip('cv2')
    np = pytest.importorskip('numpy')
    from geometry_msgs.msg import Twist
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.signals import SignalHandlerOptions
    from ttbot4_face_emote.node import FaceEmoteNode

    state = {'face': True, 'released': False}

    class Camera:
        def __init__(self, index):
            pass

        def isOpened(self):
            return True

        def read(self):
            return True, np.zeros((120, 160, 3), dtype=np.uint8)

        def release(self):
            state['released'] = True

    class Model:
        @staticmethod
        def build_model(*args, **kwargs):
            return None

        @staticmethod
        def analyze(**kwargs):
            if not state['face']:
                raise ValueError('No face')
            return [{'region': {'x': 10, 'y': 10, 'w': 60, 'h': 60},
                     'emotion': {'happy': 99.0, 'neutral': 1.0}}]

    monkeypatch.setitem(sys.modules, 'deepface', types.SimpleNamespace(DeepFace=Model))
    monkeypatch.setattr(cv2, 'VideoCapture', Camera)
    rclpy.init(args=['--ros-args', '-p', 'show_camera:=false',
                     '-p', 'inference_period:=0.05',
                     '-p', 'cmd_vel_topic:=/face_emote_test/cmd_vel'],
               signal_handler_options=SignalHandlerOptions.NO)
    node = FaceEmoteNode()
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
        state['face'] = False
        received.clear()
        until(lambda: bool(received) and received[-1] == (0.0, 0.0))
        assert node.controller.active is None
        node.close()
        until(lambda: received[-1] == (0.0, 0.0))
        assert state['released']
    finally:
        node.close()
        executor.shutdown()
        observer.destroy_subscription(subscription)
        observer.destroy_node()
        node.destroy_node()
        rclpy.shutdown()
