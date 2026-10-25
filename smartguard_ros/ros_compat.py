"""
ROS 2 Compatibility Layer for SmartGuard.
Provides seamless execution with real 'rclpy' if present, or an in-process, thread-safe
ROS 2 micro-kernel emulator supporting Nodes, LifecycleNodes, Topics, Services,
Actions, Timers, and QoS profiles.
"""

import sys
import time
import uuid
import logging
import threading
from typing import Callable, Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s]: %(message)s',
    datefmt='%H:%M:%S'
)

# ----------------------------------------------------------------------
# Real ROS 2 or Emulated Fallback
# ----------------------------------------------------------------------
HAVE_RCLPY = False
try:
    import rclpy
    from rclpy.node import Node as RealNode
    from rclpy.qos import QoSProfile as RealQoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy
    HAVE_RCLPY = True
except ImportError:
    pass

class QoSProfile:
    def __init__(self, depth: int = 10, reliability: str = "RELIABLE", durability: str = "VOLATILE"):
        self.depth = depth
        self.reliability = reliability
        self.durability = durability

# Global In-Process DDS Message Bus for Emulated ROS 2
class InProcessDDS:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.topics: Dict[str, List[Callable]] = {}
                cls._instance.services: Dict[str, Callable] = {}
                cls._instance.action_servers: Dict[str, Any] = {}
                cls._instance.latched_messages: Dict[str, Any] = {}
                cls._instance.bus_lock = threading.Lock()
            return cls._instance

    def register_publisher(self, topic: str, qos: QoSProfile):
        with self.bus_lock:
            if topic not in self.topics:
                self.topics[topic] = []

    def register_subscription(self, topic: str, callback: Callable, qos: QoSProfile):
        with self.bus_lock:
            if topic not in self.topics:
                self.topics[topic] = []
            self.topics[topic].append(callback)
            if qos.durability == "TRANSIENT_LOCAL" and topic in self.latched_messages:
                last_msg = self.latched_messages[topic]
                threading.Thread(target=callback, args=(last_msg,), daemon=True).start()

    def publish(self, topic: str, msg: Any, qos: QoSProfile):
        with self.bus_lock:
            if qos.durability == "TRANSIENT_LOCAL":
                self.latched_messages[topic] = msg
            subscribers = list(self.topics.get(topic, []))
        for cb in subscribers:
            try:
                cb(msg)
            except Exception as e:
                logging.getLogger("DDS").error(f"Error in subscriber callback for {topic}: {e}")

    def register_service(self, service_name: str, handler: Callable):
        with self.bus_lock:
            self.services[service_name] = handler

    def call_service(self, service_name: str, request: Any) -> Any:
        with self.bus_lock:
            handler = self.services.get(service_name)
        if handler is None:
            raise RuntimeError(f"Service '{service_name}' not available on DDS bus.")
        return handler(request)

    def register_action_server(self, action_name: str, server: Any):
        with self.bus_lock:
            self.action_servers[action_name] = server

    def get_action_server(self, action_name: str) -> Optional[Any]:
        with self.bus_lock:
            return self.action_servers.get(action_name)


class Publisher:
    def __init__(self, topic: str, msg_type: Any, qos: QoSProfile, node_name: str):
        self.topic = topic
        self.msg_type = msg_type
        self.qos = qos
        self.node_name = node_name
        self.dds = InProcessDDS()
        self.dds.register_publisher(topic, qos)

    def publish(self, msg: Any):
        self.dds.publish(self.topic, msg, self.qos)


class Subscription:
    def __init__(self, topic: str, msg_type: Any, callback: Callable, qos: QoSProfile):
        self.topic = topic
        self.msg_type = msg_type
        self.callback = callback
        self.qos = qos
        self.dds = InProcessDDS()
        self.dds.register_subscription(topic, callback, qos)


class Service:
    def __init__(self, srv_name: str, srv_type: Any, callback: Callable):
        self.srv_name = srv_name
        self.srv_type = srv_type
        self.callback = callback
        self.dds = InProcessDDS()
        self.dds.register_service(srv_name, callback)


class Client:
    def __init__(self, srv_name: str, srv_type: Any):
        self.srv_name = srv_name
        self.srv_type = srv_type
        self.dds = InProcessDDS()

    def call(self, request: Any) -> Any:
        return self.dds.call_service(self.srv_name, request)

    def wait_for_service(self, timeout_sec: float = 1.0) -> bool:
        start = time.time()
        while time.time() - start < timeout_sec:
            if self.srv_name in self.dds.services:
                return True
            time.sleep(0.02)
        return self.srv_name in self.dds.services


class Timer:
    def __init__(self, period_sec: float, callback: Callable):
        self.period_sec = period_sec
        self.callback = callback
        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while self.running:
            time.sleep(self.period_sec)
            if self.running:
                try:
                    self.callback()
                except Exception as e:
                    logging.getLogger("Timer").error(f"Timer callback error: {e}")

    def cancel(self):
        self.running = False


