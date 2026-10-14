# TurtleBot 4: SLAM và Navigation

Hướng dẫn có hai phần độc lập:

| Phần | Mục đích | Lệnh khởi động |
|---|---|---|
| 1. SLAM | Điều khiển robot để quét và lưu bản đồ | `mapping.launch.py` |
| 2. Navigation | Load bản đồ đã lưu và điều hướng bằng Nav2 | `navigation.launch.py` |

Mỗi launch tự mở Gazebo và RViz. Chỉ chạy một phần tại một thời điểm.
Không cần chạy `simulation.launch.py` trước: launch đó chỉ mô phỏng robot,
không tạo bản đồ.

## Chuẩn bị — chỉ làm lần đầu

Yêu cầu Ubuntu 22.04 và ROS 2 Humble Desktop. Các lệnh bên dưới dùng Bash,
workspace tại `~/ur_robot_drawing` và world `small_room`.

World mặc định mới là phòng **6 × 6 m**, có bốn tường bao, một vách ngăn,
một khối hộp và một trụ. World nằm trong `worlds/small_room.sdf`, không cần tải
model môi trường từ Fuel. Đi vòng qua đầu phía nam của vách ngăn để khảo sát
cả hai phía phòng. Có thể quay lại môi trường cũ bằng `world:=maze`.

Phải quét SLAM lại khi đổi world; **không dùng map của `maze` cho `small_room`**.
Các lệnh dưới lưu map mới với tên `small_room`, không ghi đè `maps/map.*` cũ.
World nhỏ hơn giúp giảm phạm vi khảo sát, không bảo đảm sửa được lỗi Nav2/TF.

Cài dependency:

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
  ros-humble-rmw-cyclonedds-cpp \
  ros-humble-teleop-twist-keyboard
```

Build package:

```bash
cd ~/ur_robot_drawing
source /opt/ros/humble/setup.bash
rosdep install --ignore-src --from-paths turtlebot_simu -r -y
colcon build --packages-select turtlebot_simu --symlink-install
```

Các khối lệnh chạy bên dưới đã bao gồm source ROS, source workspace và
`ROS_LOCALHOST_ONLY=1`. Copy toàn bộ khối vào đúng terminal.

## Phần 1 — SLAM: quét và lưu bản đồ

### Terminal 1: mở Gazebo, SLAM Toolbox và RViz

Dừng mọi launch simulation/navigation cũ trước khi chạy:

```bash
cd ~/ur_robot_drawing
source /opt/ros/humble/setup.bash
source install/setup.bash
export ROS_LOCALHOST_ONLY=1

ros2 launch turtlebot_simu mapping.launch.py world:=small_room
```

Giữ terminal này chạy trong suốt quá trình quét và lưu map.

Mapping mặc định dùng SLAM bất đồng bộ (`sync:=false`) và cấu hình nhẹ trong
`config/slam.yaml`: xử lý mỗi 3 scan, khoảng cách thời gian tối thiểu 0.5 giây,
cập nhật map mỗi 2 giây và giảm xử lý khi robot gần như đứng yên.
Map vẫn có độ phân giải 5 cm và bật loop closure. Map trên RViz cập nhật thưa
hơn; đi chậm khoảng 0.2 m/s như lệnh teleop bên dưới.

Nếu vừa cập nhật repo, build lại trước khi chạy để nhận cấu hình mới:

```bash
cd ~/ur_robot_drawing
source /opt/ros/humble/setup.bash
colcon build --packages-select turtlebot_simu --symlink-install
```

Để giảm tải hiển thị, đặt **Global Options → Frame Rate = 10** trong RViz.
Nếu vẫn nặng, có thể tắt RViz và quan sát robot trong Gazebo:

```bash
ros2 launch turtlebot_simu mapping.launch.py world:=small_room rviz:=false
```

SLAM và lưu map vẫn hoạt động khi tắt RViz. Giảm tải không thay thế việc kiểm
tra TF nếu cảnh báo `queue is full` tiếp tục lặp lại.

Nếu chỉ cần Gazebo server và xem map trên RViz, không mở giao diện Gazebo:

```bash
ros2 launch turtlebot_simu mapping.launch.py world:=small_room headless:=true
```

Để kiểm tra simulation riêng:

```bash
ros2 launch turtlebot_simu simulation.launch.py world:=small_room check_topics:=true
```

Trong Gazebo, bấm **Play** nếu simulation đang pause. Trong RViz kiểm tra:

- **Global Options → Fixed Frame:** `map`.
- **Map:** được bật, Topic là `/map`.
- **LaserScan:** được bật, Topic là `/scan`.

Map sẽ xuất hiện khi SLAM nhận được LaserScan và TF hợp lệ. Nếu chưa thấy map,
xem mục kiểm tra phía dưới trước khi chạy lệnh lưu.

### Terminal 2: undock và điều khiển robot

```bash
cd ~/ur_robot_drawing
source /opt/ros/humble/setup.bash
source install/setup.bash
export ROS_LOCALHOST_ONLY=1

