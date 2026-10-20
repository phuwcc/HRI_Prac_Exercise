"""Run Ultralytics YOLO on the TurtleBot 4 RGB camera stream."""

from collections import Counter
import json
import math
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import String


def detections_from_result(result):
    """Convert one Ultralytics result into JSON-serializable detections."""
    detections = []
    boxes = getattr(result, 'boxes', None)
    if boxes is None:
        return detections
    names = getattr(result, 'names', {})
    for box in boxes:
        class_id = int(box.cls[0].item())
        confidence = float(box.conf[0].item())
        coordinates = [round(float(value), 1) for value in box.xyxy[0].tolist()]
        if isinstance(names, dict):
            label = names.get(class_id, str(class_id))
        else:
            label = names[class_id]
        detections.append({
            'class_id': class_id,
            'label': str(label),
            'confidence': round(confidence, 3),
            'bbox_xyxy': coordinates,
        })
    return detections


class ObjectDetector(Node):
    """Subscribe to RGB images and publish YOLO annotations and metadata."""

    def __init__(self):
        super().__init__('object_detector')
        self.declare_parameter('image_topic', '/oakd/rgb/preview/image_raw')
        self.declare_parameter('annotated_topic', '/yolo/annotated_image')
        self.declare_parameter('detections_topic', '/yolo/detections')
        self.declare_parameter('model', 'yolov8n.pt')
        self.declare_parameter('confidence', 0.40)
        self.declare_parameter('iou', 0.45)
        self.declare_parameter('device', 'cpu')
        self.declare_parameter('inference_hz', 5.0)
        self.declare_parameter('show_window', False)

        confidence = float(self.get_parameter('confidence').value)
        iou = float(self.get_parameter('iou').value)
        inference_hz = float(self.get_parameter('inference_hz').value)
        if not 0.0 <= confidence <= 1.0:
            raise ValueError('confidence must be in [0, 1]')
        if not 0.0 <= iou <= 1.0:
            raise ValueError('iou must be in [0, 1]')
        if not math.isfinite(inference_hz) or inference_hz <= 0.0:
            raise ValueError('inference_hz must be finite and positive')

        try:
            from cv_bridge import CvBridge
        except (ImportError, RuntimeError) as error:
            raise RuntimeError(
                'cv_bridge could not be loaded. Install ros-humble-cv-bridge and use a '
                'NumPy version compatible with ROS 2 Humble (normally numpy<2).',
            ) from error
        try:
            from ultralytics import YOLO
        except ImportError as error:
            raise RuntimeError(
                'Ultralytics is missing. Install it with: python3 -m pip install ultralytics',
            ) from error

        self._cv2 = __import__('cv2')
        self._bridge = CvBridge()
        model_name = str(self.get_parameter('model').value)
        self.get_logger().info(f'Loading YOLO model: {model_name}')
        self._model = YOLO(model_name)
        self._confidence = confidence
        self._iou = iou
        self._device = str(self.get_parameter('device').value)
        self._minimum_period = 1.0 / inference_hz
        self._last_inference = 0.0
        self._last_log = 0.0
        self._show_window = bool(self.get_parameter('show_window').value)

        image_topic = str(self.get_parameter('image_topic').value)
        annotated_topic = str(self.get_parameter('annotated_topic').value)
        detections_topic = str(self.get_parameter('detections_topic').value)
        self._image_publisher = self.create_publisher(Image, annotated_topic, 10)
        self._detection_publisher = self.create_publisher(String, detections_topic, 10)
        self._subscription = self.create_subscription(
            Image, image_topic, self._on_image, qos_profile_sensor_data,
        )
        self.get_logger().info(
            f'YOLO ready: {image_topic} -> {annotated_topic}; metadata -> {detections_topic}',
        )

    def _on_image(self, message):
        now = time.monotonic()
        if now - self._last_inference < self._minimum_period:
            return
        self._last_inference = now
        try:
            image = self._bridge.imgmsg_to_cv2(message, desired_encoding='bgr8')
            results = self._model.predict(
                source=image,
                conf=self._confidence,
                iou=self._iou,
                device=self._device,
                verbose=False,
            )
            if not results:
                return
            result = results[0]
            detections = detections_from_result(result)
            annotated = result.plot()

            output = self._bridge.cv2_to_imgmsg(annotated, encoding='bgr8')
            output.header = message.header
            self._image_publisher.publish(output)

            metadata = String()
            metadata.data = json.dumps({
                'stamp': {
                    'sec': message.header.stamp.sec,
                    'nanosec': message.header.stamp.nanosec,
                },
                'frame_id': message.header.frame_id,
                'detections': detections,
            }, ensure_ascii=False)
            self._detection_publisher.publish(metadata)

            if detections and now - self._last_log >= 1.0:
                counts = Counter(item['label'] for item in detections)
                summary = ', '.join(f'{name} x{count}' for name, count in sorted(counts.items()))
                best = max(item['confidence'] for item in detections)
                self.get_logger().info(
                    f'Detected {len(detections)} object(s): {summary}; best confidence={best:.2f}',
                )
                self._last_log = now

            if self._show_window:
                self._cv2.imshow('TurtleBot 4 - YOLO detections', annotated)
                self._cv2.waitKey(1)
        except Exception as error:  # Keep the camera subscription alive after a bad frame.
            self.get_logger().error(f'YOLO frame processing failed: {error}')

    def destroy_node(self):
        if getattr(self, '_show_window', False):
            self._cv2.destroyAllWindows()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = ObjectDetector()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as error:
        if node is not None:
            node.get_logger().fatal(str(error))
        else:
            print(f'Object detector failed: {error}')
        raise SystemExit(1) from error
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.try_shutdown()
