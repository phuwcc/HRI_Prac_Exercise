# BÁO CÁO BÀI THỰC HÀNH 04 – TURTLEBOT 4

> Thay toàn bộ phần trong dấu `<...>`, chèn ảnh thật và xuất tài liệu này thành
> PDF. Không nộp nguyên template.

## 1. Thông tin

- Họ tên: `<...>`
- MSSV: `<...>`
- Lớp: `<...>`
- Link video công khai: `<...>`
- Link GitHub Public: `<...>`

## 2. Cấu trúc chương trình

Package `turtlebot_simu` gồm ba launch file cho simulation, mapping và
localization/navigation; ba node tiện ích để kiểm tra topic, lưu map và chạy ba
goal; cấu hình waypoint và cặp file map YAML/PGM.

`<Chèn hình cây thư mục và giải thích ngắn từng file>`

## 3. Các node/package và topic chính

| Thành phần | Vai trò | Input chính | Output chính |
|---|---|---|---|
| TurtleBot 4 simulator/bridge | Mô phỏng robot và cảm biến | `/cmd_vel` | `/scan`, `/odom`, TF |
| SLAM Toolbox | Xây map và ước lượng pose đồng thời | `/scan`, TF | `/map`, `map -> odom` |
| map_server | Nạp occupancy map đã lưu | `map.yaml`, `map.pgm` | `/map` |
| AMCL | Localization trên map tĩnh | `/scan`, `/map`, TF | pose, particle cloud, `map -> odom` |
| Nav2 planner | Tạo global path | goal, global costmap | global path |
| Nav2 controller | Bám đường/tránh vật cản | path, local costmap, odometry | `/cmd_vel` |

## 4. Quá trình xây dựng bản đồ

`<Mô tả world, cách teleop, loop closure, chất lượng map và chèn ảnh RViz>`

Map là occupancy grid: pixel tối là vật cản, pixel sáng là vùng tự do, vùng chưa
quan sát có giá trị chưa biết. `map.yaml` lưu resolution, origin và ngưỡng phân
loại; `map.pgm` chứa dữ liệu ảnh.

## 5. Localization

`<Mô tả cách load map, đặt 2D Pose Estimate, quan sát particle cloud hội tụ và
so sánh pose giữa RViz với Gazebo; chèn ảnh>`

AMCL dùng particle filter. Mỗi particle là một giả thuyết pose; odometry dùng để
dự đoán chuyển động, còn LaserScan và map dùng để cập nhật trọng số.

## 6. Navigation với Nav2

`<Liệt kê tọa độ ba goal, kết quả từng goal, ảnh path/costmap và mô tả tránh vật cản>`

Global planner tìm đường trên global costmap. Controller tạo vận tốc để bám
đường dựa trên local costmap; behavior tree điều phối planning, controlling,
recovery và điều kiện hoàn thành goal.

## 7. Nội dung cần hiểu

### `/scan`, `/odom`, `/cmd_vel` dùng để làm gì?

`<Trả lời bằng hiểu biết của sinh viên, dựa trên bảng ở mục 3>`

### Vì sao cần TF `map -> odom -> base_link`?

`<Giải thích quan hệ hệ tọa độ toàn cục, liên tục cục bộ và thân robot>`

### Khác nhau giữa SLAM và localization?

`<Giải thích SLAM vừa tạo map vừa ước lượng pose; localization dùng map có sẵn>`

### Nav2 lập kế hoạch và điều khiển robot thế nào?

`<Giải thích planner, controller, costmap, behavior tree và cmd_vel>`

## 8. Kết luận

`<Nêu kết quả đạt được, vấn đề gặp phải và cách khắc phục>`
