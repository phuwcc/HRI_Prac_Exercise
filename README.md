# Bài 7 — Điều hướng bằng giọng nói

ROS 2 Humble, Conda `hri` (Python 3.10). Các script tự kích hoạt môi trường
và source workspace. Chạy các lệnh dưới từ `~/ur_robot_drawing`.

## 1. Build

```bash
cd ~/ur_robot_drawing
./ttbot4_seman_nav/scripts/build.sh
```

Máy mới cần cài dependency và overlay TF2 trước: xem [cài đặt](docs/REFERENCE.md#1-chuẩn-bị-và-build).
Sau khi sửa code/config, build lại rồi khởi động lại launch.

## 2. Chọn một chế độ chạy

**Có mic — Terminal 1:**

```bash
./ttbot4_seman_nav/scripts/run_mic.sh
```

Chờ log **Listening**; giữ im lặng khi đo nhiễu nền lúc đầu. Nói tiếng Anh,
ngắt khoảng 0,8 giây để kết thúc câu. Mặc định Whisper `base.en` trên CPU,
lần đầu cần tải model. Ví dụ chọn micro/model khác:

```bash
./ttbot4_seman_nav/scripts/run_mic.sh microphone:="USB Audio" whisper_model:=tiny.en
```

**Không mic — Terminal 1:**

```bash
./ttbot4_seman_nav/scripts/run_no_mic.sh
```

Chế độ này vẫn chạy Gazebo, RViz, AMCL và Nav2; gửi lệnh văn bản ở bước 4.
Chỉ mở **một** chế độ; dừng bằng `Ctrl+C` trước khi đổi chế độ.
Script từ chối mở thêm một phiên trên cùng ROS domain. Mỗi launch tạo kênh
Gazebo riêng để tránh nối nhầm vào simulator cũ còn sót sau khi thoát.

## 3. Undock — Terminal 2

Chờ **Managed nodes are active** của Nav2 rồi chạy:

```bash
./ttbot4_seman_nav/scripts/undock.sh
```

Chờ **SUCCEEDED** trước khi gửi lệnh. RViz mặc định mở sau khi localization
sẵn sàng. Đặt pose thủ công bằng `auto_initial_pose:=false` nếu cần.
Nếu log còn `scan=False`, `odom_tf=0` hoặc `Requesting list of world names`,
robot chưa sẵn sàng: chưa gửi undock hay lệnh đi. `Robot already undocked`
chỉ là lý do từ chối undock, không chứng minh Nav2 đã hoạt động.

## 4. Các lệnh kiểm tra có sẵn — Terminal 2

Dùng được ở cả hai chế độ. Gửi **từng lệnh**, đợi nhiệm vụ trước hoàn thành;
không chạy cả khối lệnh liên tiếp.

| Lệnh | Câu nói tương đương | Kết quả mong đợi |
| --- | --- | --- |
| `./ttbot4_seman_nav/scripts/send_command.sh a` | Go to area A. | Đến A (Classroom) |
| `./ttbot4_seman_nav/scripts/send_command.sh b` | Go to area B. | Đến B (Laboratory) |
| `./ttbot4_seman_nav/scripts/send_command.sh c` | Go to area C. | Đến C (Corridor) |
| `./ttbot4_seman_nav/scripts/send_command.sh ab` | Go from area A to area B. | A → B |
| `./ttbot4_seman_nav/scripts/send_command.sh acb` | Go from A via C then to B. | A → C → B |
| `./ttbot4_seman_nav/scripts/send_command.sh lab` | Go to the laboratory. | Đến B |
| `./ttbot4_seman_nav/scripts/send_command.sh invalid` | Go to area Z. | Từ chối, không di chuyển |
| `./ttbot4_seman_nav/scripts/send_command.sh stop` | Stop. | Yêu cầu hủy nhiệm vụ đang chạy |

Gửi câu tự nhập:

```bash
./ttbot4_seman_nav/scripts/send_command.sh "Go to the classroom."
```

Theo dõi kết quả ở **Terminal 3**:

```bash
./ttbot4_seman_nav/scripts/status.sh
```

Khi robot đang bận, lệnh đi mới bị từ chối. Để kiểm tra hủy: gửi `ab`, đợi
robot bắt đầu đi rồi gửi `stop`; chờ xác nhận hủy trước khi gửi lệnh khác.

## 5. Check logic tự động — không cần Gazebo hoặc mic

```bash
./ttbot4_seman_nav/scripts/check_logic.sh
```

Kiểm tra parser, vùng không tồn tại, tách câu nói, thứ tự đích, cancel và
timeout bằng Nav2 giả lập. Script dùng ROS domain 86 riêng; không phát lệnh
đến simulator đang chạy ở domain mặc định. Đây là kiểm thử logic, chưa xác
nhận chất lượng mic hoặc khả năng di chuyển thực tế.

## 6. Đổi bản đồ/phân vùng khi cần

Sửa đa giác và tên trong `config/polygons_small_room.yaml`, rồi tạo lại vùng:

```bash
./ttbot4_seman_nav/scripts/segment_map.sh manual
```

Hoặc phân vùng tự động: `./ttbot4_seman_nav/scripts/segment_map.sh auto`.
Hai lệnh ghi YAML, PNG và `.labels.npy`; xem PNG trước khi chạy điều hướng.
Vùng tự động dùng ID `R1`, `R2`, …; các preset A/B/C phía trên dành cho cấu
hình thủ công. Với vùng tự động, gửi câu theo ID/tên thực tế trong YAML.

Chọn file vùng khác hoặc dùng Nav2 đã chạy sẵn:

```bash
./ttbot4_seman_nav/scripts/run_no_mic.sh regions:="$PWD/ttbot4_seman_nav/config/regions_auto.yaml"
./ttbot4_seman_nav/scripts/run_no_mic.sh navigation:=false
```

Các script chạy mặc định với map trong `turtlebot_simu/maps`; map phải khớp
world, polygon và vị trí ban đầu. Chi tiết cài đặt, tọa độ, dock và chỉnh
ngưỡng mic: [tài liệu tham khảo](docs/REFERENCE.md). Mỗi script có `--help`.
