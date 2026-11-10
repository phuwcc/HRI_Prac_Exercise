"""Prevent stale Gazebo servers from sharing discovery with a fresh launch."""
import importlib.util
from pathlib import Path

from launch import LaunchContext


def test_each_launch_gets_a_shared_but_unique_gazebo_partition():
    path = Path(__file__).resolve().parents[1] / 'launch/coursework.launch.py'
    spec = importlib.util.spec_from_file_location('coursework_launch', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    contexts = []
    for _ in range(2):
        context = LaunchContext()
        # An inherited stale partition must be replaced, not reused.
        context.environment['IGN_PARTITION'] = 'stale_server'
        context.environment['GZ_PARTITION'] = 'stale_server'
        for action in module.simulator_environment():
            action.execute(context)
        assert context.environment['IGN_PARTITION'] == context.environment['GZ_PARTITION']
        assert context.environment['IGN_PARTITION'] != 'stale_server'
        contexts.append(context.environment['IGN_PARTITION'])
    assert contexts[0] != contexts[1]
