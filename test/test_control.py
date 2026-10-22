"""Exercise command ordering, interrupted motions, watchdogs, and noisy gestures."""

import math

import pytest

from ttbot4_handges_control.control import Controller, Settings
from ttbot4_handges_control.gestures import GestureFilter, WaveDetector


def start(gesture='Pointing_Up'):
    control = Controller()
    control.track(True, 0.0)
    control.receive(gesture, 0.0)
    control.receive('Thumb_Up', 0.1)
    return control


def test_selection_needs_confirmation():
    control = Controller()
    control.receive('Thumb_Up', 0)
    assert control.active is None
    control.receive('Victory', .1)
    assert control.command(.2, (0, 0, 0)) == (0, 0)
    control.receive('Thumb_Up', .3)
    control.track(True, .3)
    assert control.command(.3, (0, 0, 0))[0] > 0


def test_four_complete_forward_backward_pairs_and_no_repeat():
    control = start()
    for index in range(8):
        # Holding Thumb Up is a heartbeat, never another trigger.
        control.receive('Thumb_Up', .2)
        origin_x = 0 if index % 2 == 0 else .41
        destination_x = .41 if index % 2 == 0 else 0
        command = control.command(.2, (origin_x, 0, 0))
        assert math.copysign(1, command[0]) == (1 if index % 2 == 0 else -1)
        assert control.command(.3, (destination_x, 0, 0)) == (0, 0)
    assert control.status == 'COMPLETED'
    control.receive('Thumb_Up', .4)
    assert control.active is None


@pytest.mark.parametrize('gesture,status', [('Open_Palm', 'STOPPED'),
                                            ('Closed_Fist', 'WAITING')])
def test_stop_interrupts_and_requires_fresh_confirmation(gesture, status):
    control = start()
    control.receive(gesture, .2)
    assert control.command(.2, (0, 0, 0)) == (0, 0)
    assert control.status == status
    if gesture == 'Closed_Fist':
        assert control.selected is None


def test_signal_loss_clears_action_and_held_thumb_cannot_restart():
    control = start()
    control.receive('None', .8)
    assert control.command(2.2, (0, 0, 0)) == (0, 0)
    assert control.selected is None
    control.track(True, 2.3)
    control.receive('Thumb_Up', 2.3)
    assert control.active is None


@pytest.mark.parametrize('safe,now', [(False, .2), (True, 121)])
def test_safety_and_timeout(safe, now):
    control = start()
    control.receive('Thumb_Up', now)
    control.track(True, now)
    assert control.command(now, (0, 0, 0), safe=safe) == (0, 0)
    assert control.status == 'SAFETY_STOP'


def test_circle_tracks_yaw_across_wraparound():
    control = start('Victory')
    for index in range(65):
        control.receive('Thumb_Up', .2)
        yaw = math.atan2(math.sin(index * .1), math.cos(index * .1))
        control.command(.2, (0, 0, yaw))
    assert control.status == 'COMPLETED'


def test_greeting_returns_to_original_heading():
    control = start('Wave')
    assert control.command(.2, (0, 0, 0))[1] > 0
    control.command(.2, (0, 0, .5))
    assert control.command(.2, (0, 0, .5))[1] < 0
    control.command(.2, (0, 0, -.5))
    assert control.command(.2, (0, 0, -.5))[1] > 0
    control.command(.2, (0, 0, 0))
    assert control.status == 'COMPLETED'


def test_confirmation_requires_exactly_five_consecutive_frames():
    gate = GestureFilter(5)
    for index in range(4):
        assert gate.update('Victory') == 'None'
        assert gate.count == index + 1
    assert gate.update('Victory') == 'Victory'
    assert gate.update('Victory') == 'Victory'
    assert gate.count == 5


@pytest.mark.parametrize('interrupt', ['Pointing_Up', 'None', 'Open_Palm', 'Closed_Fist'])
def test_interruption_resets_confirmation_and_safety_is_immediate(interrupt):
    gate = GestureFilter(5)
    for _ in range(4):
        gate.update('Victory')
    result = gate.update(interrupt)
    assert result == (interrupt if interrupt in ('Open_Palm', 'Closed_Fist') else 'None')
    for _ in range(4):
        assert gate.update('Victory') == 'None'
    assert gate.update('Victory') == 'Victory'


