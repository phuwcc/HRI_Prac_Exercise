# ROS 2 Robotics — Universal Robots & TurtleBot 4

Workspace tổng hợp các bài thực hành robot trên **ROS 2 Humble**, từ điều khiển
cánh tay robot Universal Robots đến mô phỏng và điều hướng TurtleBot 4.
Dự án kết hợp lập kế hoạch chuyển động, thị giác máy tính, mô hình ngôn ngữ
và nhận diện cử chỉ để xây dựng các ứng dụng tương tác người – robot.

## Các bài thực hành

| Bài | Nội dung | Tài liệu |
|---|---|---|
| 1 | Vẽ chữ P bằng cánh tay UR và MoveIt 2 | [ur_drawing](ur_drawing/README.md) |
| 2 | Điều khiển UR3e gắp, đặt vật bằng ngôn ngữ tự nhiên với Gemini | [ur_llm_control](ur_llm_control/README.md) |
| 3 | Kết hợp camera RGB và Gemini để nhận biết vật, xử lý vị trí bị chiếm và thực hiện gắp, đặt | [ur_llm_camera](ur_llm_camera/README.md) |
| 4 | Mô phỏng TurtleBot 4, tạo bản đồ bằng SLAM và điều hướng bằng Nav2 | [turtlebot_simu](turtlebot_simu/README.md) |
| 5 | Điều hướng TurtleBot 4 qua các waypoint và nhận diện đối tượng bằng YOLO | [ttbot4_nav+detect](ttbot4_nav+detect/README.md) |
| 6 | Điều khiển TurtleBot 4 bằng cử chỉ tay qua webcam với MediaPipe | [ttbot4_handges_control](ttbot4_handges_control/README.md) |

## Công nghệ sử dụng

- **Nền tảng:** Ubuntu 22.04, ROS 2 Humble, Gazebo và RViz.
- **Cánh tay robot:** Universal Robots UR3e, tay gắp Robotiq 2F-85 và MoveIt 2.
- **Robot di động:** TurtleBot 4, SLAM Toolbox và Nav2.
- **AI và thị giác:** Gemini, OpenCV, YOLO và MediaPipe.

## Bắt đầu

Mỗi bài có hướng dẫn cài đặt, build và chạy riêng trong README tương ứng ở
bảng trên. Chọn bài muốn thực hành và làm theo tài liệu của bài đó.

Các thư mục `Universal_Robots_ROS2_GZ_Simulation`, `ros2_robotiq_gripper` và
`serial` cung cấp các thành phần phụ thuộc cho nhóm bài cánh tay robot.
