# Bài thực hành 7 — Phân vùng bản đồ và điều hướng bằng giọng nói

Package ROS 2 Humble `ttbot4_seman_nav`, dùng **Conda `hri` (Python 3.10)**.
Mô phỏng, AMCL và Nav2 được dùng lại từ package `turtlebot_simu` trong workspace.
Không cần sao chép hoặc sửa mã của các bài trước.

## 1. Chuẩn bị và build

Chạy từ thư mục workspace `~/ur_robot_drawing`:

```bash
cd ~/ur_robot_drawing
source ttbot4_seman_nav/scripts/activate_hri.bash
python --version  # phải là Python 3.10 để dùng rclpy của Humble
python -m pip install -r ttbot4_seman_nav/requirements.txt
sudo apt update
sudo apt install libportaudio2 ffmpeg ros-humble-rmw-cyclonedds-cpp
# Nếu PortAudio của hệ thống không có hoặc sounddevice không tìm được:
conda install -n hri -c conda-forge portaudio -y
rosdep install --from-paths turtlebot_simu ttbot4_seman_nav --ignore-src -r -y
python -m colcon --log-base log_seman build --build-base build_seman \
  --install-base install_seman --packages-select turtlebot_simu ttbot4_seman_nav --symlink-install
source install_seman/setup.bash
```

Nếu thiếu simulator/Nav2, cài các dependency theo README của
[`turtlebot_simu`](../turtlebot_simu/README.md).
Script kích hoạt source Conda, ROS, workspace, đặt cùng Cyclone DDS cho các
terminal. Các lệnh build và cài thư viện chạy bằng Python của `hri`.
Không chạy package bằng Python 3.11/3.12.

## 2. Phân vùng và đặt tên

Phải có map đã lưu từ SLAM, đúng với world sẽ chạy. Đọc hướng dẫn quét/lưu
map trong `turtlebot_simu`. Không dùng map khởi tạo hoặc map của world khác.

### Cách thủ công: ba khu vực chức năng A, B, C

File `config/polygons_small_room.yaml` minh họa ba đa giác trên ảnh
`small_room.pgm` hiện có trong repository. Đây là nhãn chức năng do người dùng
đặt, không phải kết quả xác định loại phòng tự động. Sau khi quét lại map, sửa
các đỉnh đa giác theo ảnh mới trước khi chạy:

```bash
source ttbot4_seman_nav/scripts/activate_hri.bash
ros2 run ttbot4_seman_nav segment_map \
  --map "$PWD/turtlebot_simu/maps/small_room.yaml" \
  --polygons "$PWD/ttbot4_seman_nav/config/polygons_small_room.yaml" \
  --output "$PWD/ttbot4_seman_nav/config/regions_small_room.yaml"
```

`polygon: [[u,v], ...]` dùng pixel, gốc trên trái, `u` sang phải, `v` xuống dưới.
Có thể mở ảnh bằng trình sửa ảnh để đọc tọa độ. Mỗi vùng cần ít nhất ba đỉnh,
không chồng lên nhau và có vùng trống đủ rộng. Các đốm free rời rạc rất nhỏ
được bỏ qua; đa giác phủ nhiều vùng trống tách biệt đáng kể sẽ bị từ chối.
Tên và `aliases` có thể sửa trong YAML đa giác, sau đó chạy lại phân vùng.

Chương trình tạo:

- `regions_small_room.yaml`: ID, tên, alias, điểm đích trong frame `map`.
- `regions_small_room.png`: bản đồ màu có ID và điểm đích đỏ.
- `regions_small_room.labels.npy`: ma trận nhãn pixel; 0 là không được gắn nhãn.

Điểm đích tự chọn trong vùng trống, mặc định cách tường/unknown ít nhất 0.30 m.
Chuyển pixel sang mét có xét resolution, origin, yaw và đảo trục dọc của ảnh.
YAML xuất ra lưu đường dẫn tới map tương đối với file vùng để giữ được khi chuyển workspace.

