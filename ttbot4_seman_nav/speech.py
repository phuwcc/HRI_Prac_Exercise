"""Continuous English speech capture with automatic phrase boundaries."""
import queue
import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from .audio_capture import UtteranceDetector, resample_for_whisper


class SpeechRecognition(Node):
    def __init__(self):
        super().__init__('speech_recognition')
        for name, value in {
            'model': 'base.en', 'device': 'cpu', 'microphone': '',
            'language': 'en', 'record_seconds': 8., 'min_rms': .006,
            'silence_seconds': .8, 'min_speech_seconds': .24,
            'pre_roll_seconds': .3, 'calibration_seconds': .6,
        }.items():
            self.declare_parameter(name, value)
        self.publisher = self.create_publisher(String, 'voice/command', 10)
        self.messages = queue.Queue()
        self.utterances = queue.Queue(maxsize=2)
        self.stop_event = threading.Event()
        self.create_timer(.1, self.flush)
        # Read ROS parameters before entering the audio thread.
        self.settings = {name: self.get_parameter(name).value for name in (
            'model', 'device', 'microphone', 'language', 'record_seconds',
            'min_rms', 'silence_seconds', 'min_speech_seconds',
            'pre_roll_seconds', 'calibration_seconds',
        )}
        self.worker = threading.Thread(target=self.listen, daemon=True)
        self.worker.start()

    def flush(self):
        while True:
            try:
                kind, text = self.messages.get_nowait()
            except queue.Empty:
                break
            if kind == 'warning':
                self.get_logger().warning(text)
            else:
                self.get_logger().info(text)
            if kind == 'text':
                self.publisher.publish(String(data=text))

    def listen(self):
        try:
            import sounddevice as sd
            import whisper
            settings = self.settings
            mic = settings['microphone'] or None
            if mic is not None and str(mic).isdigit():
                mic = int(mic)
            device_info = sd.query_devices(mic, 'input')
            sample_rate = int(device_info['default_samplerate'])
            detector = UtteranceDetector(
                sample_rate, min_rms=float(settings['min_rms']),
                silence_seconds=float(settings['silence_seconds']),
                min_speech_seconds=float(settings['min_speech_seconds']),
                max_seconds=float(settings['record_seconds']),
                pre_roll_seconds=float(settings['pre_roll_seconds']),
                calibration_seconds=float(settings['calibration_seconds']),
            )
            self.messages.put(('log', f"Loading Whisper {settings['model']}..."))
            model = whisper.load_model(settings['model'], device=settings['device'])

            def capture(indata, frames, time_info, status):
                if self.stop_event.is_set():
                    return
                if status:
                    self.messages.put(('warning', f'Microphone stream: {status}'))
                was_calibrating = detector.calibration_frames > 0
                audio = detector.feed(indata[:, 0])
                if was_calibrating and not detector.calibration_frames:
                    self.messages.put(('log',
                        'Listening. Say "Go to area A", "Go to the laboratory", '
                        'or "Stop". Pause briefly to finish your command.'))
                if audio is not None:
                    try:
                        self.utterances.put_nowait(audio)
                    except queue.Full:
                        self.messages.put(('warning',
                            'Recognition is busy; phrase skipped. Wait for the result, then repeat.'))

            self.messages.put(('log',
                f"Microphone: {device_info['name']} ({sample_rate} Hz). "
                'Keep quiet briefly while background noise is measured.'))
            with sd.InputStream(
                device=mic, samplerate=sample_rate, channels=1, dtype='float32',
                blocksize=round(sample_rate * .02), callback=capture,
            ) as stream:
                while not self.stop_event.is_set():
                    if not stream.active:
                        raise RuntimeError('Microphone stream stopped unexpectedly')
                    try:
                        audio = self.utterances.get(timeout=.1)
                    except queue.Empty:
                        continue
                    self.messages.put(('log', 'Recognizing command; microphone remains active...'))
                    result = model.transcribe(
                        resample_for_whisper(audio, sample_rate),
                        language=settings['language'], fp16=False, temperature=0,
                        condition_on_previous_text=False,
                    )
                    text = result['text'].strip()
                    if text and not self.stop_event.is_set():
                        self.messages.put(('text', text))
        except Exception as error:
            self.messages.put(('warning',
                f'Speech recognition stopped: {error}. Check the microphone/model and restart the node.'))

    def stop(self):
        self.stop_event.set()
        self.worker.join(timeout=2.)


def main(args=None):
    rclpy.init(args=args)
    node = SpeechRecognition()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
