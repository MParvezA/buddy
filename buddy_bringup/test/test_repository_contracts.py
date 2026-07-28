"""Cross-package dependency, TF, and safety-boundary checks."""

from collections import defaultdict
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def _packages():
    """Return repository Buddy package manifests by package name."""
    result = {}
    for manifest in ROOT.glob('buddy_*/package.xml'):
        result[ET.parse(manifest).getroot().findtext('name')] = manifest
    return result


def test_buddy_package_dependency_graph_is_acyclic():
    """No Buddy package may create a build or runtime dependency cycle."""
    packages = _packages()
    edges = defaultdict(set)
    dependency_tags = (
        'depend',
        'build_depend',
        'buildtool_depend',
        'exec_depend',
        'test_depend',
    )
    for package, manifest in packages.items():
        root = ET.parse(manifest).getroot()
        for tag in dependency_tags:
            for dependency in root.findall(tag):
                if dependency.text in packages:
                    edges[package].add(dependency.text)

    visiting = set()
    visited = set()

    def visit(package):
        assert package not in visiting, f'dependency cycle reaches {package}'
        if package in visited:
            return
        visiting.add(package)
        for dependency in edges[package]:
            visit(dependency)
        visiting.remove(package)
        visited.add(package)

    for package in packages:
        visit(package)


def test_tf_owners_and_controller_path_match_contract():
    """Configuration preserves sole TF owners and disables controller TF."""
    ekf = yaml.safe_load(
        (ROOT / 'buddy_localization/config/ekf.yaml').read_text()
    )['ekf_filter_node']['ros__parameters']
    base = yaml.safe_load(
        (ROOT / 'buddy_base/config/base_controller.yaml').read_text()
    )['buddy_base_controller']['ros__parameters']
    slam = yaml.safe_load(
        (ROOT / 'buddy_mapping/config/slam_toolbox.yaml').read_text()
    )['slam_toolbox']['ros__parameters']
    amcl = yaml.safe_load(
        (ROOT / 'buddy_localization/config/amcl.yaml').read_text()
    )['amcl']['ros__parameters']

    assert ekf['world_frame'] == 'odom'
    assert ekf['odom_frame'] == 'odom'
    assert ekf['base_link_frame'] == 'base_link'
    assert ekf['publish_tf'] is True
    assert base['enable_odom_tf'] is False
    assert slam['map_frame'] == 'map'
    assert slam['odom_frame'] == 'odom'
    assert amcl['global_frame_id'] == 'map'
    assert amcl['odom_frame_id'] == 'odom'


def test_ai_and_voice_cannot_publish_motion():
    """AI and voice packages cannot even depend on the motion message layer."""
    for package in ('buddy_brain', 'buddy_voice'):
        source = '\n'.join(
            path.read_text()
            for path in (ROOT / package).rglob('*.py')
            if '/test/' not in str(path)
        )
        assert '/buddy/motion/' not in source
        assert 'geometry_msgs' not in source


def test_frozen_interface_package_is_still_marked_frozen():
    """Integration must not silently thaw or renumber the contracts."""
    contract = (ROOT / 'docs/contracts/README.md').read_text()
    assert 'FROZEN' in contract
    assert '0.1.0' in contract
