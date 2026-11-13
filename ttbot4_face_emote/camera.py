"""A single immutable frame slot: slow consumers skip old camera frames."""
import threading


class LatestFrame:
    def __init__(self):
        self.condition = threading.Condition()
        self.frame = None
        self.sequence = 0
        self.closed = False

    def put(self, frame, captured_at):
        with self.condition:
            if self.closed:
                return
            self.sequence += 1
            self.frame = (self.sequence, frame, captured_at)
            self.condition.notify_all()

    def snapshot(self):
        with self.condition:
            return self.frame

    def after(self, sequence, timeout=0.1):
        with self.condition:
            self.condition.wait_for(lambda: self.closed or self.sequence > sequence, timeout)
            if self.closed or self.sequence <= sequence:
                return None
            return self.frame

    def close(self):
        with self.condition:
            self.closed = True
            self.condition.notify_all()
