"""
Device Management Node for SmartGuard ROS 2.
Implements:
- [#20 / #1 in desc 5] Device management with possibility to Add, Remove, Stop, Resume, and Start devices.
- ROS 2 Lifecycle State Machine Transitions (Unconfigured -> Inactive -> Active -> Finalized).
- Exposes ROS Service: /device_manager/manage (ManageDevice.srv).
"""

from typing import Dict, Any, List
from .ros_compat import Node, LifecycleNode, LifecycleState, QoSProfile
from .interfaces import ManageDeviceRequest, ManageDeviceResponse, DeviceStatusMsg

class DeviceManagerNode(Node):
    def __init__(self, node_name: str = "device_manager_node"):
        super().__init__(node_name)

        # Service for managing device lifecycles
        self.manage_service = self.create_service(
            ManageDeviceResponse,
            "/device_manager/manage",
            self.handle_manage_device
        )

        # Publisher for device registry updates
        self.status_pub = self.create_publisher(
            DeviceStatusMsg,
            "/device_manager/status",
            QoSProfile(depth=20, durability="TRANSIENT_LOCAL")
        )

        # Registry of managed devices and their lifecycle state
        self.managed_nodes: Dict[str, LifecycleNode] = {}
        self.registered_metadata: Dict[str, Dict[str, Any]] = {}

        self.get_logger().info("Device Manager Node initialized with ROS 2 Lifecycle Controller.")

    def register_lifecycle_node(self, device_id: str, node_instance: LifecycleNode, dev_type: str = "GENERIC"):
        """Attaches an instantiated ROS 2 Lifecycle Node to the manager."""
        self.managed_nodes[device_id] = node_instance
        self.registered_metadata[device_id] = {
            "type": dev_type,
            "lifecycle_state": node_instance.current_state,
            "battery_level": 100.0,
            "error_code": 0
        }
        self.get_logger().info(f"Registered Lifecycle Node '{device_id}' (State: {node_instance.current_state})")

    def handle_manage_device(self, req: ManageDeviceRequest) -> ManageDeviceResponse:
        action = req.action.upper()
        dev_id = req.device_id
        self.get_logger().info(f"Device Manager Command: Action='{action}', Device='{dev_id}'")

        # 1. ADD Device
        if action == "ADD":
            if dev_id in self.registered_metadata:
                return ManageDeviceResponse(success=False, previous_state=self.registered_metadata[dev_id]["lifecycle_state"],
                                            new_state=self.registered_metadata[dev_id]["lifecycle_state"],
                                            message=f"Device {dev_id} already exists.")
            # Provision new managed node
            new_node = LifecycleNode(node_name=dev_id)
            new_node.on_configure()  # Unconfigured -> Inactive
            self.managed_nodes[dev_id] = new_node
            self.registered_metadata[dev_id] = {
                "type": req.device_type or "DYNAMIC_SENSOR",
                "lifecycle_state": new_node.current_state,
                "battery_level": 100.0,
                "error_code": 0
            }
            self._broadcast_status(dev_id)
            return ManageDeviceResponse(success=True, previous_state=LifecycleState.UNCONFIGURED,
                                        new_state=new_node.current_state,
                                        message=f"Device {dev_id} added and configured.")

        # For remaining actions, device must exist
        if dev_id not in self.managed_nodes:
            return ManageDeviceResponse(success=False, previous_state="UNKNOWN", new_state="UNKNOWN",
                                        message=f"Device '{dev_id}' not found in registry.")

        node = self.managed_nodes[dev_id]
        prev_state = node.current_state

        # 2. START Device (Inactive -> Active)
        if action == "START":
            if prev_state == LifecycleState.ACTIVE:
                return ManageDeviceResponse(success=True, previous_state=prev_state, new_state=prev_state,
                                            message=f"Device {dev_id} already active.")
            node.on_activate()
            self.registered_metadata[dev_id]["lifecycle_state"] = node.current_state
            self._broadcast_status(dev_id)
            return ManageDeviceResponse(success=True, previous_state=prev_state, new_state=node.current_state,
                                        message=f"Device {dev_id} successfully STARTED.")

        # 3. STOP Device (Active -> Inactive)
        elif action == "STOP":
            if prev_state != LifecycleState.ACTIVE:
                return ManageDeviceResponse(success=False, previous_state=prev_state, new_state=prev_state,
                                            message=f"Cannot STOP device {dev_id} from state {prev_state}.")
            node.on_deactivate()
            self.registered_metadata[dev_id]["lifecycle_state"] = node.current_state
            self._broadcast_status(dev_id)
            return ManageDeviceResponse(success=True, previous_state=prev_state, new_state=node.current_state,
                                        message=f"Device {dev_id} successfully STOPPED.")

        # 4. RESUME Device (Inactive -> Active)
        elif action == "RESUME":
            if prev_state != LifecycleState.INACTIVE:
                return ManageDeviceResponse(success=False, previous_state=prev_state, new_state=prev_state,
                                            message=f"Cannot RESUME device {dev_id} from state {prev_state}.")
            node.on_activate()
            self.registered_metadata[dev_id]["lifecycle_state"] = node.current_state
            self._broadcast_status(dev_id)
            return ManageDeviceResponse(success=True, previous_state=prev_state, new_state=node.current_state,
                                        message=f"Device {dev_id} successfully RESUMED.")

        # 5. REMOVE Device (Any -> Finalized -> Deleted)
        elif action == "REMOVE":
            node.on_shutdown()
            del self.managed_nodes[dev_id]
            del self.registered_metadata[dev_id]
            return ManageDeviceResponse(success=True, previous_state=prev_state, new_state=LifecycleState.FINALIZED,
                                        message=f"Device {dev_id} safely REMOVED and decommissioned.")

        return ManageDeviceResponse(success=False, previous_state=prev_state, new_state=prev_state,
                                    message=f"Unsupported action '{action}'. Valid: ADD, REMOVE, START, STOP, RESUME.")

    def _broadcast_status(self, dev_id: str):
        if dev_id in self.registered_metadata:
            meta = self.registered_metadata[dev_id]
            msg = DeviceStatusMsg(
                device_id=dev_id,
                device_type=meta["type"],
                lifecycle_state=meta["lifecycle_state"],
                operational=(meta["lifecycle_state"] == LifecycleState.ACTIVE),
                battery_level_pct=meta["battery_level"],
                power_consumption_w=15.0 if meta["lifecycle_state"] == LifecycleState.ACTIVE else 0.5,
                firmware_version="v2.1-ros2",
                error_code=meta["error_code"]
            )
            self.status_pub.publish(msg)
