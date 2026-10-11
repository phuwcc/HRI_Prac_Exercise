# TurtleBot 4 Simulation, SLAM và Nav2

Package ROS 2 Humble mô phỏng TurtleBot 4 trong Gazebo, xây dựng bản đồ bằng
SLAM Toolbox, localization bằng AMCL và autonomous navigation bằng Nav2.

```text
Gazebo → /scan + /odom → SLAM Toolbox → map.yaml + map.pgm
                                      ↓
Nav2 Goal → planner → controller → /cmd_vel → TurtleBot 4
```

## Cài dependency

Yêu cầu Ubuntu 22.04 và ROS 2 Humble Desktop.

```bash
sudo apt update
sudo apt install \
  ros-humble-turtlebot4-simulator \
  ros-humble-turtlebot4-navigation \
  ros-humble-turtlebot4-viz \
  ros-humble-irobot-create-nodes \
  ros-humble-slam-toolbox \
  ros-humble-navigation2 \
  ros-humble-nav2-bringup \
  ros-humble-nav2-simple-commander \
  ros-humble-teleop-twist-keyboard
```

## Build

```bash
cd ~/ur_robot_drawing
source /opt/ros/humble/setup.bash

rosdep install --ignore-src --from-paths turtlebot_simu -r -y
colcon build --packages-select turtlebot_simu --symlink-install
source install/setup.bash
```

Mỗi terminal mới đều phải source ROS 2 và workspace:

```bash
source /opt/ros/humble/setup.bash
source ~/ur_robot_drawing/install/setup.bash
export ROS_LOCALHOST_ONLY=1
```

Các launch file cũng tự đặt `ROS_LOCALHOST_ONLY=1`. Cần đặt cùng giá trị trong
mọi terminal chạy teleop, lưu map, waypoint hoặc lệnh kiểm tra topic để các node
nhìn thấy nhau.

## 1. Kiểm tra simulation

Terminal 1 — Gazebo, TurtleBot 4 và RViz:

```bash
cd ~/ur_robot_drawing
source /opt/ros/humble/setup.bash
source install/setup.bash

ros2 launch turtlebot_simu simulation.launch.py check_topics:=true
```

Nếu Gazebo đang pause, bấm **Play**. Khi simulation hoạt động đúng, terminal sẽ
in `PASS` cho `/scan`, `/odom` và `/cmd_vel`.

`PASS` xác nhận có dữ liệu sensor và subscriber tương thích của `/cmd_vel`.
Cần dùng teleop và quan sát robot/odometry để xác nhận chuyển động thực tế.
Node kiểm tra không publish lệnh vận tốc, nên có thể chạy khi robot đang di chuyển.

Terminal 2 — điều khiển robot:

```bash
source /opt/ros/humble/setup.bash
source ~/ur_robot_drawing/install/setup.bash
export ROS_LOCALHOST_ONLY=1

ros2 action send_goal /undock irobot_create_msgs/action/Undock '{}'
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

Khi kết thúc, bấm `Ctrl+C` **một lần** ở terminal teleop, sau đó bấm `Ctrl+C`
**một lần** ở terminal launch và chờ các node dừng. Có thể đóng cửa sổ Gazebo;
package sẽ tự shutdown phần launch còn lại. Không nhấn `Ctrl+C` liên tục.

Kiểm tra topic thủ công khi cần:

```bash
ros2 topic hz /scan
ros2 topic hz /odom
ros2 topic info /cmd_vel -v
ros2 run turtlebot_simu topic_check --timeout 30
```

## 2. Xây dựng bản đồ

Dừng simulation cũ bằng `Ctrl+C`.

Terminal 1 — Gazebo, SLAM Toolbox và RViz:

```bash
cd ~/ur_robot_drawing
source /opt/ros/humble/setup.bash
source install/setup.bash

ros2 launch turtlebot_simu mapping.launch.py world:=maze
```

Terminal 2 — teleoperation:

```bash
source /opt/ros/humble/setup.bash
source ~/ur_robot_drawing/install/setup.bash
export ROS_LOCALHOST_ONLY=1

ros2 action send_goal /undock irobot_create_msgs/action/Undock '{}'
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

Điều khiển robot đi chậm quanh phần lớn khu vực. Nên quay lại các vị trí đã đi
qua để SLAM thực hiện loop closure. Trên RViz cần thấy robot, LaserScan và map;
LaserScan phải khớp với tường, không có tường đôi hoặc vùng lệch rõ rệt.

Terminal 3 — lưu bản đồ trong khi mapping vẫn đang chạy:

```bash
cd ~/ur_robot_drawing
source /opt/ros/humble/setup.bash
source install/setup.bash
export ROS_LOCALHOST_ONLY=1

ros2 run turtlebot_simu save_map \
  --output "$PWD/turtlebot_simu/maps/map"
```

Kiểm tra kết quả:

