"""ROS test process setup independent of the read-only interactive home."""

import os
from pathlib import Path


_ROS_LOG_DIR = Path('/tmp/buddy_voice_ros_logs')
_ROS_LOG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('ROS_LOG_DIR', str(_ROS_LOG_DIR))
