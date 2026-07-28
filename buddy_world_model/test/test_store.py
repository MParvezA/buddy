from pathlib import Path

from buddy_world_model.store import SemanticStore
import pytest


CONFIG = Path(__file__).parents[1] / 'config' / 'named_locations.yaml'


def test_resolves_known_location_case_insensitively():
    store = SemanticStore.from_yaml(CONFIG)
    assert store.resolve(' Kitchen ').name == 'kitchen'
    assert store.resolve('missing') is None


def test_observation_store_is_bounded_and_replaces_by_id():
    store = SemanticStore.from_yaml(CONFIG, max_observations=2)
    store.record_observation('a', 1)
    store.record_observation('b', 2)
    store.record_observation('a', 3)
    assert store.observations == (3, 2)
    store.record_observation('c', 4)
    assert store.observations == (2, 4)


def test_rejects_non_map_location_file(tmp_path):
    config = tmp_path / 'locations.yaml'
    config.write_text('frame_id: odom\nlocations: []\n')
    with pytest.raises(ValueError, match='map frame'):
        SemanticStore.from_yaml(config)