```bash
ls -lh turtlebot_simu/maps/map.yaml turtlebot_simu/maps/map.pgm
```

Hai file trong `maps/` ban đầu chỉ là map mẫu. Phải chạy bước trên để thay bằng
map thật trước khi thực hiện localization và navigation.
Navigation sẽ báo lỗi trước khi mở Gazebo nếu vẫn dùng map mẫu hoặc thiếu ảnh map.

Sau khi lưu map, dừng mapping và build lại:

```bash
cd ~/ur_robot_drawing
source /opt/ros/humble/setup.bash
colcon build --packages-select turtlebot_simu --symlink-install
source install/setup.bash
```

## 3. Localization và Nav2

Terminal 1 — mở lại đúng world, load map, chạy AMCL và Nav2:

```bash
cd ~/ur_robot_drawing
source /opt/ros/humble/setup.bash
source install/setup.bash

ros2 launch turtlebot_simu navigation.launch.py world:=maze
```

Trong RViz:

1. Chọn **2D Pose Estimate**.
2. Chọn đúng vị trí và hướng hiện tại của robot trong Gazebo.
3. Chờ particle cloud hội tụ và LaserScan trùng với tường.
4. Chọn **Nav2 Goal** và đặt goal trong vùng trống của map.

Robot được spawn trên dock. Trước goal đầu tiên, chạy lệnh undock ở terminal
đã source và đặt `ROS_LOCALHOST_ONLY=1`, chờ trạng thái `SUCCEEDED`:

```bash
ros2 action send_goal /undock irobot_create_msgs/action/Undock '{}'
```

Sau khi đặt goal, không dùng teleop. Robot phải tự lập đường, tránh vật cản và
đi tới goal.

`config/nav2.yaml` kế thừa cấu hình TurtleBot 4 Humble. Global costmap dùng bản
đồ tĩnh; local costmap dùng LiDAR và inflation để tránh vật cản, không dùng
static layer trong cửa sổ rolling và dùng frame `map` để kiểm tra TF localization
trước khi active. Controller Regulated Pure Pursuit chạy 10 Hz, vận tốc tối đa
0,2 m/s; planner chỉ lập đường trong vùng đã biết.

Dùng map ở vị trí khác:

```bash
ros2 launch turtlebot_simu navigation.launch.py \
  world:=maze \
  map:=/duong/dan/tuyet/doi/map.yaml
```

## 4. Chạy ba navigation goal

Cách đơn giản nhất để quay video là đặt lần lượt ba goal bằng **Nav2 Goal** trên
RViz. Các goal phải nằm ở ba khu vực khác nhau.

Package cũng có node chạy tự động ba goal. Sửa tọa độ an toàn trong
`config/waypoints.yaml`, build lại, đặt initial pose trên RViz rồi chạy:

Terminal 2:

```bash
cd ~/ur_robot_drawing
source /opt/ros/humble/setup.bash
source install/setup.bash
export ROS_LOCALHOST_ONLY=1

ros2 run turtlebot_simu waypoint_nav
```

Node dùng simulation time, chờ pose AMCL đã đặt trên RViz và các node Nav2 active;
không tự ghi đè initial pose. Có thể chỉnh thời gian chờ:

```bash
ros2 run turtlebot_simu waypoint_nav --ready-timeout 120 --goal-timeout 180
```

Trước khi gửi goal, node đối chiếu toàn bộ tọa độ với `/map`, từ chối điểm nằm
ngoài map, trong vùng chưa biết hoặc cách vật cản dưới `--clearance` (mặc định
0,25 m). Kiểm tra này không thay thế lập kế hoạch và tránh vật cản của Nav2.
Sau kết quả `SUCCEEDED`, node còn đối chiếu pose AMCL với vị trí/hướng goal;
nếu robot chưa đến đích, node báo lỗi thay vì ghi nhận thành công.

Nếu robot đang dock và không nhận teleop, undock rồi mới di chuyển:

```bash
ros2 action send_goal /undock irobot_create_msgs/action/Undock '{}'
```

Với namespace (ví dụ `namespace:=robot`), topic trở thành `/robot/scan`,
`/robot/odom`, `/robot/cmd_vel`. Các lệnh ở terminal riêng cần cùng namespace:

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -r __ns:=/robot
ros2 run turtlebot_simu topic_check --ros-args -r __ns:=/robot
ros2 run turtlebot_simu save_map --output "$PWD/turtlebot_simu/maps/map" --map-topic /robot/map
ros2 run turtlebot_simu waypoint_nav --ros-args -r __ns:=/robot
```

Ví dụ cấu hình:

```yaml
goals:
  - {x: 2.0, y: 0.0, yaw: 0.0}
  - {x: 2.0, y: -1.0, yaw: 0.0}
  - {x: -2.0, y: 0.0, yaw: 0.0}
