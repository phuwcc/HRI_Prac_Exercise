"""OpenCV dashboard: live hand skeleton, confirmation, and ROS feedback."""

import cv2
import numpy as np


WINDOW = 'TurtleBot 4 | Hand Gesture Control'
BACKGROUND = (22, 19, 17)
PANEL = (37, 31, 27)
TEXT = (244, 239, 231)
MUTED = (167, 150, 132)
TEAL = (171, 214, 72)
AMBER = (93, 193, 250)
RED = (107, 106, 245)
FINGERS = (
    ((0, 1, 2, 3, 4), (155, 143, 255)),
    ((0, 5, 6, 7, 8), (122, 216, 124)),
    ((5, 9, 10, 11, 12), (245, 203, 102)),
    ((9, 13, 14, 15, 16), (249, 153, 156)),
    ((13, 17, 18, 19, 20), (139, 215, 245)),
    ((0, 17), TEAL),
)
NAMES = {'None': 'No gesture', 'Pointing_Up': 'Pointing Up', 'Thumb_Up': 'Thumb Up',
         'Open_Palm': 'Open Palm', 'Closed_Fist': 'Closed Fist', 'Victory': 'Victory',
         'Wave': 'Wave'}
BEHAVIORS = {'greet': 'Greeting', 'back_and_forth': 'Forward / back x4', 'circle': 'Circle'}


def text(canvas, label, x, y, size=0.55, color=TEXT):
    cv2.putText(canvas, str(label), (x, y), cv2.FONT_HERSHEY_SIMPLEX,
                size, color, 1, cv2.LINE_AA)


