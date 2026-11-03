import pytest

from ttbot4_seman_nav.runtime import check_tf2_versions


@pytest.mark.parametrize('package,version', [
    ('tf2', '0.25.21'), ('tf2', '0.25.22'), ('tf2', '0.25.23'),
    ('tf2_ros', '0.25.23'),
])
def test_deadlock_releases_are_rejected_in_either_library(package, version):
    versions = {'tf2': '0.25.20', 'tf2_ros': '0.25.20'}
    versions[package] = version
    with pytest.raises(RuntimeError, match='setup_tf2_compat.bash'):
        check_tf2_versions(versions)


def test_compat_overlay_is_allowed():
    check_tf2_versions({'tf2': '0.25.20', 'tf2_ros': '0.25.20'})