ros2 action send_goal /undock irobot_create_msgs/action/Undock '{}'
```

Chờ kết quả `SUCCEEDED`, sau đó chạy trong cùng terminal:

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard \
  --ros-args -p speed:=0.2 -p turn:=0.5
```

Nhấp vào terminal teleop để nhận phím:

| Phím | Thao tác |
|---|---|
| `i` | Đi tới |
| `,` | Đi lùi |
| `j` / `l` | Quay trái / phải |
| `k` | Dừng |
| `z` / `q` | Giảm / tăng tốc độ |

Đi chậm qua các hành lang và phần lớn khu vực trống. Quay lại một số vị trí
đã đi qua để SLAM khép vòng. Trên RViz, map phải mở rộng theo đường đi,
LaserScan khớp với tường, không có tường đôi hoặc vùng lệch rõ rệt.

### Terminal 3: lưu map khi SLAM vẫn đang chạy

Dừng robot bằng phím `k` ở Terminal 2. Giữ Terminal 1 chạy, mở Terminal 3:

```bash
cd ~/ur_robot_drawing
source /opt/ros/humble/setup.bash
source install/setup.bash
export ROS_LOCALHOST_ONLY=1

ros2 run turtlebot_simu save_map \
  --output "$PWD/turtlebot_simu/maps/small_room" \
  --timeout 30
```

Lệnh này tạo map của phòng nhỏ (ghi đè nếu đã lưu cùng tên trước đó).
Chỉ coi là lưu thành công khi có:

```text
Map saved successfully: .../small_room.yaml and .../small_room.pgm
```

Kiểm tra trong cùng terminal:

```bash
ls -lh turtlebot_simu/maps/small_room.yaml turtlebot_simu/maps/small_room.pgm
file turtlebot_simu/maps/small_room.pgm
head turtlebot_simu/maps/small_room.yaml
```

Map ban đầu của repository là map mẫu 40 × 40. Map mới phải phù hợp với vùng
đã quét trên RViz và không còn dòng `STARTER MAP ONLY` trong YAML.
Kích thước ảnh riêng lẻ không đủ để kết luận chất lượng bản đồ.

### Kết thúc SLAM

Sau khi lưu thành công:

1. Nhấn `Ctrl+C` một lần ở Terminal 2 để dừng teleop.
2. Nhấn `Ctrl+C` một lần ở Terminal 1 để dừng SLAM và Gazebo.
3. Chờ các node dừng hoàn toàn trước khi mở Navigation.

### Nếu map không xuất hiện hoặc lưu map bị timeout

Trong Terminal 3 đã source ROS và workspace, chạy:

```bash
ros2 node list
ros2 topic info /map
```

Phải có node `/slam_toolbox` và `/map` có ít nhất một publisher.
Ba dòng `PASS` cho `/scan`, `/odom`, `/cmd_vel` chỉ kiểm tra sensor/kết nối,
không chứng minh SLAM đã tạo map.

Nếu không có `/slam_toolbox` hoặc `Publisher count: 0`, kiểm tra Terminal 1
đang chạy **mapping.launch.py** và không có lỗi khởi động SLAM.
Nếu có publisher nhưng RViz vẫn trống, kiểm tra **Map → Status**,
Topic `/map`, Fixed Frame `map`, và trạng thái Play của Gazebo.

Các dòng `oakd/start_camera`, `oakd/stop_camera`, `start_motor`,
`stop_motor unavailable` có thể bỏ qua trong simulation nếu robot,
`/scan` và `/odom` vẫn hoạt động. Đây là service điều khiển camera và LiDAR.

## Phần 2 — Navigation: dùng bản đồ đã lưu

