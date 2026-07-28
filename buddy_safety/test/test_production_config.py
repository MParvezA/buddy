# Copyright 2026 SyncRobot

import ast
from pathlib import Path

import yaml


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_production_config_requires_exact_controller_heartbeat():
    config = yaml.safe_load((PACKAGE_ROOT / 'config' / 'safety.yaml').read_text())
    parameters = config['/buddy/safety_filter']['ros__parameters']

    assert parameters['require_controller_diagnostics'] is True
    assert parameters['controller_diagnostic_name'] == 'buddy_base_controller'
    assert parameters['controller_diagnostics_timeout_ms'] == 500.0


def test_production_launch_applies_shared_config_to_safety_filter():
    launch_path = PACKAGE_ROOT / 'launch' / 'safety_motion.launch.py'
    tree = ast.parse(launch_path.read_text())

    safety_nodes = []
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        if not isinstance(call.func, ast.Name) or call.func.id != 'Node':
            continue
        keywords = {keyword.arg: keyword.value for keyword in call.keywords}
        executable = keywords.get('executable')
        if isinstance(executable, ast.Constant) and executable.value == 'safety_filter':
            safety_nodes.append(keywords)

    assert len(safety_nodes) == 1
    parameters = safety_nodes[0]['parameters']
    assert isinstance(parameters, ast.List)
    assert len(parameters.elts) == 1
    config_call = parameters.elts[0]
    assert isinstance(config_call, ast.Call)
    assert isinstance(config_call.func, ast.Name)
    assert config_call.func.id == 'str'
    assert len(config_call.args) == 1
    assert isinstance(config_call.args[0], ast.Name)
    assert config_call.args[0].id == 'config'
