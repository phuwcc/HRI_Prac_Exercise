# Bài 8 — Nhận diện biểu cảm khuôn mặt và điều khiển TurtleBot

Package ROS 2 Python: webcam → DeepFace/OpenCV → lọc biểu cảm → `geometry_msgs/msg/Twist` trên `/cmd_vel` (20 Hz). Chạy nhận diện trên máy có webcam, cùng ROS_DOMAIN_ID và mạng ROS 2 với TurtleBot. Package không khởi động robot hoặc simulator.

| Biểu cảm | Hành động | Mặc định |
|---|---|---|
| Happy | Cong trái | v=0.08 m/s, ω=+0.4 rad/s, 3 s |
| Sad | Cong phải | v=0.08 m/s, ω=−0.4 rad/s, 3 s |
| Neutral | Dừng | v=ω=0 ngay khi kết quả hợp lệ |
| Angry | Lùi nhẹ | v=−0.08 m/s, 1 s |
| Surprise | Xoay một vòng tại chỗ | ω=+0.4 rad/s, khoảng 15.71 s |
| Fear | Tiến nhẹ | v=+0.08 m/s, 1 s |

Góc xoay tính bằng thời gian `2π / angular_speed`, là một vòng danh định, chưa hiệu chỉnh bằng odometry; robot thực có thể lệch do trượt bánh/độ trễ. Các quỹ đạo là điều khiển vận tốc, không có tránh vật cản.

## Cài đặt (Ubuntu 22.04, ROS 2 Humble)

Dùng Python hệ thống tương thích với bản ROS, không dùng Python khác phiên bản để import `rclpy`.

```bash
source /opt/ros/humble/setup.bash
sudo apt install python3-venv python3-colcon-common-extensions python3-pytest ros-humble-geometry-msgs
mkdir -p ~/face_emote_ws/src
# Clone duy nhất branch bài 8, không cần clone submodule:
git clone --single-branch --branch ttbot4_face_emote \
  https://github.com/phuwcc/ur_robot_drawing.git ~/face_emote_ws/src/ur_robot_drawing
cd ~/face_emote_ws
/usr/bin/python3 -m venv --system-site-packages .venv
source .venv/bin/activate
touch .venv/COLCON_IGNORE
python -m pip install -r src/ur_robot_drawing/ttbot4_face_emote/requirements.txt
python -m colcon build --symlink-install --packages-select ttbot4_face_emote
source install/setup.bash
ros2 launch ttbot4_face_emote face_emote.launch.py
```

DeepFace tải trọng số vào cache ngoài repo trong lần chạy đầu, cần Internet. Node giữ vận tốc 0 trong khi tải/khởi tạo. `requirements.txt` giới hạn dòng API, không phải lockfile toàn bộ dependency. Nếu dùng DeepFace bản TensorFlow cũ và gặp lỗi Keras, cài `tf-keras` có phiên bản tương thích với TensorFlow đang dùng trong venv.

Trong terminal mới, source ROS, kích hoạt cùng venv và source workspace như trên. Kiểm tra robot đã bringup và topic nhận đúng kiểu `Twist`:

```bash
ros2 topic info /cmd_vel -v
ros2 topic echo /cmd_vel
```

Nếu bringup dùng topic vận tốc khác, đổi topic khi launch:

```bash
ros2 launch ttbot4_face_emote face_emote.launch.py cmd_vel_topic:=/robot/cmd_vel
```

Node xuất `Twist`, không phải `TwistStamped`; bringup yêu cầu `TwistStamped` cần bộ chuyển đổi phù hợp. Dừng các node teleop/navigation cùng xuất vận tốc trước khi chạy bài này.

## Cách sử dụng

Đặt một khuôn mặt trước webcam. Cửa sổ hiển thị khung mặt, tên biểu cảm, điểm số mô hình và vận tốc đang gửi. Điểm số mô hình không phải độ chính xác đã được hiệu chuẩn.

Mặc định cần 3 kết quả liên tiếp có điểm số ≥50% để bắt đầu chuyển động. Mỗi biểu cảm chỉ kích hoạt một hành động; giữ nguyên biểu cảm không lặp vô hạn. Chuyển về Neutral để kích hoạt lại cùng hành động hoặc đổi sang biểu cảm khác. Khi đổi biểu cảm, robot dừng trong thời gian chờ đủ mẫu mới.

Mất mặt, nhiều mặt, `disgust` (ngoài 6 trạng thái đề bài), điểm thấp hoặc lỗi camera làm robot dừng khi nhận kết quả đó. Nếu inference bị chậm/treo, timer dừng sau tối đa `timeout` kể từ thời điểm chụp mẫu hợp lệ cuối. Không tự tiếp tục hành động đã bị timeout khi giữ cùng biểu cảm. Nhấn **Q**, **Esc** ở cửa sổ hoặc **Ctrl+C** trong terminal để thoát và gửi lệnh dừng. Mất nguồn/kill cưỡng bức không thể gửi lệnh cuối; bộ điều khiển robot cần có watchdog vận tốc.

## Tham số

Chỉnh `config/emotions.yaml` trước khi build hoặc truyền một file riêng:

```bash
ros2 launch ttbot4_face_emote face_emote.launch.py params_file:=/absolute/path/emotions.yaml
# Chạy không mở cửa sổ (vẫn dùng webcam):
ros2 run ttbot4_face_emote face_emote --ros-args -p show_camera:=false -p camera_index:=0
```

`linear_speed` tối đa 0.2 m/s, `angular_speed` tối đa 1 rad/s; cả hai phải dương. `arc_duration`, `step_duration` giới hạn thời gian hành động. `stable_samples` đếm kết quả inference, không đếm tick ROS. `inference_period` là thời gian nghỉ giữa hai lần inference, không bảo đảm FPS. `timeout` tính theo đồng hồ monotonic, không phụ thuộc `/clock`; tăng thận trọng nếu CPU xử lý chậm. Tham số đọc khi khởi động; sửa cấu hình rồi khởi động lại node.

## Kiểm thử

```bash
cd ~/face_emote_ws/src/ur_robot_drawing/ttbot4_face_emote
python -m pytest -q
```

Để chạy thêm kiểm thử topic với ROS 2 thật và camera/model giả lập:

```bash
source /opt/ros/humble/setup.bash
FACE_EMOTE_ROS_TEST=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q
```

Nếu pytest bị lỗi do plugin cài sẵn không tương thích, dùng `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` như trên. Đã kiểm tra trên máy phát triển: 22 test đạt (gồm truyền `/cmd_vel` và dừng khi mất mặt), `colcon build` thành công, executable và launch arguments được ROS 2 nhận diện. Chưa chạy DeepFace/webcam/robot thật.

Các unit test không cần ROS, webcam hoặc tải model: kiểm tra đủ sáu hành động, lọc ổn định, điểm thấp, mất mặt, timeout, không lặp, Neutral, một vòng danh định và dữ liệu DeepFace. Để kiểm tra tích hợp, bringup TurtleBot/simulator riêng, quan sát `/cmd_vel`, thử đủ sáu biểu cảm và che/rút camera. Chỉ thử robot thật trong vùng trống với nút dừng sẵn sàng. Chưa thể kết luận độ chính xác nhận diện hay quỹ đạo thực chỉ từ unit test.

API tham khảo: [DeepFace](https://github.com/serengil/deepface), [ROS 2 rclpy](https://github.com/ros2/rclpy).
