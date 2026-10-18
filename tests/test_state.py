"""Reject obsolete revisions, malformed stamps and retired backend lifetimes."""

import pytest

from custom_components.bedrock_server_manager.state import ResourceState


def test_ordering_is_per_resource_and_retired_epochs_cannot_return():
    state = ResourceState()
    assert state.accept("metrics", {"epoch": "first", "revision": 10})
    assert state.accept("summary", {"epoch": "first", "revision": 5})
    assert not state.accept("metrics", {"epoch": "first", "revision": 9})
    assert state.accept("metrics", {"epoch": "second", "revision": 1})
    assert not state.accept("summary", {"epoch": "first", "revision": 20})


@pytest.mark.parametrize(
    "stamp",
    [
        {"epoch": "x"},
        {"revision": 1},
        {"epoch": "", "revision": 1},
        {"epoch": "x", "revision": True},
        {"epoch": "x", "revision": 0},
        {"epoch": "x", "revision": 2**53},
    ],
)
def test_invalid_stamp_is_rejected(stamp):
    assert not ResourceState().accept("metrics", stamp)
