# Bài 8 — Biểu cảm khuôn mặt điều khiển TurtleBot trong sim

Chạy **TurtleBot 4 Lite trong Gazebo Fortress, ROS 2 Humble**. Webcam máy tính nhận diện biểu cảm người dùng; robot di chuyển trong world `emotion_arena` của package. Một lệnh launch mở cả Gazebo, tạo robot, kích hoạt bộ điều khiển bánh xe và chạy DeepFace/OpenCV. Không cần robot thật hoặc submodule.

Luồng điều khiển: webcam → DeepFace → lọc biểu cảm → `/cmd_vel` (`Twist`, 20 Hz) → `sim_velocity_relay` → `/diffdrive_controller/cmd_vel_unstamped` → bánh xe trong Gazebo. `/odom` phản ánh chuyển động mô phỏng, `/clock` lấy từ Gazebo.

| Biểu cảm | Hành động | Mặc định |
|---|---|---|
| Happy | Cong trái | v=0.08 m/s, ω=+0.4 rad/s, 3 s |
| Sad | Cong phải | v=0.08 m/s, ω=−0.4 rad/s, 3 s |
| Neutral | Dừng | v=ω=0 ngay khi kết quả hợp lệ |
| Angry | Lùi nhẹ | v=−0.08 m/s, 1 s |
| Surprise | Xoay một vòng tại chỗ | ω=+0.4 rad/s, khoảng 15.71 s |
| Fear | Tiến nhẹ | v=+0.08 m/s, 1 s |

Góc xoay tính theo thời gian `2π / angular_speed`, là một vòng danh định, chưa đóng vòng bằng odometry. Bản này dùng thời gian thực cho webcam, timeout và thời lượng hành động: giữ sim chạy, không Pause khi đang thực hiện. Nếu máy chạy sim chậm hơn thời gian thực, góc/quãng đường sẽ ngắn hơn giá trị danh định. World có sàn trống 20×20 m, vòng xanh đánh dấu vị trí xuất phát.

## Cài đặt

Ubuntu 22.04 + ROS 2 Humble + Gazebo Fortress (không dùng launch Jazzy/Harmonic).

```bash
source /opt/ros/humble/setup.bash
sudo apt install python3-venv python3-colcon-common-extensions python3-pytest \
  ros-humble-turtlebot4-simulator ros-humble-ros-gz-sim ros-humble-ros-gz-bridge \
  ros-humble-ign-ros2-control ros-humble-ros2-controllers
mkdir -p ~/face_emote_ws/src
git clone --single-branch --branch ttbot4_face_emote \
  https://github.com/phuwcc/HRI_Prac_Exercise.git ~/face_emote_ws/src/ur_robot_drawing
cd ~/face_emote_ws
/usr/bin/python3 -m venv --system-site-packages .venv
source .venv/bin/activate
touch .venv/COLCON_IGNORE
python -m pip install -r src/ur_robot_drawing/ttbot4_face_emote/requirements.txt
python -m colcon build --symlink-install --packages-select ttbot4_face_emote
source install/setup.bash
ros2 launch ttbot4_face_emote face_emote.launch.py
```

Dùng Python hệ thống tương thích ROS, không dùng Python khác phiên bản để import `rclpy`. DeepFace tải trọng số vào cache ngoài repo trong lần đầu, cần Internet; vận tốc giữ 0 khi đang tải. `requirements.txt` giới hạn dòng API, không khóa toàn bộ dependency. DeepFace bản TensorFlow cũ có thể cần `tf-keras` tương thích phiên bản TensorFlow trong venv.

Nếu clone đã có, chỉ cần `git pull` trên branch bài 8 rồi build lại. Repo chỉ chứa thư mục `ttbot4_face_emote`, không cần `git submodule update`.

## Chạy bài

Trong terminal mới: source ROS, kích hoạt cùng venv và source workspace. Lệnh mặc định mở cửa sổ Gazebo và cửa sổ webcam:

```bash
ros2 launch ttbot4_face_emote face_emote.launch.py
# Chọn webcam khác:
ros2 launch ttbot4_face_emote face_emote.launch.py camera_index:=1
# Không mở GUI Gazebo (vẫn mở cửa sổ webcam):
ros2 launch ttbot4_face_emote face_emote.launch.py headless:=true
```

Chờ robot xuất hiện trên sàn và controller được kích hoạt; giữ Neutral rồi thử từng biểu cảm trong bảng. Cửa sổ webcam hiển thị khung mặt, tên biểu cảm, điểm số và vận tốc. Điểm số mô hình không phải độ chính xác đã được hiệu chuẩn. Nhấn **Q/Esc** để dừng nhận diện (relay tự dừng robot); **Ctrl+C** ở terminal launch để đóng toàn bộ sim.

