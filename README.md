# Bài 5 — TurtleBot 4 Navigation + YOLO

Package ROS 2: `ttbot4_nav_detect`

Package này chạy chung trong **một launch**:

- Gazebo với world `small_room`;
- map, AMCL và Nav2;
- tự undock và chạy ba waypoint;
- camera OAK-D mô phỏng;
- YOLO và ảnh có bounding box ngay trong RViz.

> **Quan trọng:** `turtlebot_simu` là package bài Navigation, không có YOLO.
> Nếu tiêu đề RViz chứa `install/turtlebot_simu/.../navigation.rviz` thì bạn
> đang chạy nhầm package. Tiêu đề đúng phải chứa
> `install/ttbot4_nav_detect/.../navigation.rviz`.

## 1. Cài đặt lần đầu — copy toàn bộ khối này

Yêu cầu Ubuntu 22.04, ROS 2 Humble và Conda environment `hri` đã được tạo.

```bash
cd ~/ur_robot_drawing

source ~/miniconda3/etc/profile.d/conda.sh
conda activate hri
source /opt/ros/humble/setup.bash

sudo apt update
sudo apt install -y \
  ros-humble-turtlebot4-simulator \
  ros-humble-turtlebot4-navigation \
  ros-humble-nav2-simple-commander \
  ros-humble-cv-bridge \
  ros-humble-rmw-cyclonedds-cpp \
  python3-opencv

python -m pip install -r 'ttbot4_nav+detect/requirements.txt'
rosdep install --ignore-src --from-paths 'ttbot4_nav+detect' -r -y

colcon build --packages-select ttbot4_nav_detect --symlink-install
```

Không dùng `pip install --user` trong Conda. ROS 2 Humble `cv_bridge` cần
`numpy<2`; giới hạn này đã có trong `requirements.txt`.

## 2. Chạy toàn bộ bài — copy toàn bộ khối này

Trước tiên, nhấn `Ctrl+C` ở các terminal Gazebo, Nav2 hoặc RViz cũ. Chỉ để một
simulation chạy tại một thời điểm. Sau đó mở terminal mới và chạy:

```bash
cd ~/ur_robot_drawing

source ~/miniconda3/etc/profile.d/conda.sh
conda activate hri
source /opt/ros/humble/setup.bash

colcon build --packages-select ttbot4_nav_detect --symlink-install
source install/setup.bash
export ROS_LOCALHOST_ONLY=1

test -f "$PWD/yolov8n.pt" || {
  echo "THIEU MODEL: $PWD/yolov8n.pt"
  exit 1
}

ros2 launch ttbot4_nav_detect coursework.launch.py \
  rviz:=true \
  headless:=true \
  detect:=true \
  run_mission:=true \
  yolo_model:="$PWD/yolov8n.pt" \
  inference_hz:=2.0
```

Không chạy thêm `turtlebot_simu navigation.launch.py`, `waypoint_nav` hoặc
RQt trong lúc launch trên đang chạy. `coursework.launch.py` đã chạy toàn bộ
navigation, waypoint và YOLO.

## 3. Phải thấy gì trong RViz?

Sau khi launch hoàn tất:

1. Thanh tiêu đề RViz chứa `install/ttbot4_nav_detect/.../navigation.rviz`.
2. Cột **Displays** có mục **YOLO Camera** và ô Enabled được bật.
3. **YOLO Camera** dùng topic `/yolo/annotated_image`.
4. Map, LaserScan, AMCL và Global Path vẫn hiển thị như bình thường.
5. Terminal có dòng `YOLO ready` và các kết quả nhận diện nếu có vật thuộc
   lớp mà model nhận ra.

Camera mô phỏng nhìn theo hướng trước của robot. Nếu ảnh không có bounding box
thì có thể camera vẫn hoạt động nhưng trong khung hình chưa có vật mà model
COCO nhận diện được.

## 4. Kiểm tra ảnh — mở Terminal 2 và copy khối này

Giữ launch ở Terminal 1 đang chạy. Mở Terminal 2:

```bash
cd ~/ur_robot_drawing

source ~/miniconda3/etc/profile.d/conda.sh
conda activate hri
source /opt/ros/humble/setup.bash
source install/setup.bash
export ROS_LOCALHOST_ONLY=1

echo '=== NODE YOLO ==='
ros2 node list | grep object_detector

echo '=== CAMERA GOC ==='
timeout 8 ros2 topic hz /oakd/rgb/preview/image_raw

echo '=== ANH YOLO ==='
timeout 8 ros2 topic hz /yolo/annotated_image

echo '=== THONG TIN TOPIC YOLO ==='
ros2 topic info /yolo/annotated_image
```

