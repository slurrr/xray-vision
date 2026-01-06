from __future__ import annotations

from abc import ABC, abstractmethod

from .contracts import DashboardViewModel


class DashboardRenderer(ABC):
    """DVM-only renderer interface.

    Renderers manage their own lifecycle and never reach upstream inputs.
    """

    @abstractmethod
    def start(self) -> None:
        """Start the renderer. Must not depend on builder state or upstream schemas."""

    @abstractmethod
    def stop(self) -> None:
        """Stop the renderer gracefully without affecting builder operation."""

    @abstractmethod
    def render(self, snapshot: DashboardViewModel) -> None:
        """Render the latest snapshot. Implementations must treat the DVM as immutable."""


def validate_renderer_input(snapshot: object) -> DashboardViewModel:
    if not isinstance(snapshot, DashboardViewModel):
        raise TypeError("renderer accepts DashboardViewModel snapshots only")
    return snapshot
