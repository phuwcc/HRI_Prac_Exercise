"""Independent camera, inference and ROS/preview loops, without a frame queue."""
import math
import threading
import time

import cv2
import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions

from .camera import LatestFrame
from .controller import Controller, Settings
from .inference import FaceAnalyzer
from .vision import EmotionSmoother, parse_result


class FaceEmoteNode(Node):
    def __init__(self):
        super().__init__('face_emote')
        defaults = vars(Settings())
        for name, value in defaults.items():
            self.declare_parameter(name, value)
        extra = {'camera_index': 0, 'show_camera': True, 'cmd_vel_topic': '/cmd_vel',
                 'inference_period': 0.1, 'camera_width': 640, 'camera_height': 480,
                 'camera_fps': 30, 'camera_timeout': 0.5, 'camera_mjpeg': True,
                 'detection_width': 320, 'min_face_size': 24, 'detector_confidence': 0.5,
                 'smoothing_seconds': 0.0, 'emotion_margin': 0.0}
        for name, value in extra.items():
            self.declare_parameter(name, value)
        self.options = {key: self.get_parameter(key).value for key in extra}
        for key in ('camera_width', 'camera_height', 'camera_fps', 'detection_width', 'min_face_size'):
            if self.options[key] <= 0:
                raise ValueError(f'{key} must be positive')
        for key in ('inference_period', 'camera_timeout'):
            if not math.isfinite(self.options[key]) or self.options[key] <= 0:
                raise ValueError(f'{key} must be finite and positive')
        self.controller = Controller(Settings(**{
            key: self.get_parameter(key).value for key in defaults}))
        if not 0 < self.options['detector_confidence'] <= 1:
            raise ValueError('detector_confidence must be in (0, 1]')
        self.smoother = EmotionSmoother(
            confidence=self.controller.s.confidence, margin=self.options['emotion_margin'],
            time_constant=self.options['smoothing_seconds'],
            max_gap=min(self.controller.s.timeout, 0.7))
        self.period = self.options['inference_period']
        self.show = self.options['show_camera']
        self.publisher = self.create_publisher(Twist, self.options['cmd_vel_topic'], 1)
        self.lock = threading.Lock()
        self.halt = threading.Event()
        self.frames = LatestFrame()
        self.latest = None
        self.sequence = self.processed = 0
        self.camera_ok = False
        self.camera_fps = self.inference_ms = 0.0
        self.region = None
        self.status = 'Loading model / waiting for camera'
        self.closed = False
        cv2.setNumThreads(1)
        self.capture_worker = threading.Thread(target=self.capture, daemon=True)
        self.worker = threading.Thread(target=self.infer, daemon=True)
        self.capture_worker.start()
        self.worker.start()
        self.timer = self.create_timer(0.05, self.tick)
        self.preview_timer = self.create_timer(1/30, self.preview) if self.show else None

    def invalid(self, status):
        with self.lock:
            self.sequence += 1
            self.latest = (None, 0.0, time.monotonic())
            self.region = None
            self.status = status

    def capture(self):
        cap = None
        try:
            cap = cv2.VideoCapture(self.options['camera_index'], cv2.CAP_V4L2)
            if not cap.isOpened():
                raise RuntimeError('Cannot open webcam')
            if self.options['camera_mjpeg']:
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            for prop, value in ((cv2.CAP_PROP_FRAME_WIDTH, self.options['camera_width']),
                                (cv2.CAP_PROP_FRAME_HEIGHT, self.options['camera_height']),
                                (cv2.CAP_PROP_FPS, self.options['camera_fps']),
                                (cv2.CAP_PROP_BUFFERSIZE, 1)):
                cap.set(prop, value)  # Driver may ignore unsupported settings.
            previous = None
            while not self.halt.is_set():
                ok, frame = cap.read()
                captured = time.monotonic()
                if not ok:
                    raise RuntimeError('Webcam read failed')
                with self.lock:
                    self.camera_ok = True
                    if previous is not None and captured > previous:
                        fps = 1 / (captured-previous)
                        self.camera_fps = fps if not self.camera_fps else 0.9*self.camera_fps + 0.1*fps
                previous = captured
                self.frames.put(frame, captured)
        except Exception as exc:
            self.get_logger().error(f'Camera stopped: {exc}')
            with self.lock:
                self.camera_ok = False
            self.invalid(f'Camera error: {exc}')
        finally:
            self.frames.close()
            if cap is not None:
                cap.release()

    def infer(self):
        analyzer = None
        try:
            analyzer = FaceAnalyzer(self.options['detection_width'], self.options['min_face_size'],
                                    self.options['detector_confidence'])
            previous = 0
            while not self.halt.is_set():
                sample = self.frames.after(previous)
                if sample is None:
                    if self.frames.closed:
                        return
                    continue
                previous, frame, captured = sample
                started = time.monotonic()
                results = analyzer.analyze(frame)
                raw, _, _ = parse_result(results)
                emotion, confidence, region = self.smoother.update(results, captured)
                elapsed = time.monotonic()-started
                with self.lock:
                    # A slow result must not override a camera failure.
                    if self.camera_ok:
                        self.sequence += 1
                        self.latest = (emotion, confidence, captured)
                        self.region = region
                        self.inference_ms = elapsed*1000
                        self.status = f'{emotion or "Uncertain / no single face"} {confidence:.0%} | raw: {raw or "none"}'
                # period is start-to-start, not additional sleep after inference.
                self.halt.wait(max(0, self.period-elapsed))
        except Exception as exc:
            self.get_logger().error(f'Vision stopped: {exc}')
            self.invalid(f'Vision error: {exc}')
        finally:
            if analyzer is not None:
                analyzer.close()

    def tick(self):
        now = time.monotonic()
        sample = self.frames.snapshot()
        with self.lock:
            sequence, result, camera_ok = self.sequence, self.latest, self.camera_ok
        if not camera_ok or sample is None or now-sample[2] > self.options['camera_timeout']:
            self.controller.observe(None, 0.0, now, now)
        elif sequence != self.processed and result is not None:
            self.controller.observe(*result, now)
            self.processed = sequence
        linear, angular = self.controller.command(now)
        msg = Twist()
        msg.linear.x, msg.angular.z = linear, angular
        self.publisher.publish(msg)

    def preview(self):
        sample = self.frames.snapshot()
        if sample is None:
            return
        _, image, captured = sample
        frame = image.copy()
        now = time.monotonic()
        with self.lock:
            status, region, result = self.status, self.region, self.latest
            fps, elapsed = self.camera_fps, self.inference_ms
            camera_ok = self.camera_ok
        if not camera_ok or now-captured > self.options['camera_timeout']:
            status = 'Camera disconnected / stale - STOP'
            region = None
        elif result and now-result[2] > self.controller.s.timeout:
            status = 'Recognition stale - STOP'
            region = None
        if region and result and now-result[2] < 0.5:
            x, y, w, h = (int(region[k]) for k in ('x', 'y', 'w', 'h'))
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
        lines = [status, f'Camera {fps:.0f} FPS | inference {elapsed:.0f} ms | frame age {(now-captured)*1000:.0f} ms',
                 f'Confirm: {self.controller.candidate or "none"} {min(self.controller.count, self.controller.s.stable_samples)}/{self.controller.s.stable_samples} | Action: {self.controller.active or "STOP"} | Q/Esc: exit']
        for i, line in enumerate(lines):
            cv2.putText(frame, line, (10, 25+i*25), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (0, 255, 255), 1, cv2.LINE_AA)
        cv2.imshow('TurtleBot face emotions', frame)
        if cv2.waitKey(1) & 0xFF in (ord('q'), 27):
            raise KeyboardInterrupt

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.halt.set()
        self.frames.close()
        self.timer.cancel()
        if self.preview_timer:
            self.preview_timer.cancel()
        self.publisher.publish(Twist())
        self.capture_worker.join(timeout=1.0)
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
