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

## Chạy bài 8 bằng run.sh và Conda hri

Cần Ubuntu 22.04 + ROS 2 Humble + Gazebo Fortress và môi trường Conda `hri` có sẵn, dùng Python 3.10. Script tự kích hoạt `hri`, source ROS 2, kiểm tra thư viện, build bằng Python của `hri` rồi mở sim và webcam. Không cần tạo venv hoặc kích hoạt Conda thủ công.

Các gói ROS cài một lần nếu máy chưa có:

```bash
sudo apt install ros-humble-turtlebot4-simulator ros-humble-ros-gz-sim \
  ros-humble-ros-gz-bridge ros-humble-ign-ros2-control ros-humble-ros2-controllers
```

Clone branch bài 8 (các file package nằm ngay gốc repo):

```bash
git clone --single-branch --branch ttbot4_face_emote \
  https://github.com/phuwcc/HRI_Prac_Exercise.git
cd HRI_Prac_Exercise
# Lần đầu: bổ sung thư viện Python vào hri, build và chạy:
./run.sh --install-deps
# Các lần sau:
./run.sh
```

Trong workspace gốc đang phát triển nhiều bài, chạy từ thư mục bài 8:

```bash
cd /home/phuc/ur_robot_drawing/ttbot4_face_emote
./run.sh
```

Các tùy chọn:

```bash
./run.sh --help
./run.sh --check                       # Chỉ kiểm tra hri + thư viện
./run.sh --build-only                  # Build, chưa mở sim
./run.sh camera_index:=1               # Chọn webcam khác
./run.sh headless:=true                # Không mở GUI Gazebo, vẫn mở webcam
./run.sh show_camera:=false            # Nhận diện nhưng không mở cửa sổ webcam
./run.sh headless:=true recognition:=false  # Chỉ chạy sim để kiểm thử
```

Build/install/log được lưu trong `.run_ws/` cạnh script và bị Git bỏ qua. Script chỉ build package bài 8. `CONDA_SH` có thể chỉ tới `etc/profile.d/conda.sh` nếu Conda nằm ở vị trí khác; `CONDA_ENV_NAME` mặc định `hri`, `ROS_SETUP` mặc định `/opt/ros/humble/setup.bash`, `BAI8_WORKSPACE` đổi nơi lưu build.

DeepFace 0.0.105 chạy bằng ONNX Runtime, không cần TensorFlow. `run.sh --install-deps` cài `requirements.txt` trước, rồi cài `requirements-models.txt` với `--no-deps` để dùng OpenCV contrib có GUI thay cho bản headless được khai báo bởi DeepFace/RetinaFace. Đây là thay thế có chủ đích: `pip check` có thể báo thiếu bản headless dù `cv2` có đầy đủ chức năng bài này. Không cài thêm OpenCV headless đè lên bản GUI. NumPy được giới hạn `<2` để giữ tương thích môi trường HRI đang có. Script đặt `PYTHONNOUSERSITE=1` để tránh thư viện ở `~/.local` lấn vào `hri`.

Lần đầu model Emotion tải trọng số về cache ngoài repo, cần Internet. Robot đứng yên trong khi tải/khởi tạo. Không cần clone submodule.

## Sử dụng

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
./run.sh params_file:=/absolute/path/emotions.yaml show_camera:=false
```

`linear_speed` dương, tối đa 0.2 m/s; `angular_speed` dương, tối đa 1 rad/s. `arc_duration` và `step_duration` giới hạn thời gian chuyển động. `stable_samples` đếm kết quả inference. `inference_period` là thời gian nghỉ giữa hai lần inference, không bảo đảm FPS. `timeout` dùng đồng hồ monotonic, không phụ thuộc `/clock`. Tham số đọc lúc khởi động; sửa cấu hình rồi khởi động lại. Topic bài này cố định `/cmd_vel` trong launch để khớp với relay mô phỏng.

## Kiểm thử

Unit test và kiểm thử topic ROS 2 dùng camera/model giả lập, không cần tải model:

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate hri
source /opt/ros/humble/setup.bash
export PYTHONNOUSERSITE=1
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
FACE_EMOTE_ROS_TEST=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
```

Kiểm tra chuyển động mô phỏng qua đủ sáu trạng thái mà không cần DeepFace/webcam:

```bash
# Terminal 1:
./run.sh headless:=true recognition:=false
# Terminal 2: trong thư mục chứa run.sh, cùng ROS_DOMAIN_ID
source ~/miniconda3/etc/profile.d/conda.sh
conda activate hri
source /opt/ros/humble/setup.bash
source .run_ws/install/setup.bash
export PYTHONNOUSERSITE=1 ROS_LOCALHOST_ONLY=1
python test/check_sim_motion.py
```

Script bơm sáu biểu cảm vào chính `Controller` rồi gửi `/cmd_vel`, kiểm tra dấu vận tốc đo từ `/odom`, sau đó kiểm tra robot dừng khi mất heartbeat. Đây là kiểm thử đường điều khiển và physics, không đo độ chính xác nhận diện khuôn mặt hay xác minh góc quay đủ 360°. Chế độ `recognition:=false` chỉ phục vụ kiểm tra sim; mặc định nhận diện webcam bật.

Đã kiểm tra bằng Conda `hri`: `run.sh --check` và `run.sh --build-only` thành công; model Emotion ONNX thật đã tải/nạp và chạy dự đoán; 22 unit/ROS test đạt; Gazebo Fortress headless tạo TurtleBot 4 Lite và kích hoạt hai controller; kiểm tra `/odom` đạt cho cả sáu hành động và watchdog. Phần kiểm thử dùng dữ liệu khuôn mặt giả lập; chất lượng nhận diện với webcam người dùng và giao diện Gazebo cần được kiểm tra khi sử dụng.

Tham khảo: [TurtleBot 4 Simulator (Humble)](https://github.com/turtlebot/turtlebot4_simulator/tree/humble), [DeepFace](https://github.com/serengil/deepface).