### Cách tự động

```bash
ros2 run ttbot4_seman_nav segment_map \
  --map "$PWD/turtlebot_simu/maps/small_room.yaml" \
  --output "$PWD/ttbot4_seman_nav/config/regions_auto.yaml" \
  --doorway-width 0.8 --min-area 0.5 --clearance 0.30
```

Thuật toán dùng occupancy threshold, distance transform để tách lõi phòng ở
các cửa hẹp, connected components và lan nhãn theo khoảng cách qua ô free.
Tên mặc định `R1`, `R2`, ...; sửa `name`/`aliases` trong YAML kết quả để có tên
ngữ nghĩa. `--doorway-width` tính bằng mét, `--min-area` bằng m².
Nếu tìm được dưới ba lõi, chương trình báo lỗi để điều chỉnh hoặc phân vùng
thủ công. Vùng free bên ngoài tường do SLAM cũng có thể được phân vùng;
phải xem ảnh kết quả, giữ các vùng robot có thể tiếp cận. Thuật toán không
suy ra chức năng phòng hoặc chứng minh mọi đích đều đi được từ vị trí robot.

## 3. Chạy mô phỏng và giọng nói

Terminal 1:

```bash
cd ~/ur_robot_drawing
source ttbot4_seman_nav/scripts/activate_hri.bash
ros2 launch ttbot4_seman_nav coursework.launch.py \
  regions:="$PWD/ttbot4_seman_nav/config/regions_small_room.yaml" \
  world:=small_room
```

Launch mở simulation headless, RViz, localization, Nav2 và hai node của bài 7.
Trên RViz đặt **2D Pose Estimate** nếu cần, đợi localization/Nav2 active và
laser khớp tường. Nếu map có gốc khác, truyền `initial_x`, `initial_y`,
`initial_yaw` hoặc `auto_initial_pose:=false` để đặt pose thủ công.
Đảm bảo **world đúng với map**, không chỉ dựa vào tên file `small_room`.

Terminal 2, undock trước khi gửi lệnh:

```bash
cd ~/ur_robot_drawing
source ttbot4_seman_nav/scripts/activate_hri.bash
ros2 action send_goal /undock irobot_create_msgs/action/Undock '{}'
```

Đợi `SUCCEEDED`. Khi node báo **Micro sẵn sàng**, nói trong lượt thu 5 giây,
chờ Whisper xử lý rồi mới nói lệnh tiếp theo. Whisper mặc định `base`, tiếng
Việt, CPU; lần đầu cần Internet để tải model. Có thể dùng `whisper_model:=small`
để tăng chất lượng nhưng thời gian xử lý lâu hơn. Bản multilingual được dùng,
không dùng model hậu tố `.en` cho tiếng Việt.

Ba câu lệnh cần nghiệm thu:

1. “Đi đến khu vực A.”
2. “Di chuyển từ khu vực A đến khu vực B.”
3. “Đi đến phòng thí nghiệm.”

Mở rộng: “Đi từ phòng A qua hành lang C rồi đến phòng B”. Node giữ thứ tự
A → C → B và chỉ chuyển đích khi goal trước thành công. Kể cả robot đang ở
nơi khác, lệnh từ A đến B luôn gửi A trước B. Nhận cả văn bản không dấu.
“Nói dừng lại”/“hủy điều hướng” gửi yêu cầu cancel tới Nav2. Việc nhận giọng
nói theo từng đoạn và thời gian suy luận có độ trễ; nút dừng của simulator
vẫn cần dùng khi muốn dừng ngay.

Lệnh chứa bất kỳ vùng không tồn tại sẽ bị từ chối toàn bộ. Khi đang có nhiệm
vụ, lệnh mới bị từ chối; hãy hủy và đợi kết quả hủy rồi gửi lại. Goal lỗi,
bị từ chối hoặc quá 180 giây sẽ dừng các điểm còn lại. Nav2 đảm nhiệm tránh
vật cản và lập đường; metadata map và khoảng trống tại đích được kiểm tra
lại trên `/map` đang chạy trước mỗi goal.

