"""Read a laptop webcam, classify gestures, and publish a filtered heartbeat."""

from contextlib import ExitStack
import json
import math
from pathlib import Path
import signal
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from std_msgs.msg import Bool, String

from .control import GESTURES
from .gestures import GestureFilter, WaveDetector


class GestureRecognitionNode(Node):
    def __init__(self, resources):
        super().__init__('gesture_recognition_node')
        # Import here so a missing AI dependency produces a clear startup failure.
        import cv2
        import mediapipe as mp
        from .display import WINDOW, render_dashboard

        self.cv2, self.mp = cv2, mp
        self.window, self.render_dashboard = WINDOW, render_dashboard
        defaults = {
            'model_path': '', 'camera_index': 0, 'confidence': 0.65,
            'confirm_frames': 5, 'fps': 15.0, 'show_window': True,
        }
        for key, value in defaults.items():
            self.declare_parameter(key, value)
        def p(key):
            return self.get_parameter(key).value

        path = Path(p('model_path')).expanduser()
        if not path.is_file():
            raise ValueError(f'Missing MediaPipe model: {path}. Follow README section 1.')
        values = [p('confidence'), p('fps')]
        if (not all(math.isfinite(value) for value in values)
                or not 0 < p('confidence') <= 1 or p('fps') <= 0):
            raise ValueError('Invalid confidence or fps')
        self.threshold = p('confidence')
        self.show_window = p('show_window')
        self.filter = GestureFilter(p('confirm_frames'))
        self.wave = WaveDetector()
        self.publisher = self.create_publisher(String, '/detected_gesture', 1)
        self.tracking = self.create_publisher(Bool, '/gesture_control/hand_present', 1)
        self.state = {}
        self.state_time = self.command_time = -math.inf
        self.command = (0.0, 0.0)
        self.previous_frame_time = None
        self.fps = 0.0
        self.create_subscription(String, '/gesture_control/state', self.on_state, 1)
        self.create_subscription(Twist, '/cmd_vel', self.on_command, 1)
        self.camera = cv2.VideoCapture(p('camera_index'), cv2.CAP_V4L2)
        resources.callback(self.camera.release)
        if not self.camera.isOpened():
            raise RuntimeError(f'Cannot open webcam /dev/video{p("camera_index")}')
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        options = mp.tasks.vision.GestureRecognizerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=1,
        )
        self.recognizer = resources.enter_context(
            mp.tasks.vision.GestureRecognizer.create_from_options(options))
        if self.show_window:
            cv2.namedWindow(self.window, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(self.window, 1280, 820)
            resources.callback(cv2.destroyAllWindows)
        self.last_timestamp = -1
        self.create_timer(1.0 / p('fps'), self.process_frame)
        self.get_logger().info(
            f'Gesture recognizer ready. Select, then Thumb Up; '
            f'hold each for {self.filter.confirm_frames} consecutive frames.')

    def on_state(self, message):
        try:
            state = json.loads(message.data)
        except (ValueError, TypeError):
            return
        if isinstance(state, dict):
            self.state = state
            self.state_time = time.monotonic()

    def on_command(self, message):
        self.command = (message.linear.x, message.angular.z)
        self.command_time = time.monotonic()

    def process_frame(self):
        cv2, mp = self.cv2, self.mp
        ok, frame = self.camera.read()
        if not ok:
            self.publisher.publish(String(data='None'))
            raise RuntimeError('Webcam stopped delivering frames')
        frame = cv2.flip(frame, 1)
        now = time.monotonic()
        if self.previous_frame_time is not None:
            measured_fps = 1.0 / max(now - self.previous_frame_time, 1e-6)
            self.fps = measured_fps if not self.fps else 0.85 * self.fps + 0.15 * measured_fps
        self.previous_frame_time = now
        timestamp = max(self.last_timestamp + 1, int(now * 1000))
        self.last_timestamp = timestamp
        image = mp.Image(image_format=mp.ImageFormat.SRGB,
                         data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        result = self.recognizer.recognize_for_video(image, timestamp)
        # This heartbeat follows completed inference, never a timer or a cached result.
        # A low gesture score must not masquerade as a lost hand/camera stream.
        self.tracking.publish(Bool(data=bool(result.hand_landmarks)))
        gesture, score, wrist_x = 'None', 0.0, 0.0
        if result.gestures and result.gestures[0]:
            category = result.gestures[0][0]
            score = float(category.score)
            if score >= self.threshold and category.category_name in GESTURES:
                gesture = category.category_name
                wrist_x = result.hand_landmarks[0][0].x
        if self.wave.update(gesture, wrist_x, now):
            gesture = 'Wave'
        filtered = self.filter.update(gesture)
        self.publisher.publish(String(data=filtered))
        if not self.show_window:
            return
        dashboard = self.render_dashboard(
            frame, result.hand_landmarks[0] if result.hand_landmarks else [],
            gesture=gesture, score=score, filtered=filtered, count=self.filter.count,
            required=self.filter.confirm_frames, fps=self.fps, state=self.state,
            linked=now - self.state_time < 1.5, command=self.command,
            command_live=now - self.command_time < 1.5,
            subscribers=self.publisher.get_subscription_count(),
        )
        cv2.imshow(self.window, dashboard)
        cv2.waitKey(1)  # Pump GUI events; keys never control the robot.
        if cv2.getWindowProperty(self.window, cv2.WND_PROP_VISIBLE) < 1:
            self.publisher.publish(String(data='None'))
            raise SystemExit(0)


def main(args=None):
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    node = None
    try:
        with ExitStack() as resources:
            node = GestureRecognitionNode(resources)
            rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        if node is not None:
            if rclpy.ok():
                node.publisher.publish(String(data='None'))
            node.destroy_node()
        rclpy.try_shutdown()
