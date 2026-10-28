# Source from workspace root: source ttbot4_seman_nav/scripts/activate_hri.bash
if ! command -v conda >/dev/null 2>&1; then
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
else
    source "$(conda info --base)/etc/profile.d/conda.sh"
fi
conda activate hri || return
source /opt/ros/humble/setup.bash
if test -f install/setup.bash; then source install/setup.bash; fi
if test -f install_seman/setup.bash; then source install_seman/setup.bash; fi
export ROS_LOCALHOST_ONLY=1
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
# Keep all terminals on the same DDS discovery settings.
export CYCLONEDDS_URI="file://$(pwd)/turtlebot_simu/config/cyclonedds.xml"