Chỉ bắt đầu khi Phần 1 đã lưu thành công `small_room.yaml` và `small_room.pgm`,
và launch SLAM đã dừng. Navigation không tiếp tục quét bản đồ;
nó dùng map đã lưu để định vị và lập đường.

### Terminal 1: mở Gazebo, map đã lưu, AMCL và Nav2

Khối lệnh dưới build lại package để cập nhật map/config, rồi load trực tiếp
map trong thư mục source bằng đường dẫn tuyệt đối:

```bash
cd ~/ur_robot_drawing
source /opt/ros/humble/setup.bash
colcon build --packages-select turtlebot_simu --symlink-install
source install/setup.bash
export ROS_LOCALHOST_ONLY=1

ros2 launch turtlebot_simu navigation.launch.py \
  world:=small_room \
  map:="$PWD/turtlebot_simu/maps/small_room.yaml"
```

Dùng đúng world đã quét ở Phần 1. Launch sẽ từ chối map mẫu hoặc thiếu file ảnh.
Navigation mặc định tìm `maps/small_room.yaml`; phải lưu map thật trước.
Nếu dùng lại `world:=maze`, truyền `map:=...` trỏ tới map đã quét của maze.
Giữ terminal này chạy trong suốt quá trình navigation.

Launch mới chờ localization sẵn sàng rồi mới khởi động Nav2. Mặc định nó
gửi initial pose `(0, 0, 0)` một lần trong frame `map`, phù hợp khi map được
quét từ vị trí xuất phát này. Chờ dòng `Localization ready` trước khi gửi goal.
Tọa độ spawn trong Gazebo (`x`, `y`, `yaw`) và pose trong map có thể khác nhau.
Với map có gốc/hướng khác, truyền `initial_x:=... initial_y:=... initial_yaw:=...`
hoặc dùng `auto_initial_pose:=false` và đặt **2D Pose Estimate** trong RViz.
Trong chế độ thủ công, Navigation chưa active trước khi đặt pose là bình thường;
Localization vẫn active và RViz vẫn mở để bạn đặt pose. Sau 180 giây chưa có
pose/TF hợp lệ, launch dừng với thông báo nguyên nhân thay vì khởi động Nav2
trong trạng thái thiếu TF. Có thể tăng bằng `localization_timeout:=300`.

Navigation dùng Cyclone DDS và `config/cyclonedds.xml` cho discovery trên
localhost. Cài một lần bằng `sudo apt install ros-humble-rmw-cyclonedds-cpp`.
Trong các terminal gửi action/goal hoặc kiểm tra topic, dùng cùng middleware:

```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI="file://$PWD/turtlebot_simu/config/cyclonedds.xml"
```

Controller dùng DWB chuẩn TurtleBot 4 với số mẫu giảm xuống 8 × 12 để giới
hạn tải tính toán, chạy trong container với executor riêng cho từng component.
Local costmap và global plan dùng cùng frame `map`. Timeout xác nhận action
của Behavior Tree là 2000 ms, thay cho 20 ms quá ngắn khi máy bận.

Navigation mặc định chạy Gazebo ở chế độ `headless:=true`: không có cửa sổ
Gazebo, nhưng mô phỏng vẫn tự chạy và RViz vẫn hiển thị map/scan. Chế độ này
tránh Gazebo GUI và RViz tranh GPU, đặc biệt trên máy không dùng được NVIDIA
driver. Chỉ khi thật sự cần xem cửa sổ Gazebo mới chạy thêm `headless:=false`.
Navigation mặc định dùng `model:=lite` để giảm tải camera; có thể chọn lại
`model:=standard` nếu cần. Mapping và simulation vẫn giữ model mặc định cũ.

RViz dùng cấu hình nhẹ `config/navigation.rviz`, giới hạn 10 FPS và chỉ bật
Map, LaserScan, AMCL particles và global path. Global/Local Costmap và TF vẫn
có trong danh sách nhưng mặc định tắt; chỉ bật tạm từng display khi cần debug.
Giữ **Fixed Frame = `map`** và Map topic `/map`.

### Terminal 2: undock

```bash
cd ~/ur_robot_drawing
source /opt/ros/humble/setup.bash
source install/setup.bash
export ROS_LOCALHOST_ONLY=1
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI="file://$PWD/turtlebot_simu/config/cyclonedds.xml"

ros2 action send_goal /undock irobot_create_msgs/action/Undock '{}'
```

