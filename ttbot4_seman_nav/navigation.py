"""ROS action client: execute a semantic route strictly one successful goal at a time."""
import math
import time

import rclpy
from action_msgs.msg import GoalStatus
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import OccupancyGrid
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String
from visualization_msgs.msg import Marker, MarkerArray

from .commands import CommandParser
from .map_data import load_regions


class VoiceNavigation(Node):
    def __init__(self):
        super().__init__('voice_navigation')
        self.declare_parameter('regions_file', '')
        self.declare_parameter('goal_timeout', 180.0)
        self.data, self.grid = load_regions(self.get_parameter('regions_file').value)
        self.parser = CommandParser(self.data['regions'])
        self.regions = {r['id']: r for r in self.data['regions']}
        self.timeout = float(self.get_parameter('goal_timeout').value)
        if not math.isfinite(self.timeout) or self.timeout <= 0:
            raise ValueError('goal_timeout must be finite and positive.')
        self.status_pub = self.create_publisher(String, 'semantic/status', 10)
        qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                         reliability=ReliabilityPolicy.RELIABLE)
        self.markers_pub = self.create_publisher(MarkerArray, 'semantic/markers', qos)
        self.map_sub = self.create_subscription(OccupancyGrid, 'map', self.on_map, qos)
        self.command_sub = self.create_subscription(String, 'voice/command', self.on_command, 10)
        self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.route = []
        self.active = False
        self.goal_handle = None
        self.cancel_requested = False
        self.deadline = 0
        self.live_map = None
        self.create_timer(.5, self.tick)
        self.create_timer(2.0, self.publish_markers)
        self.report('Sẵn sàng nhận câu lệnh; chờ map/Nav2. Undock và định vị trước khi chạy.')

    def report(self, message):
        self.get_logger().info(message)
        self.status_pub.publish(String(data=message))

    def on_map(self, message):
        self.live_map = message

    def check_live_map(self, region):
        msg = self.live_map
        if msg is None or msg.header.frame_id != 'map':
            raise ValueError('Chưa nhận map trong frame map.')
        info = msg.info
        ox, oy, yaw = self.grid.origin
        q = info.origin.orientation
        live_yaw = math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))
        h, w = self.grid.image.shape
        if (info.width != w or info.height != h or abs(info.resolution-self.grid.resolution) > 1e-6
                or abs(info.origin.position.x-ox) > 1e-5 or abs(info.origin.position.y-oy) > 1e-5
                or abs(math.atan2(math.sin(live_yaw-yaw), math.cos(live_yaw-yaw))) > 1e-5):
            raise ValueError('Map đang chạy khác map đã phân vùng; hãy tạo lại regions.')
        g = region['goal']
        u, v = self.grid.world_to_pixel(g['x'], g['y'])
        row = h-1-v
        radius = math.ceil(self.data['clearance']/info.resolution)
        for dy in range(-radius, radius+1):
            for dx in range(-radius, radius+1):
                if math.hypot(dx,dy)*info.resolution > self.data['clearance']:
                    continue
                x, y = u+dx, row+dy
                if not (0 <= x < w and 0 <= y < h) or msg.data[y*w+x] != 0:
                    raise ValueError('Điểm đích không đủ khoảng trống trên map hiện tại.')

    def on_command(self, message):
        try:
            route = self.parser.parse(message.data)
            if route is None:
                self.stop('Đã yêu cầu hủy điều hướng.')
                return
            if self.active:
                raise ValueError('Robot đang chạy. Nói “dừng lại”, chờ hủy xong rồi gửi lệnh mới.')
            if not self.client.server_is_ready():
                raise ValueError('Nav2 chưa sẵn sàng.')
            for region_id in route:
                self.check_live_map(self.regions[region_id])
            self.route = list(route)
            self.active = True
            self.cancel_requested = False
            self.send_next()
        except (ValueError, KeyError, IndexError) as error:
            self.report(f'Từ chối: {error}')

    def send_next(self):
        if not self.route:
            self.active = False
            self.report('Hoàn thành toàn bộ lộ trình.')
            return
        region_id = self.route.pop(0)
        try:
            self.check_live_map(self.regions[region_id])
        except ValueError as error:
            self.active = False
            self.route.clear()
            self.report(f'Dừng lộ trình: {error}')
            return
        g = self.regions[region_id]['goal']
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = float(g['x'])
        goal.pose.pose.position.y = float(g['y'])
        goal.pose.pose.orientation.z = math.sin(g.get('yaw', 0)/2)
        goal.pose.pose.orientation.w = math.cos(g.get('yaw', 0)/2)
        self.deadline = time.monotonic() + self.timeout
        self.report(f'Đang đến {region_id}: {self.regions[region_id]["name"]}')
        self.client.send_goal_async(goal).add_done_callback(self.accepted)

    def accepted(self, future):
        try:
            self.goal_handle = future.result()
            if not self.goal_handle.accepted:
                self.active = False
                self.route.clear()
                self.goal_handle = None
                self.report('Nav2 từ chối goal; đã dừng lộ trình.')
                return
            self.goal_handle.get_result_async().add_done_callback(self.finished)
            if self.cancel_requested:
                self.goal_handle.cancel_goal_async()
        except Exception as error:
            self.route.clear()
            self.report(f'Lỗi gửi goal; cần kiểm tra Nav2 và khởi động lại node: {error}')
            # Keep busy: a transport error does not prove the robot stopped.

    def finished(self, future):
        try:
            status = future.result().status
        except Exception as error:
            self.report(f'Không nhận được kết quả; kiểm tra Nav2: {error}')
            return
        self.goal_handle = None
        if self.cancel_requested or status != GoalStatus.STATUS_SUCCEEDED:
            self.route.clear()
            self.active = False
            self.report(f'Đã dừng lộ trình, trạng thái Nav2={status}.')
            return
        self.report('Đã đến điểm đích.')
        self.send_next()

    def stop(self, reason):
        self.route.clear()
        self.cancel_requested = True
        if self.goal_handle is not None:
            self.goal_handle.cancel_goal_async()
        self.report(reason)

    def tick(self):
        if self.active and not self.cancel_requested and time.monotonic() > self.deadline:
            self.stop('Hết thời gian; yêu cầu Nav2 hủy goal, dừng các điểm còn lại.')

    def publish_markers(self):
        array = MarkerArray()
        for i, region in enumerate(self.regions.values()):
            for kind in (Marker.SPHERE, Marker.TEXT_VIEW_FACING):
                m = Marker()
                m.header.frame_id = 'map'
                m.header.stamp = self.get_clock().now().to_msg()
                m.ns = 'regions'
                m.id = i*2 + (kind == Marker.TEXT_VIEW_FACING)
                m.type, m.action = kind, Marker.ADD
                m.pose.position.x = float(region['goal']['x'])
                m.pose.position.y = float(region['goal']['y'])
                m.pose.position.z = .5 if kind == Marker.TEXT_VIEW_FACING else .1
                m.pose.orientation.w = 1.0
                m.scale.x = m.scale.y = m.scale.z = .24
                m.color.a = 1.0
                m.color.g = .9
                m.color.b = .4
                m.text = f"{region['id']}: {region['name']}"
                array.markers.append(m)
        self.markers_pub.publish(array)


def main(args=None):
    # Keep the ROS context alive long enough to cancel an active goal on Ctrl+C.
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    node = None
    try:
        node = VoiceNavigation()
        rclpy.spin(node)
    except KeyboardInterrupt:
        if node is not None:
            node.stop('Node dừng, gửi yêu cầu hủy goal.')
            end = time.monotonic()+2
            while node.active and time.monotonic() < end:
                rclpy.spin_once(node, timeout_sec=.1)
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
