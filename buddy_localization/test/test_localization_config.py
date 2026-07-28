from pathlib import Path

import yaml


PACKAGE = Path(__file__).parents[1]


def test_ekf_is_only_odom_to_base_link_owner():
    params = yaml.safe_load((PACKAGE / 'config' / 'ekf.yaml').read_text())
    ekf = params['ekf_filter_node']['ros__parameters']
    assert ekf['map_frame'] == 'map'
    assert ekf['odom_frame'] == 'odom'
    assert ekf['base_link_frame'] == 'base_link'
    assert ekf['world_frame'] == 'odom'
    assert ekf['publish_tf'] is True
    assert ekf['odom0'] == '/odom/wheel'
    assert ekf['imu0'] == '/imu/data_raw'


def test_amcl_owns_map_to_odom_only_in_saved_map_mode():
    params = yaml.safe_load((PACKAGE / 'config' / 'amcl.yaml').read_text())
    amcl = params['amcl']['ros__parameters']
    assert amcl['global_frame_id'] == 'map'
    assert amcl['odom_frame_id'] == 'odom'
    assert amcl['base_frame_id'] == 'base_link'
    assert amcl['tf_broadcast'] is True
    launch = (PACKAGE / 'launch' / 'saved_map_localization.launch.py').read_text()
    assert 'slam_toolbox' not in launch


def test_all_localization_nodes_accept_sim_time():
    for filename in ('ekf.yaml', 'amcl.yaml'):
        config = yaml.safe_load((PACKAGE / 'config' / filename).read_text())
        for node in config.values():
            assert 'use_sim_time' in node['ros__parameters']


def test_base_controller_does_not_compete_for_odom_transform():
    workspace = PACKAGE.parent
    base_configs = [
        workspace / 'buddy_base' / 'config' / 'base_controller.yaml',
        workspace / 'buddy_description' / 'config' / 'buddy_controllers.yaml',
    ]
    for path in base_configs:
        params = yaml.safe_load(path.read_text())
        controller = params['buddy_base_controller']['ros__parameters']
        assert controller['odom_frame_id'] == 'odom'
        assert controller['base_frame_id'] == 'base_link'
        assert controller['enable_odom_tf'] is False