def render_dashboard(frame, landmarks, *, gesture, score, filtered, count, required,
                     fps, state, linked, command, command_live, subscribers):
    """Render a fixed logical canvas, independently of webcam aspect ratio."""
    canvas = np.full((820, 1280, 3), BACKGROUND, dtype=np.uint8)
    text(canvas, 'TURTLEBOT 4', 24, 38, 0.9)
    text(canvas, 'HAND GESTURE CONTROL', 24, 67, 0.53, MUTED)
    text(canvas, f'WEBCAM LIVE   /   {fps:.1f} FPS', 908, 43, 0.55, TEAL)
    text(canvas, '01  CAMERA + HAND TRACKING', 24, 100, 0.5, MUTED)
    text(canvas, '02  CONFIRMATION + ROBOT', 848, 100, 0.5, MUTED)

    # Preserve the webcam's aspect ratio; draw the 21 landmarks and finger links.
    image = frame.copy()
    h, w = image.shape[:2]
    if landmarks:
        points = [(int(p.x * w), int(p.y * h)) for p in landmarks]
        for chain, color in FINGERS:
            for a, b in zip(chain, chain[1:]):
                cv2.line(image, points[a], points[b], color, 3, cv2.LINE_AA)
        for point in points:
            cv2.circle(image, point, 5, BACKGROUND, -1, cv2.LINE_AA)
            cv2.circle(image, point, 3, TEXT, -1, cv2.LINE_AA)
    ratio = min(800 / w, 600 / h)
    video = cv2.resize(image, (int(w * ratio), int(h * ratio)))
    vh, vw = video.shape[:2]
    cv2.rectangle(canvas, (24, 112), (824, 712), PANEL, -1)
    x, y = 24 + (800 - vw) // 2, 112 + (600 - vh) // 2
    canvas[y:y + vh, x:x + vw] = video
    cv2.rectangle(canvas, (24, 112), (824, 712), (74, 65, 54), 1)

    cv2.rectangle(canvas, (848, 112), (1256, 712), PANEL, -1)
    left = 872
    text(canvas, 'RECOGNIZED GESTURE', left, 143, 0.45, MUTED)
    text(canvas, NAMES.get(gesture, gesture), left, 180, 0.85)
    text(canvas, f'AI confidence  {score:.0%}', left, 211, 0.5, MUTED)
    cv2.rectangle(canvas, (left, 226), (1232, 233), BACKGROUND, -1)
    cv2.rectangle(canvas, (left, 226), (left + int(360 * min(max(score, 0), 1)), 233), TEAL, -1)
    safety = gesture in ('Open_Palm', 'Closed_Fist')
    text(canvas, 'IMMEDIATE STOP / CANCEL' if safety else f'CONFIRMATION  {count}/{required}',
         left, 261, 0.52, RED if safety else TEAL)
    # Five segments by default, also supports other configured frame counts.
    gap, cells = 6, min(required, 10)
    cell_width = (360 - gap * (cells - 1)) / cells
    for index in range(cells):
        x0 = left + int(index * (cell_width + gap))
        cv2.rectangle(canvas, (x0, 277), (x0 + max(1, int(cell_width)), 288),
                      (RED if safety else TEAL) if index < count * cells / required
                      else BACKGROUND, -1)
    text(canvas, f'Sent: {NAMES.get(filtered, filtered)}', left, 317, 0.5)
    cv2.line(canvas, (left, 334), (1232, 334), (74, 65, 54), 1)

    selected = BEHAVIORS.get(state.get('selected'), 'Choose a behavior') if linked else '--'
    text(canvas, 'ROBOT FEEDBACK' if linked else 'ROBOT FEEDBACK OFFLINE',
         left, 363, 0.45, TEAL if linked else RED)
    text(canvas, selected, left, 396, 0.65)
    status = state.get('status', 'WAITING FOR NODE') if linked else 'NO RECENT FEEDBACK'
    status_key = status.split(':')[0]
    status_color = TEAL if status_key in ('SELECTED', 'RUNNING', 'COMPLETED') else AMBER
    if status_key not in ('SELECTED', 'RUNNING', 'COMPLETED', 'WAITING'):
        status_color = RED
    text(canvas, status_key.replace('_', ' '), left, 427, 0.62, status_color)
    sensors = 'READY' if state.get('sensors_ready') else 'WAITING'
    clearance = state.get('clearance')
    scan = f'{clearance:.2f} m' if clearance is not None else 'No nearby return'
    text(canvas, f'Sensors: {sensors}    Mode: DIRECT' if linked else 'Sensors: --',
         left, 460, 0.43, MUTED)
    text(canvas, f'LiDAR: {scan}' if linked else 'LiDAR: --', left, 483, 0.46,
         RED if linked and state.get('obstacle') else MUTED)
    if not linked:
        tracking, tracking_color = 'Hand: --', MUTED
    elif not state.get('tracking_alive'):
        tracking, tracking_color = 'Camera: OFF', RED
    elif state.get('hand_present'):
        tracking, tracking_color = 'Hand: OK', TEAL
    else:
        tracking, tracking_color = 'Hand: NONE', MUTED
    text(canvas, tracking, 1080, 483, 0.43, tracking_color)
    motion = f'v {command[0]:+.2f} m/s    w {command[1]:+.2f} rad/s' if command_live else '--'
    text(canvas, 'CMD_VEL: ' + motion, left, 509, 0.43)
    cv2.line(canvas, (left, 526), (1232, 526), (74, 65, 54), 1)
    text(canvas, '1  SELECT    Pointing Up / Victory / Wave', left, 552, 0.43)
    text(canvas, f'2  CONFIRM   Thumb Up for {required} frames', left, 577, 0.43, TEAL)
    text(canvas, '3  EXECUTE   You may lower your hand', left, 602, 0.43)
    text(canvas, 'STOP  Open Palm    |    CANCEL  Closed Fist', left, 639, 0.42, RED)
    text(canvas, 'New label or missing hand resets the counter.', left, 680, 0.4, MUTED)

    # Link indicators use live ROS discovery and message freshness, not fixed colors.
    steps = [('WEBCAM', True), ('GESTURE NODE', True),
             ('BEHAVIOR NODE', linked and subscribers > 0), ('CMD_VEL TOPIC', command_live)]
    for index, (label, online) in enumerate(steps):
        x0 = 24 + index * 314
        cv2.rectangle(canvas, (x0, 742), (x0 + 280, 790), PANEL, -1)
        cv2.circle(canvas, (x0 + 17, 766), 4, TEAL if online else RED, -1)
        text(canvas, label, x0 + 31, 772, 0.49, TEXT if online else MUTED)
        if index < len(steps) - 1:
            text(canvas, '>', x0 + 291, 772, 0.55, MUTED)
    return canvas
