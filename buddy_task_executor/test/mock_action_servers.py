"""Deterministic frozen-interface action doubles for executive component tests."""

import time

from buddy_interfaces.action import NavigateToNamedLocation, Speak
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.node import Node


class MockCapabilityActionServers(Node):
    """Record requests and immediately return successful frozen action results."""

    def __init__(self):
        super().__init__('mock_capability_action_servers')
        self.speak_requests = []
        self.navigation_requests = []
        self.hold_speak = False
        self.hold_navigation = False
        self.navigation_outcome = NavigateToNamedLocation.Result.OUTCOME_SUCCEEDED
        self._speak_server = ActionServer(
            self, Speak, '/buddy/voice/speak', self._speak,
            goal_callback=self._accept, cancel_callback=self._cancel)
        self._navigation_server = ActionServer(
            self, NavigateToNamedLocation,
            '/buddy/navigation/navigate_to_named_location', self._navigate,
            goal_callback=self._accept, cancel_callback=self._cancel)

    @staticmethod
    def _accept(_request):
        return GoalResponse.ACCEPT

    @staticmethod
    def _cancel(_goal_handle):
        return CancelResponse.ACCEPT

    def _speak(self, goal_handle):
        self.speak_requests.append(goal_handle.request)
        result = Speak.Result()
        while self.hold_speak and not goal_handle.is_cancel_requested:
            time.sleep(0.01)
        if goal_handle.is_cancel_requested:
            result.outcome = Speak.Result.OUTCOME_CANCELLED
            result.message = 'mock speech cancelled'
            goal_handle.canceled()
            return result
        result.outcome = Speak.Result.OUTCOME_SUCCEEDED
        result.message = 'mock speech complete'
        goal_handle.succeed()
        return result

    def _navigate(self, goal_handle):
        self.navigation_requests.append(goal_handle.request)
        result = NavigateToNamedLocation.Result()
        while self.hold_navigation and not goal_handle.is_cancel_requested:
            time.sleep(0.01)
        if goal_handle.is_cancel_requested:
            result.outcome = NavigateToNamedLocation.Result.OUTCOME_CANCELLED
            result.message = 'mock navigation cancelled'
            goal_handle.canceled()
            return result
        result.outcome = self.navigation_outcome
        result.message = 'mock navigation complete'
        goal_handle.succeed()
        return result