Đọc trạng thái:

```bash
ros2 topic echo /semantic/status
```

Trong RViz: **Add → By topic → /semantic/markers → MarkerArray** để hiện tên
vùng và các điểm đích. Ảnh PNG xuất ra hiển thị đầy đủ phần tô màu phân vùng.

## 4. Kiểm tra bằng văn bản, chọn micro và dùng Nav2 có sẵn

Tắt micro khi kiểm tra riêng logic:

```bash
ros2 launch ttbot4_seman_nav coursework.launch.py \
  regions:="$PWD/ttbot4_seman_nav/config/regions_small_room.yaml" speech:=false
```

Trong terminal đã kích hoạt `hri`:

```bash
ros2 topic pub --once /voice/command std_msgs/msg/String "{data: 'Đi đến khu vực A.'}"
ros2 topic pub --once /voice/command std_msgs/msg/String "{data: 'Di chuyển từ khu vực A đến khu vực B.'}"
ros2 topic pub --once /voice/command std_msgs/msg/String "{data: 'Đi đến phòng thí nghiệm.'}"
ros2 topic pub --once /voice/command std_msgs/msg/String "{data: 'Đi đến khu vực Z.'}"
ros2 topic pub --once /voice/command std_msgs/msg/String "{data: 'Dừng lại'}"
```

Gửi từng câu khi nhiệm vụ trước đã hoàn thành. Câu chứa Z phải báo từ chối,
không di chuyển. Nếu đã mở Nav2 đúng map, thêm `navigation:=false` để chỉ
chạy phần bài 7. Cấu hình hiện tại dùng namespace gốc và frame `map`.

Chọn micro hoặc GPU bằng cách chạy node giọng nói riêng, tắt `speech` trong launch:

```bash
python -c 'import sounddevice as sd; print(sd.query_devices())'
ros2 run ttbot4_seman_nav speech_recognition --ros-args \
  -p microphone:="USB Audio" -p model:=base -p device:=cpu
```

Nếu import `rclpy` lỗi, kiểm tra `which python`, phiên bản 3.10 và đã source
ROS. Nếu PortAudio không có thiết bị, kiểm tra micro của Ubuntu/VM và chọn
đúng thiết bị. Model cần tải thành công trước khi bắt đầu thu. Ngưỡng im lặng
`min_rms` mặc định 0.008 giúp hạn chế Whisper suy diễn khi không có lời nói.

## 5. Kiểm thử và giới hạn xác minh

```bash
source ttbot4_seman_nav/scripts/activate_hri.bash
ROS_DOMAIN_ID=86 python -m pytest ttbot4_seman_nav/test -q
ROS_DOMAIN_ID=86 python -m colcon --log-base log_seman test --build-base build_seman \
  --install-base install_seman --packages-select ttbot4_seman_nav --python-testing pytest
python -m colcon test-result --test-result-base build_seman --verbose
```

Unit test kiểm tra câu lệnh tiếng Việt, nhiều điểm, vùng không tồn tại,
chuyển tọa độ với map xoay, tránh unknown/tường, phân vùng tự động và thủ công.
Kiểm thử ROS dùng action server Nav2 giả lập để xác minh thứ tự đích, hủy
trước khi chấp nhận goal, dừng sau abort và từ chối map không khớp.
Khóa pytest dưới phiên bản 9 để tương thích plugin launch_testing của Humble.
Chạy nghiệm thu Gazebo/micro vẫn cần xác nhận riêng: ít nhất ba vùng có nhãn,
ba câu giọng nói điều khiển đúng, A → B đúng thứ tự, tránh vật cản và từ chối Z.
Không xem kết quả build/unit test là bằng chứng robot đã chạy thành công.