Chờ kết quả `SUCCEEDED`.

### Trên RViz: định vị và gửi goal

1. Với `auto_initial_pose:=false`, chọn **2D Pose Estimate**. Ở chế độ tự động,
   chỉ đặt lại pose nếu scan không khớp map.
2. Khi đặt lại pose, nhấp vào vị trí hiện tại của robot trên bản đồ và kéo
   mũi tên đúng hướng.
3. Chờ particle cloud hội tụ, LaserScan trùng với tường và hai trạng thái
   **Navigation**, **Localization** trong panel Navigation 2 đều là `active`.
4. Chọn **Nav2 Goal**, nhấp vào vùng trắng và kéo mũi tên theo hướng muốn tới.
5. Chờ robot đến đích rồi đặt goal tiếp theo ở vị trí khác.

Thực hiện ít nhất 3 goal ở các khu vực khác nhau. Goal phải cách tường đủ xa.
Không chạy teleop trong khi Nav2 đang điều khiển robot.

### Tùy chọn: chạy 3 goal tự động

Sửa `turtlebot_simu/config/waypoints_small_room.yaml` thành ít nhất 3 vị trí an toàn
trên map của bạn. Các tọa độ có sẵn chỉ là ví dụ; `x`, `y` tính bằng mét,
`yaw` bằng radian trong frame `map`.

Sau khi undock và đặt **2D Pose Estimate**, chạy ở Terminal 2:

```bash
cd ~/ur_robot_drawing
source /opt/ros/humble/setup.bash
source install/setup.bash
export ROS_LOCALHOST_ONLY=1

ros2 run turtlebot_simu waypoint_nav \
  --goals-file "$PWD/turtlebot_simu/config/waypoints_small_room.yaml" \
  --ready-timeout 120 \
  --goal-timeout 180
```

Node chờ AMCL/Nav2 sẵn sàng, kiểm tra goal có nằm trong vùng trống và cách
vật cản ít nhất `0.25 m`, rồi gửi lần lượt các goal. Sau mỗi kết quả thành công,
node kiểm tra pose AMCL để xác nhận robot đã đến đích.

File mẫu của phòng nhỏ dùng ba điểm `(-2, -2)`, `(2, 1.5)`, `(-2, 2.3)`.
Đây là tọa độ tham khảo trong world, không phải kết quả navigation đã kiểm chứng;
đối chiếu với frame `map` sau SLAM và sửa nếu cần. Node `waypoint_nav` chạy
không có `--goals-file` vẫn dùng file mẫu cũ `config/waypoints.yaml`.

### Nếu Nav2 không nhận goal

Kiểm tra đã undock, đã đặt initial pose và các node đều ở trạng thái `active`:

```bash
ros2 lifecycle get /amcl
ros2 lifecycle get /planner_server
ros2 lifecycle get /controller_server
ros2 lifecycle get /bt_navigator
```

Nếu LaserScan lệch với tường, đặt lại **2D Pose Estimate** và kiểm tra đang
dùng đúng world/map. Chỉ gửi goal khi localization đã khớp.

Nếu log lặp `Control loop missed its desired rate` hoặc `Failed to make
progress` trong khi robot vẫn nhích, cần build lại để nhận profile mô phỏng
nhẹ trong `config/nav2.yaml`. Profile chạy controller ở 5 Hz và cho phép 60
giây để robot dịch chuyển 5 cm hoặc quay 0.1 radian. `PoseProgressChecker`
tính cả việc quay hướng vào đường đi sau undock, tránh recovery nhầm.
Nếu `/hazard_detection` có phần tử hoặc `/stop_status` báo
`is_stopped: true`, xử lý trạng thái an toàn đó trước khi gửi goal mới.

### Kết thúc Navigation

Nhấn `Ctrl+C` một lần ở terminal waypoint (nếu đang chạy), sau đó ở Terminal 1.
Chờ Gazebo và các node dừng hoàn toàn.



## Tài liệu tham khảo

- [TurtleBot 4 Simulator](https://turtlebot.github.io/turtlebot4-user-manual/software/turtlebot4_simulator.html)
- [TurtleBot 4 Navigation](https://turtlebot.github.io/turtlebot4-user-manual/tutorials/navigation.html)
- [Navigation2](https://docs.nav2.org/)