class ActionServer:
    def __init__(self, node: 'Node', action_name: str, execute_callback: Callable):
        self.node = node
        self.action_name = action_name
        self.execute_callback = execute_callback
        self.dds = InProcessDDS()
        self.dds.register_action_server(action_name, self)

    def execute_goal(self, goal_handle: 'ServerGoalHandle'):
        return self.execute_callback(goal_handle)


class ServerGoalHandle:
    def __init__(self, goal: Any, feedback_cb: Optional[Callable] = None):
        self.request = goal
        self.feedback_cb = feedback_cb
        self.is_active = True
        self.status = "EXECUTING"

    def publish_feedback(self, feedback: Any):
        if self.feedback_cb:
            self.feedback_cb(feedback)

    def succeed(self):
        self.status = "SUCCEEDED"
        self.is_active = False

    def abort(self):
        self.status = "ABORTED"
        self.is_active = False


class ActionClient:
    def __init__(self, node: 'Node', action_name: str):
        self.node = node
        self.action_name = action_name
        self.dds = InProcessDDS()

    def send_goal(self, goal: Any, feedback_callback: Optional[Callable] = None) -> Any:
        server = self.dds.get_action_server(self.action_name)
        if server is None:
            raise RuntimeError(f"Action server '{self.action_name}' not available.")
        goal_handle = ServerGoalHandle(goal, feedback_callback)
        result = server.execute_goal(goal_handle)
        return result


class Node:
    """Base ROS 2 Node abstraction."""
    def __init__(self, node_name: str):
        self.node_name = node_name
        self.logger = logging.getLogger(node_name)
        self.publishers: List[Publisher] = []
        self.subscriptions: List[Subscription] = []
        self.services: List[Service] = []
        self.clients: List[Client] = []
        self.timers: List[Timer] = []

    def get_logger(self):
        return self.logger

    def get_name(self) -> str:
        return self.node_name

    def create_publisher(self, msg_type: Any, topic: str, qos_profile: Optional[QoSProfile] = None) -> Publisher:
        qos = qos_profile or QoSProfile()
        pub = Publisher(topic, msg_type, qos, self.node_name)
        self.publishers.append(pub)
        return pub

    def create_subscription(self, msg_type: Any, topic: str, callback: Callable, qos_profile: Optional[QoSProfile] = None) -> Subscription:
        qos = qos_profile or QoSProfile()
        sub = Subscription(topic, msg_type, callback, qos)
        self.subscriptions.append(sub)
        return sub

    def create_service(self, srv_type: Any, srv_name: str, callback: Callable) -> Service:
        srv = Service(srv_name, srv_type, callback)
        self.services.append(srv)
        return srv

    def create_client(self, srv_type: Any, srv_name: str) -> Client:
        client = Client(srv_name, srv_type)
        self.clients.append(client)
        return client

    def create_timer(self, period_sec: float, callback: Callable) -> Timer:
        timer = Timer(period_sec, callback)
        self.timers.append(timer)
        return timer

    def destroy_node(self):
        for t in self.timers:
            t.cancel()


class LifecycleState:
    UNCONFIGURED = "UNCONFIGURED"
    INACTIVE = "INACTIVE"
    ACTIVE = "ACTIVE"
    FINALIZED = "FINALIZED"


class LifecycleNode(Node):
    """
    ROS 2 Managed Lifecycle Node matching Description 5:
    Add, Remove, Stop, Resume, Start.
    """
    def __init__(self, node_name: str):
        super().__init__(node_name)
        self._state = LifecycleState.UNCONFIGURED

    @property
    def current_state(self) -> str:
        return self._state

    def on_configure(self) -> bool:
        """Unconfigured -> Inactive"""
        self._state = LifecycleState.INACTIVE
        self.get_logger().info(f"Lifecycle state transitioned to: {self._state}")
        return True

    def on_activate(self) -> bool:
        """Inactive -> Active (Start / Resume)"""
        self._state = LifecycleState.ACTIVE
        self.get_logger().info(f"Lifecycle state transitioned to: {self._state}")
        return True

    def on_deactivate(self) -> bool:
        """Active -> Inactive (Stop / Pause)"""
        self._state = LifecycleState.INACTIVE
        self.get_logger().info(f"Lifecycle state transitioned to: {self._state}")
        return True

    def on_cleanup(self) -> bool:
        """Inactive -> Unconfigured"""
        self._state = LifecycleState.UNCONFIGURED
        self.get_logger().info(f"Lifecycle state transitioned to: {self._state}")
        return True

    def on_shutdown(self) -> bool:
        """Any -> Finalized (Remove)"""
        self._state = LifecycleState.FINALIZED
        self.destroy_node()
        self.get_logger().info(f"Lifecycle state transitioned to: {self._state}")
        return True
