"""Ordering guards for independently fetched resources and live invalidations."""

from typing import Any


class ResourceState:
    """Reject snapshots overtaken by events, older revisions, or retired epochs."""

    def __init__(self, limit: int = 500) -> None:
        self.limit = limit
        self.generation = 0
        self.epoch: str | None = None
        self.retired_epochs: set[str] = set()
        self.revisions: dict[str, int] = {}

    def invalidate(self, stamp: dict[str, Any]) -> bool:
        """Mark an accepted event as a barrier for requests already in flight."""
        if not self.accept("event", stamp):
            return False
        self.generation += 1
        return True

    def accept(self, resource: str, stamp: dict[str, Any]) -> bool:
        """Accept monotonic, paired revision metadata; allow unversioned resources."""
        epoch, revision = stamp.get("epoch"), stamp.get("revision")
        if epoch is None and revision is None:
            return True
        if (
            not isinstance(epoch, str)
            or not epoch.strip()
            or type(revision) is not int
            or not 1 <= revision <= 2**53 - 1
            or epoch in self.retired_epochs
        ):
            return False
        if epoch != self.epoch:
            if self.epoch is not None:
                self.retired_epochs.add(self.epoch)
            self.epoch = epoch
            self.revisions.clear()
            self.generation += 1
        if revision < self.revisions.get(resource, -1):
            return False
        self.revisions.pop(resource, None)
        self.revisions[resource] = revision
        if len(self.revisions) > self.limit:
            self.revisions.pop(next(iter(self.revisions)))
        return True
