# Bài 8 — Biểu cảm khuôn mặt điều khiển TurtleBot trong sim

Chạy **TurtleBot 4 Lite trong Gazebo Fortress, ROS 2 Humble**. Webcam máy tính nhận diện biểu cảm người dùng; robot di chuyển trong world `emotion_arena` của package. Một lệnh launch mở cả Gazebo, tạo robot, kích hoạt bộ điều khiển bánh xe và chạy DeepFace/OpenCV. Không cần robot thật hoặc submodule.

Luồng điều khiển: webcam → MediaPipe tìm mặt → DeepFace phân loại vùng mặt → lọc biểu cảm → `/cmd_vel` (`Twist`, 20 Hz) → `sim_velocity_relay` → `/diffdrive_controller/cmd_vel_unstamped` → bánh xe trong Gazebo. `/odom` phản ánh chuyển động mô phỏng, `/clock` lấy từ Gazebo.

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

Chờ robot xuất hiện trên sàn và controller được kích hoạt; giữ Neutral rồi thử từng biểu cảm trong bảng. Cửa sổ webcam hiển thị khung mặt, nhãn sau lọc, nhãn thô (`raw`), điểm số, FPS camera, thời gian inference, tuổi khung hình và hành động. Điểm số mô hình không phải độ chính xác đã được hiệu chuẩn. Nhấn **Q/Esc** để dừng nhận diện (relay tự dừng robot); **Ctrl+C** ở terminal launch để đóng toàn bộ sim.

Mặc định làm mượt toàn bộ điểm số biểu cảm trong khoảng 0.25 giây, cần điểm số sau lọc ≥55%, chênh lệch với nhãn đứng thứ hai ≥12 điểm phần trăm và 3 kết quả liên tiếp cùng nhãn để bắt đầu. Mỗi biểu cảm chỉ kích hoạt một hành động, giữ nguyên không lặp vô hạn. Giữ Neutral đủ 3 kết quả ổn định để kích hoạt lại cùng hành động, hoặc đổi sang biểu cảm khác. Neutral hợp lệ dừng robot ngay, nhưng một khung Neutral thoáng qua không cho phép lặp lại chuyển động. Khi đổi biểu cảm, robot dừng trong thời gian chờ đủ mẫu mới.

Mất mặt, nhiều mặt, `disgust` (ngoài 6 trạng thái đề bài), điểm sau lọc thấp hoặc lỗi camera làm robot dừng khi nhận kết quả. Camera không có khung mới quá `camera_timeout` (0.5 giây) cũng làm robot dừng, kể cả khi inference đang bận. Nếu inference treo/chậm, dừng sau `timeout` kể từ lúc chụp mẫu hợp lệ cuối; giữ cùng biểu cảm không tự tiếp tục hành động đã timeout. Relay dừng đầu ra nếu mất `/cmd_vel` trong 0.5 giây. Controller bánh xe cũng có timeout 0.5 giây.

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

`linear_speed` dương, tối đa 0.2 m/s; `angular_speed` dương, tối đa 1 rad/s. `arc_duration` và `step_duration` giới hạn thời gian chuyển động. `stable_samples` đếm kết quả inference. `inference_period` là chu kỳ mục tiêu giữa hai lần bắt đầu inference (mặc định 0.1 giây); không cộng thêm thời gian nghỉ sau khi model xử lý xong. Không bảo đảm FPS nếu máy bận. `timeout` dùng đồng hồ monotonic, không phụ thuộc `/clock`. Tham số đọc lúc khởi động; sửa cấu hình rồi khởi động lại. Topic bài này cố định `/cmd_vel` trong launch để khớp với relay mô phỏng.

## Camera và độ ổn định nhận diện

Camera được đọc liên tục trong một luồng riêng. Preview chạy tối đa 30 FPS; inference chỉ lấy khung mới nhất từ một ô nhớ, bỏ qua các khung cũ thay vì xếp hàng. Preview không bị thay bằng ảnh cũ sau khi model xử lý xong. Camera yêu cầu MJPEG 640×480, 30 FPS và buffer 1; giá trị thực tế phụ thuộc driver, ánh sáng và phần cứng.

