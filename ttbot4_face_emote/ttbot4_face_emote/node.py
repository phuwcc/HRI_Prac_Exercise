"""Webcam inference in a worker; ROS heartbeat and GUI remain responsive."""
import threading
import time

import cv2
import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions

from .controller import Controller, Settings
from .vision import parse_result


class FaceEmoteNode(Node):
    def __init__(self):
        super().__init__('face_emote')
        defaults = vars(Settings())
        for name, value in defaults.items():
            self.declare_parameter(name, value)
        for name, value in {'camera_index': 0, 'show_camera': True,
                            'cmd_vel_topic': '/cmd_vel', 'inference_period': 0.15}.items():
            self.declare_parameter(name, value)
        self.controller = Controller(Settings(**{
            key: self.get_parameter(key).value for key in defaults}))
        self.period = self.get_parameter('inference_period').value
        if self.period <= 0:
            raise ValueError('inference_period must be positive')
        self.show = self.get_parameter('show_camera').value
        self.publisher = self.create_publisher(
            Twist, self.get_parameter('cmd_vel_topic').value, 1)
        self.lock = threading.Lock()
        self.halt = threading.Event()
        self.latest = None
        self.sequence = self.processed = 0
        self.frame = None
        self.status = 'Loading model / waiting for camera'
        self.worker = threading.Thread(target=self.capture, daemon=True)
        self.worker.start()
        self.timer = self.create_timer(0.05, self.tick)

    def capture(self):
        cap = None
        try:
            from deepface import DeepFace
            # Load weights before opening the webcam; first run can download them.
            DeepFace.build_model('Emotion', task='facial_attribute')
            cap = cv2.VideoCapture(self.get_parameter('camera_index').value)
            if not cap.isOpened():
                raise RuntimeError('Cannot open webcam')
            while not self.halt.is_set():
                ok, frame = cap.read()
                captured = time.monotonic()
                if not ok:
                    raise RuntimeError('Webcam read failed')
                with self.lock:
                    self.frame = frame.copy()
                try:
                    results = DeepFace.analyze(
                        img_path=frame, actions=['emotion'], detector_backend='opencv',
                        enforce_detection=True, silent=True)
                    emotion, confidence, region = parse_result(results)
                    status = f'{emotion or "No single face"} ({confidence:.0%})'
                except ValueError:
                    emotion, confidence, region = None, 0.0, None
                    status = 'No face / invalid detection'
                with self.lock:
                    self.sequence += 1
                    self.latest = (emotion, confidence, captured)
                    self.status = status
                    if region:
                        x, y, w, h = (int(region[k]) for k in ('x', 'y', 'w', 'h'))
                        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                    self.frame = frame
                self.halt.wait(self.period)
        except Exception as exc:
            self.get_logger().error(f'Vision stopped: {exc}')
            with self.lock:
                self.sequence += 1
                self.latest = (None, 0.0, time.monotonic())
                self.status = f'Vision error: {exc}'
        finally:
            if cap is not None:
                cap.release()

    def tick(self):
        now = time.monotonic()
        with self.lock:
            sequence, result, status = self.sequence, self.latest, self.status
            frame = None if self.frame is None else self.frame.copy()
        if sequence != self.processed and result is not None:
            self.controller.observe(*result, now)
            self.processed = sequence
        linear, angular = self.controller.command(now)
        msg = Twist()
        msg.linear.x, msg.angular.z = linear, angular
        self.publisher.publish(msg)
        if self.show and frame is not None:
            cv2.putText(frame, status, (10, 25), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (0, 255, 255), 2)
            cv2.putText(frame, f'v={linear:.2f} w={angular:.2f} | Q: exit', (10, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.imshow('TurtleBot face emotions', frame)
            if cv2.waitKey(1) & 0xFF in (ord('q'), 27):
                self.halt.set()
                raise KeyboardInterrupt

    def close(self):
        self.halt.set()
        self.timer.cancel()
        self.publisher.publish(Twist())
        self.worker.join(timeout=1.0)
        if self.show:
            cv2.destroyAllWindows()


def main(args=None):
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    node = None
    try:
        node = FaceEmoteNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            if rclpy.ok():
                node.close()
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