Kết quả đúng:

- có node `/object_detector`;
- camera gốc khoảng 20–30 Hz;
- ảnh YOLO gần mức `inference_hz` đã chọn, ví dụ khoảng 2 Hz;
- `/yolo/annotated_image` có ít nhất một publisher và RViz tạo subscriber.

Xem JSON nhận diện:

```bash
ros2 topic echo /yolo/detections
```

## 5. Nếu RViz vẫn không có ảnh

| Hiện tượng | Nguyên nhân và cách xử lý |
|---|---|
| Tiêu đề chứa `install/turtlebot_simu` | Đang chạy nhầm package. Dừng launch đó và chạy đúng khối ở mục 2. |
| Không có mục **YOLO Camera** | Build/source chưa cập nhật. Chạy lại đầy đủ mục 2. |
| Có YOLO Camera nhưng màu xám | Mở mục đó, kiểm tra Topic là `/yolo/annotated_image` và Enabled đang bật. |
| Không có `/object_detector` | Xem lỗi trong Terminal 1; thường do chưa `conda activate hri` hoặc thiếu model. |
| Camera gốc có Hz nhưng ảnh YOLO không có Hz | YOLO bị lỗi thư viện/model; kiểm tra dòng `object_detector` trong Terminal 1. |
| Cả hai topic đều không có Hz | Gazebo/camera bridge chưa chạy hoặc đang có simulation cũ xung đột. |

Không cần dùng `rqt_image_view`. Cấu hình RViz đã subscribe trực tiếp ảnh YOLO.

## 6. Chạy không tự đi waypoint

Để robot đứng yên khi kiểm tra camera và YOLO:

```bash
cd ~/ur_robot_drawing
source ~/miniconda3/etc/profile.d/conda.sh
conda activate hri
source /opt/ros/humble/setup.bash
source install/setup.bash
export ROS_LOCALHOST_ONLY=1

ros2 launch ttbot4_nav_detect coursework.launch.py \
  rviz:=true \
  headless:=true \
  detect:=true \
  run_mission:=false \
  yolo_model:="$PWD/yolov8n.pt" \
  inference_hz:=2.0
```

Muốn mở cả giao diện Gazebo, đổi `headless:=true` thành `headless:=false`.
Việc mở đồng thời Gazebo GUI và RViz sẽ dùng GPU nhiều hơn.

## 7. Waypoint đang dùng

File `config/waypoints_small_room.yaml`:

| Goal | x (m) | y (m) | yaw (rad) |
|---|---:|---:|---:|
| 1 | -1.8 | -1.5 | 1.57 |
| 2 | -1.8 | -0.2 | -0.38 |
| 3 | -0.8 | -0.6 | 0.0 |

Tuyến ngắn nằm trong vùng trống phía tây nam của map đi kèm, tránh vách ngăn,
khối hộp, trụ và dock. Phải kiểm tra lại tọa độ khi thay map hoặc initial pose.
Nếu LaserScan lệch rõ khỏi tường trên map, dừng mission và kiểm tra localization;
đổi waypoint không khắc phục được lỗi định vị.

## 8. Topic chính

| Topic | Nội dung |
|---|---|
| `/oakd/rgb/preview/image_raw` | Ảnh RGB gốc từ camera mô phỏng |
| `/yolo/annotated_image` | Ảnh đã vẽ bounding box để RViz hiển thị |
| `/yolo/detections` | Kết quả nhận diện dạng JSON |
| `/scan` | LiDAR |
| `/map` | Occupancy map |
| `/amcl_pose` | Pose robot do AMCL ước lượng |

## 9. File chính

- `launch/coursework.launch.py`: chạy simulation, localization, Nav2, mission,
  YOLO và RViz.
- `config/navigation.rviz`: có sẵn display **YOLO Camera**.
- `ttbot4_nav_detect/object_detector.py`: nhận ảnh, chạy YOLO và publish kết quả.
- `ttbot4_nav_detect/navigation_ready.py`: chờ map, scan, AMCL và TF hợp lệ.
- `ttbot4_nav_detect/waypoint_mission.py`: undock và chạy ba goal.