MediaPipe tìm mặt trên ảnh thu nhỏ (rộng tối đa 320 px), lấy mốc mắt để hiệu chỉnh nghiêng nhẹ, rồi DeepFace chỉ phân loại vùng mặt 224×224. Không chạy lại bộ tìm mặt/mắt trên toàn ảnh trong mỗi lần phân loại. Cần đúng một mặt đủ lớn; không dùng `skip` trên toàn khung khi chưa xác minh có mặt.

Bộ lọc làm mượt điểm số cả 7 nhãn, gồm `disgust`, theo thời gian và kiểm tra khoảng cách giữa hai điểm cao nhất. Bộ lọc được xóa khi mất mặt, xuất hiện nhiều mặt, mặt đổi vị trí quá xa hoặc khoảng thời gian nhận diện bị gián đoạn; điểm số cũ không bị mang sang một mặt ở vị trí khác. Cơ chế này giảm nhảy nhãn nhưng không bảo đảm mọi biểu cảm đều nhận đúng; nên nhìn thẳng, để mặt đủ lớn và chiếu sáng đều.

Các tham số trong `config/emotions.yaml`:

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `camera_width`, `camera_height`, `camera_fps` | 640, 480, 30 | Yêu cầu định dạng camera |
| `camera_mjpeg` | true | Dùng MJPEG nếu camera hỗ trợ |
| `camera_timeout` | 0.5 s | Dừng nếu không đọc được khung mới |
| `detection_width` | 320 | Giới hạn chiều rộng ảnh tìm mặt |
| `min_face_size` | 30 px | Kích thước mặt tối thiểu trên ảnh tìm mặt |
| `detector_confidence` | 0.65 | Ngưỡng tìm mặt của MediaPipe |
| `inference_period` | 0.1 s | Chu kỳ mục tiêu phân loại |
| `smoothing_seconds` | 0.25 s | Độ mượt điểm số; tăng sẽ phản hồi chậm hơn |
| `emotion_margin` | 0.12 | Chênh lệch tối thiểu giữa hai nhãn dẫn đầu |
| `confidence`, `stable_samples` | 0.55, 3 | Điểm sau lọc và số mẫu xác nhận |

Nếu cần giảm tải cho Gazebo, chạy `./run.sh headless:=true`. Nếu camera không hỗ trợ MJPEG, đặt `camera_mjpeg: false` trong file tham số riêng rồi truyền bằng `params_file:=...`. Sau khi chỉnh cấu hình, dừng và chạy lại `./run.sh` để build/nạp cấu hình mới.

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

Đã kiểm tra bằng Conda `hri`: `run.sh --check` và `run.sh --build-only` thành công; model Emotion ONNX thật đã tải/nạp và chạy dự đoán; 37 unit/ROS test đạt; Gazebo Fortress headless tạo TurtleBot 4 Lite và kích hoạt hai controller; kiểm tra `/odom` đạt cho cả sáu hành động và watchdog. Benchmark 20 lần sau warm-up trên ảnh mẫu Grace Hopper của Matplotlib (410×480) trong Conda `hri`: pipeline cũ median 847.9 ms, mới 23.8 ms; đây là đo trên ảnh tĩnh, không phải cam kết FPS nhận diện trên mọi máy. Đo webcam thực trong 5 giây, không lưu ảnh: camera khoảng 20.5 FPS, tuổi khung sau khi đọc tới vòng preview p95 48.9 ms; FPS thực phụ thuộc driver và thời gian phơi sáng. Kiểm thử hồi quy xác nhận capture vẫn cập nhật trong khi inference bị chặn, timeout vẫn dừng robot và bộ lọc không đổi nhãn vì một mẫu nhiễu. Phần kiểm thử ROS dùng dữ liệu khuôn mặt giả lập; chất lượng nhận diện với webcam người dùng và giao diện Gazebo cần được kiểm tra khi sử dụng.

Tham khảo: [TurtleBot 4 Simulator (Humble)](https://github.com/turtlebot/turtlebot4_simulator/tree/humble), [DeepFace](https://github.com/serengil/deepface).
