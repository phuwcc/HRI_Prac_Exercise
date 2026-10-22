"""Gesture state machine and odometry-based motions, independent of ROS."""

from dataclasses import dataclass
import math


SELECTIONS = {'Wave': 'greet', 'Pointing_Up': 'back_and_forth', 'Victory': 'circle'}
GESTURES = set(SELECTIONS) | {'Thumb_Up', 'Open_Palm', 'Closed_Fist'}


@dataclass(frozen=True)
class Settings:
    linear_speed: float = 0.15
    angular_speed: float = 0.5
    travel_distance: float = 0.4
    circle_radius: float = 0.6
    greeting_angle: float = 0.5
    signal_timeout: float = 2.0
    selection_timeout: float = 10.0
    motion_timeout: float = 120.0

    def __post_init__(self):
        for name, value in vars(self).items():
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f'{name} must be finite and positive')
        if self.linear_speed > 0.3 or self.angular_speed > 1.0:
            raise ValueError('Maximum speeds: 0.3 m/s and 1.0 rad/s')
        if self.linear_speed / self.circle_radius > 1.0:
            raise ValueError('Circle angular speed must not exceed 1.0 rad/s')


class Controller:
    def __init__(self, settings=None):
        self.settings = settings or Settings()
        self.selected = None
        self.active = None
        self.last_gesture = None
        self.last_frame = -math.inf
        self.last_hand = -math.inf
        self.hand_present = False
        self.selected_at = -math.inf
        self.started = 0.0
        self.segment = 0
        self.origin = None
        self.previous_yaw = None
        self.turned = 0.0
        self.status = 'WAITING'

    def stop(self, reason, clear=True):
        self.active = None
        self.origin = None
        self.previous_yaw = None
        self.turned = 0.0
        if clear:
            self.selected = None
        self.status = reason

    def receive(self, gesture, now):
        if gesture not in GESTURES:
            return
        edge = gesture != self.last_gesture
        self.last_gesture = gesture
        # Safety commands are never debounced in the controller.
        if gesture == 'Open_Palm':
            self.stop('STOPPED', clear=False)
            if self.selected and edge:
                self.selected_at = now
        elif gesture == 'Closed_Fist':
            self.stop('WAITING')
        elif edge and not self.active:
            if gesture in SELECTIONS:
                self.selected = SELECTIONS[gesture]
                self.selected_at = now
                self.status = f'SELECTED: {self.selected}'
            elif gesture == 'Thumb_Up' and self.selected:
                self.active = self.selected
                self.started = now
                self.segment = 0
                self.origin = None
                self.previous_yaw = None
                self.turned = 0.0
                self.status = f'RUNNING: {self.active}'

    def track(self, hand_present, now):
        """Refresh only from an actually processed camera frame, before label filtering."""
        self.last_frame = now
        self.hand_present = hand_present
        if hand_present:
            self.last_hand = now

    def signal_status(self, now):
        if now - self.last_frame > self.settings.signal_timeout:
            return 'SIGNAL_LOST'
        return None

    def command(self, now, pose, safe=True):
        # Idle/terminal states must not be overwritten by a continuously firing watchdog.
        # A selection gets its own deadline so switching hand poses does not erase it.
        if self.active:
            lost = self.signal_status(now)
            if lost:
                self.stop(lost)
        elif self.selected and now - self.selected_at > self.settings.selection_timeout:
            self.stop('SELECTION_EXPIRED')
        if not self.active:
            return 0.0, 0.0
        if not safe or now - self.started > self.settings.motion_timeout:
            self.stop('SAFETY_STOP')
            return 0.0, 0.0
        self.status = f'RUNNING: {self.active}'
        x, y, yaw = pose
        if self.origin is None:
            self.origin = (x, y)
            self.previous_yaw = yaw
        delta = math.atan2(math.sin(yaw - self.previous_yaw),
                           math.cos(yaw - self.previous_yaw))
        self.turned += delta
        self.previous_yaw = yaw
        s = self.settings
        if self.active == 'back_and_forth':
            if math.hypot(x - self.origin[0], y - self.origin[1]) >= s.travel_distance:
                self.segment += 1
                self.origin = (x, y)
                if self.segment >= 8:  # Four complete forward/backward pairs.
                    self.stop('COMPLETED')
                return 0.0, 0.0
            return (s.linear_speed if self.segment % 2 == 0 else -s.linear_speed), 0.0
        if self.active == 'circle':
            if self.turned >= 2 * math.pi:
                self.stop('COMPLETED')
                return 0.0, 0.0
            return s.linear_speed, s.linear_speed / s.circle_radius
        target = (s.greeting_angle, -s.greeting_angle, 0.0)[self.segment]
        error = target - self.turned
        if abs(error) < 0.04:
            self.segment += 1
            if self.segment == 3:
                self.stop('COMPLETED')
            return 0.0, 0.0
        return 0.0, math.copysign(s.angular_speed, error)