Mặc định cần 3 kết quả liên tiếp có điểm số ≥50% để bắt đầu. Mỗi biểu cảm chỉ kích hoạt một hành động, giữ nguyên không lặp vô hạn. Về Neutral để kích hoạt lại cùng hành động hoặc đổi sang biểu cảm khác. Khi đổi biểu cảm, robot dừng trong thời gian chờ đủ mẫu mới.

Mất mặt, nhiều mặt, `disgust` (ngoài 6 trạng thái đề bài), điểm thấp hoặc lỗi camera làm robot dừng khi nhận kết quả. Nếu inference treo/chậm, dừng sau `timeout` kể từ lúc chụp mẫu hợp lệ cuối; giữ cùng biểu cảm không tự tiếp tục hành động đã timeout. Relay dừng đầu ra nếu mất `/cmd_vel` trong 0.5 giây. Controller bánh xe cũng có timeout 0.5 giây.

Launch đặt `ROS_LOCALHOST_ONLY=1`. Dùng cùng giá trị trong terminal kiểm tra; nếu đang chạy bài ROS khác, chọn riêng `ROS_DOMAIN_ID` cho tất cả terminal của bài này để tránh trùng topic.

```bash
export ROS_LOCALHOST_ONLY=1
ros2 control list_controllers
ros2 topic echo /cmd_vel
# Terminal khác:
ros2 topic echo /odom
```

Hai controller `joint_state_broadcaster` và `diffdrive_controller` phải là `active`. Nếu Gazebo chưa hiện robot, xem log `create`/`spawner`; không chạy thêm một launch mô phỏng thứ hai cùng domain. Tài nguyên mesh lấy từ các package ROS cài sẵn, world không cần tải model Fuel. Bài tập tập trung chuyển động bánh xe: không bật navigation hay bridge lidar/camera ảo; nguồn ảnh nhận diện vẫn là webcam người dùng.

## Tham số

Chỉnh `config/emotions.yaml` trước khi build hoặc truyền file riêng:

```bash
ros2 launch ttbot4_face_emote face_emote.launch.py \
  params_file:=/absolute/path/emotions.yaml show_camera:=false
```

`linear_speed` dương, tối đa 0.2 m/s; `angular_speed` dương, tối đa 1 rad/s. `arc_duration` và `step_duration` giới hạn thời gian chuyển động. `stable_samples` đếm kết quả inference. `inference_period` là thời gian nghỉ giữa hai lần inference, không bảo đảm FPS. `timeout` dùng đồng hồ monotonic, không phụ thuộc `/clock`. Tham số đọc lúc khởi động; sửa cấu hình rồi khởi động lại. Topic bài này cố định `/cmd_vel` trong launch để khớp với relay mô phỏng.

## Kiểm thử

Unit test và kiểm thử topic ROS 2 dùng camera/model giả lập, không cần tải model:

```bash
cd ~/face_emote_ws/src/ur_robot_drawing/ttbot4_face_emote
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
# Thêm kiểm thử ROS 2 sau khi source ROS:
FACE_EMOTE_ROS_TEST=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
```

Kiểm tra chuyển động mô phỏng qua đủ sáu trạng thái mà không cần DeepFace/webcam:

```bash
# Terminal 1: source ROS + workspace, cùng ROS_DOMAIN_ID
ros2 launch ttbot4_face_emote face_emote.launch.py headless:=true recognition:=false
# Terminal 2: source ROS + workspace, cùng ROS_DOMAIN_ID
export ROS_LOCALHOST_ONLY=1
python test/check_sim_motion.py
```

Script bơm sáu biểu cảm vào chính `Controller` rồi gửi `/cmd_vel`, kiểm tra dấu vận tốc đo từ `/odom`, sau đó kiểm tra robot dừng khi mất heartbeat. Đây là kiểm thử đường điều khiển và physics, không đo độ chính xác nhận diện khuôn mặt hay xác minh góc quay đủ 360°. Chế độ `recognition:=false` chỉ phục vụ kiểm tra sim; mặc định nhận diện webcam bật.

Đã kiểm tra trên máy phát triển: build package thành công; 22 unit/ROS test đạt; Gazebo Fortress headless tạo TurtleBot 4 Lite và kích hoạt hai controller; kiểm tra `/odom` đạt cho cả sáu hành động và watchdog. Nhận diện DeepFace/webcam và giao diện Gazebo chưa được kiểm tra trong lần xác minh này.

Tham khảo: [TurtleBot 4 Simulator (Humble)](https://github.com/turtlebot/turtlebot4_simulator/tree/humble), [DeepFace](https://github.com/serengil/deepface).