```

Đây chỉ là tọa độ mẫu. Chỉ sử dụng goal nằm trong vùng trắng của map và cách
tường, vật cản đủ xa.

## Launch arguments

Các launch file dùng chung những tham số sau:

| Tham số | Mặc định | Nội dung |
|---|---:|---|
| `world` | `maze` | World Gazebo |
| `model` | `standard` | `standard` hoặc `lite` |
| `rviz` | `true` | Bật/tắt RViz |
| `x`, `y`, `z`, `yaw` | `0.0` | Pose spawn của robot |

Mapping hỗ trợ thêm `sync:=true|false`. Navigation hỗ trợ `map:=<đường dẫn>`.

Ví dụ:

```bash
ros2 launch turtlebot_simu mapping.launch.py \
  world:=maze model:=standard sync:=true
```

## Topics chính

| Topic | Nội dung |
|---|---|
| `/scan` | Dữ liệu LaserScan từ LiDAR |
| `/odom` | Odometry của robot |
| `/cmd_vel` | Lệnh vận tốc gửi tới robot |
| `/map` | Occupancy grid từ SLAM hoặc map server |
| `/tf`, `/tf_static` | Quan hệ giữa `map`, `odom`, `base_link` và sensor |
| `/plan` | Global path do Nav2 tạo |
| `/particle_cloud` | Các giả thuyết pose của AMCL |

## Cấu trúc package

```text
turtlebot_simu/
├── launch/
│   ├── simulation.launch.py
│   ├── mapping.launch.py
│   └── navigation.launch.py
├── turtlebot_simu/
│   ├── topic_check.py
│   ├── save_map.py
│   └── waypoint_nav.py
├── config/waypoints.yaml
├── maps/map.yaml
├── maps/map.pgm
└── docs/BAO_CAO.md
```

## Lỗi thường gặp

Không tìm thấy package:

```text
Package 'turtlebot4_ignition_bringup' not found
```

Cài lại dependency, source và build lại workspace.

RViz báo `Frame [map] does not exist`: kiểm tra Gazebo đã bấm Play, `/scan` và
`/odom` đang publish, đồng thời SLAM hoặc localization đang chạy.

Gazebo đứng ở `Requesting list of world names`: world `warehouse` đang tải
nhiều model từ Gazebo Fuel. Dùng `world:=maze` để chạy hoàn toàn bằng asset có
sẵn trên máy. Chỉ dùng `warehouse` sau khi mạng đã tải xong toàn bộ model.

Nếu sau khi bấm `Ctrl+C` xuất hiện stack trace Qt/QML hoặc `Segmentation fault`
của `ign gazebo gui`, đây là lỗi lúc đóng GUI của Ignition Fortress. Simulation
không lỗi nếu trước đó robot hoạt động và health check đã báo đủ ba dòng `PASS`.

Các dòng `process has not terminated`, `SIGTERM` hoặc `SIGKILL` lúc thoát thường
do đóng Gazebo rồi nhấn `Ctrl+C` nhiều lần trước khi ROS hoàn tất shutdown. Build
lại package để nhận cơ chế tự shutdown mới, sau đó chỉ nhấn `Ctrl+C` một lần và
chờ khoảng 10 giây.

Gazebo mở được world nhưng không thấy robot và terminal chỉ lặp
`Waiting messages on topic [robot_description]`: Fast DDS có thể còn
shared-memory từ lần bị `SIGKILL`. Dừng toàn bộ ROS/Gazebo, dọn các file zombie
rồi chạy lại:

```bash
/opt/ros/humble/bin/fastdds shm clean
export ROS_LOCALHOST_ONLY=1
```

AMCL không xác định được pose: dùng **2D Pose Estimate**, chọn đúng vị trí và
hướng robot rồi di chuyển robot một đoạn ngắn.

Nav2 không nhận goal: kiểm tra AMCL đã hội tụ, goal nằm trong vùng trống và các
Nav2 lifecycle node đang ở trạng thái `active`:

```bash
ros2 lifecycle get /amcl
ros2 lifecycle get /planner_server
ros2 lifecycle get /controller_server
```

## Checklist nộp bài

- `maps/map.yaml` và `maps/map.pgm` là map được tạo từ SLAM, không phải map mẫu.
- Video có quá trình mapping, map hoàn chỉnh, load map và localization.
- Video có ít nhất ba navigation goal thành công, không dùng teleop sau khi đặt goal.
- Google Drive bật quyền xem công khai.
- GitHub Public chứa source, launch, map, config và README.
- Hoàn thiện `docs/BAO_CAO.md`, thêm ảnh/link thật và xuất thành PDF.

Tài liệu:

- [TurtleBot 4 Simulator](https://turtlebot.github.io/turtlebot4-user-manual/software/turtlebot4_simulator.html)
- [TurtleBot 4 Navigation](https://turtlebot.github.io/turtlebot4-user-manual/tutorials/navigation.html)
- [Navigation2](https://docs.nav2.org/)