def test_noisy_thumb_does_not_execute_selected_action():
    control, gate = Controller(), GestureFilter(5)
    for gesture in ['Victory'] * 5 + ['Thumb_Up'] * 4 + ['None'] + ['Thumb_Up'] * 4:
        control.receive(gate.update(gesture), 0)
    assert control.selected == 'circle'
    assert control.active is None
    control.receive(gate.update('Thumb_Up'), 0)
    assert control.active == 'circle'


@pytest.mark.parametrize('value', [0, -1, 1.5, True])
def test_invalid_frame_count(value):
    with pytest.raises(ValueError):
        GestureFilter(value)


def test_wave_requires_two_direction_reversals():
    wave = WaveDetector()
    for index in range(20):
        assert not wave.update('Open_Palm', .5 + .005 * (index % 2), index * .03)
    assert not wave.update('Open_Palm', .65, .61)
    assert not wave.update('Open_Palm', .4, .7)
    assert wave.update('Open_Palm', .65, .8)
    assert not wave.update('Victory', .65, .9)
    assert not wave.update('Open_Palm', .65, 1)


@pytest.mark.parametrize('values', [{'linear_speed': float('nan')}, {'circle_radius': 0},
                                   {'angular_speed': 2.0}, {'linear_speed': -1}])
def test_invalid_settings(values):
    with pytest.raises(ValueError):
        Settings(**values)


def test_tracking_keeps_motion_alive_despite_repeated_filter_resets():
    control, gate = start(), GestureFilter(5)
    # A 4 FPS camera and uncertain class labels previously caused SIGNAL_LOST.
    # The hand is still tracked; no new command has passed the five-frame gate.
    for index in range(1, 41):
        now = index * .25
        raw = 'None' if index % 3 == 0 else 'Thumb_Up'
        control.track(True, now)
        control.receive(gate.update(raw), now)
        assert control.command(now, (0, 0, 0))[0] > 0
        assert control.active == 'back_and_forth'


def test_brief_hand_dropout_does_not_cancel_motion():
    control = start()
    control.track(False, .5)
    assert control.command(1.5, (0, 0, 0))[0] > 0
    control.track(True, 1.6)
    assert control.command(1.6, (0, 0, 0))[0] > 0


def test_robot_keeps_running_without_hand_until_stop_command():
    control = start()
    for now in range(1, 31):
        control.track(False, now)
        control.receive('None', now)
        assert control.command(now, (0, 0, 0))[0] > 0
        assert control.status == 'RUNNING: back_and_forth'
    control.receive('Open_Palm', 30.1)
    assert control.command(30.1, (0, 0, 0)) == (0, 0)
    assert control.status == 'STOPPED'


@pytest.mark.parametrize('gesture,status', [('Open_Palm', 'STOPPED'),
                                            ('Closed_Fist', 'WAITING')])
def test_stop_and_cancel_still_work_after_hand_returns(gesture, status):
    control = start()
    control.track(False, 10)
    assert control.command(10, (0, 0, 0))[0] > 0
    control.track(True, 10.1)
    control.receive(gesture, 10.1)
    assert control.command(10.1, (0, 0, 0)) == (0, 0)
    assert control.status == status


def test_dead_recognizer_stops_even_if_old_gesture_is_republished():
    control = start()
    control.receive('Thumb_Up', 2.1)
    assert control.command(2.1, (0, 0, 0)) == (0, 0)
    assert control.status == 'SIGNAL_LOST'


def test_waiting_and_completion_are_not_replaced_by_signal_lost():
    control = Controller()
    control.command(100, (0, 0, 0))
    assert control.status == 'WAITING'
    control.stop('COMPLETED')
    control.command(200, (0, 0, 0))
    assert control.status == 'COMPLETED'


def test_selection_has_time_to_change_pose_and_then_expires():
    control = Controller()
    control.receive('Victory', 0)
    control.command(3, (0, 0, 0))
    assert control.selected == 'circle'
    control.command(10.1, (0, 0, 0))
    assert control.status == 'SELECTION_EXPIRED'
    assert control.selected is None


def test_tracking_is_not_confirmation():
    control = Controller()
    control.receive('Victory', 0)
    control.track(True, 1)
    assert control.command(1, (0, 0, 0)) == (0, 0)
    assert control.active is None


def test_palm_stop_gives_a_new_confirmation_window_after_a_long_motion():
    control = start()
    control.track(True, 20)
    control.receive('Open_Palm', 20)
    assert control.command(21, (0, 0, 0)) == (0, 0)
    assert control.selected == 'back_and_forth'
    assert control.status == 'STOPPED'
    control.track(True, 21)
    control.receive('Thumb_Up', 21)
    assert control.command(21, (0, 0, 0))[0] > 0
