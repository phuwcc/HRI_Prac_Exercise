# Bài 5 — TurtleBot 4 Navigation + YOLO

Package ROS 2: `ttbot4_nav_detect`  
Môi trường: Ubuntu 22.04, ROS 2 Humble, TurtleBot 4 Simulation.

Package thực hiện đầy đủ bốn phần của đề:

- Mở `small_room.sdf`, nạp `maps/small_room.yaml`, chạy AMCL và Nav2.
- Tự đặt initial pose mặc định `(0, 0, 0)` trong frame `map`.
- Tự undock và đi tuần tự qua ba tọa độ trong
  `config/waypoints_small_room.yaml` bằng `nav2_simple_commander`.
- Subscribe camera RGB, chạy Ultralytics YOLO, in kết quả ra terminal,
  publish ảnh có bounding box lên `/yolo/annotated_image`, và publish JSON
  nhận diện lên `/yolo/detections`.

## 1. Cài dependency

```bash
sudo apt update
sudo apt install \
  ros-humble-turtlebot4-simulator \
  ros-humble-turtlebot4-navigation \
  ros-humble-nav2-simple-commander \
  ros-humble-cv-bridge \
  ros-humble-rmw-cyclonedds-cpp \
  python3-opencv

python3 -m pip install --user -r 'ttbot4_nav+detect/requirements.txt'
```

ROS 2 Humble `cv_bridge` trên Ubuntu 22.04 thường được biên dịch với NumPy 1.x.
Nếu terminal báo `_ARRAY_API not found`, cần dùng `numpy<2` như lệnh trên.

Model mặc định là `yolov8n.pt`. Ultralytics sẽ tải weight ở lần chạy đầu nếu
file chưa có. Có thể tải trước và truyền đường dẫn local bằng `yolo_model:=...`.

## 2. Build

```bash
cd ~/ur_robot_drawing
source /opt/ros/humble/setup.bash
rosdep install --ignore-src --from-paths 'ttbot4_nav+detect' -r -y
colcon build --packages-select ttbot4_nav_detect --symlink-install
source install/setup.bash
```

## 3. Chạy toàn bộ bài bằng một lệnh

Tắt các tiến trình Gazebo/Nav2 cũ trước khi chạy:

```bash
cd ~/ur_robot_drawing
source /opt/ros/humble/setup.bash
source install/setup.bash

ros2 launch ttbot4_nav_detect coursework.launch.py
```

Mặc định launch sẽ:

1. Chạy Gazebo headless với TurtleBot 4 Standard trong `small_room`.
2. Nạp map, chạy AMCL và gửi initial pose `(0, 0, 0)`.
3. Chỉ khởi động Nav2 sau khi map, scan, AMCL và TF đã hợp lệ.
4. Chạy YOLO trên `/oakd/rgb/preview/image_raw`.
5. Tự undock và lần lượt đi Goal 1 → Goal 2 → Goal 3.

Muốn xem cả cửa sổ Gazebo:

```bash
ros2 launch ttbot4_nav_detect coursework.launch.py headless:=false
```

Chỉ kiểm tra localization/Nav2, chưa tự chạy waypoint và chưa chạy YOLO:

```bash
ros2 launch ttbot4_nav_detect coursework.launch.py \
  run_mission:=false detect:=false
```

Nếu initial pose của map khác vị trí xuất phát mặc định:

```bash
ros2 launch ttbot4_nav_detect coursework.launch.py \
  initial_x:=0.5 initial_y:=-0.2 initial_yaw:=1.57
```

Hoặc đặt thủ công bằng **2D Pose Estimate** trong RViz:

```bash
ros2 launch ttbot4_nav_detect coursework.launch.py \
  auto_initial_pose:=false run_mission:=false
```

## 4. Tọa độ mục tiêu

Ba điểm hiện tại trong `config/waypoints_small_room.yaml`:

| Goal | x (m) | y (m) | yaw (rad) |
|---|---:|---:|---:|
| 1 | -2.0 | -2.0 | 0.0 |
| 2 | 2.0 | 1.5 | 1.57 |
| 3 | -2.0 | 2.3 | 3.14 |

Các điểm này nằm trong vùng trống của map `small_room` đi kèm. Nếu quét lại
map hoặc đổi world, lấy tọa độ mới bằng RViz rồi sửa YAML:

```bash
ros2 topic echo /clicked_point
ros2 topic echo /amcl_pose
```

Node waypoint kiểm tra từng goal với occupancy grid trước khi chạy và từ chối
goal ngoài map, trong vùng unknown, hoặc quá gần vật cản.

## 5. Kiểm tra camera và YOLO

```bash
ros2 topic hz /oakd/rgb/preview/image_raw
ros2 topic echo /yolo/detections
ros2 topic hz /yolo/annotated_image
```

Trong RViz, thêm display **Image** và chọn `/yolo/annotated_image` để xem ảnh
có bounding box. Cách này nhẹ và ổn định hơn cửa sổ OpenCV. Nếu muốn bật cửa
sổ OpenCV:

```bash
ros2 launch ttbot4_nav_detect coursework.launch.py \
  headless:=false show_window:=true
```

Đổi model, ngưỡng và tốc độ suy luận:

```bash
ros2 launch ttbot4_nav_detect coursework.launch.py \
  yolo_model:=yolo11n.pt confidence:=0.50 inference_hz:=3.0
```

Nếu topic RGB thực tế khác tên, xem danh sách rồi truyền lại:

```bash
ros2 topic list | grep -E 'image_raw|rgb'
ros2 launch ttbot4_nav_detect coursework.launch.py \
  image_topic:=/ten/topic/camera/thuc/te
```

## 6. Các file chính

- `launch/coursework.launch.py`: launch toàn bộ hệ thống.
- `ttbot4_nav_detect/navigation_ready.py`: kiểm tra map/scan/AMCL/TF và initial pose.
- `ttbot4_nav_detect/waypoint_mission.py`: undock và chạy ba goal bằng code.
- `ttbot4_nav_detect/object_detector.py`: `Image` → `cv_bridge` → YOLO → ảnh/JSON.
- `config/waypoints_small_room.yaml`: các tọa độ `(x, y, yaw)`.
- `maps/small_room.yaml`, `maps/small_room.pgm`: map đã quét.
