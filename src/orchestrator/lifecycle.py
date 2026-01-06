from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OrchestratorState(str, Enum):
    INIT = "init"
    RUNNING = "running"
    DRAINED = "drained"
    STOPPED = "stopped"
    DEGRADED = "degraded"


@dataclass
class Lifecycle:
    state: OrchestratorState = OrchestratorState.INIT

    def start(self) -> None:
        if self.state not in {OrchestratorState.INIT, OrchestratorState.DRAINED}:
            raise RuntimeError(f"cannot start from {self.state}")
        self.state = OrchestratorState.RUNNING

    def drain(self) -> None:
        if self.state != OrchestratorState.RUNNING:
            raise RuntimeError(f"cannot drain from {self.state}")
        self.state = OrchestratorState.DRAINED

    def stop(self) -> None:
        if self.state == OrchestratorState.STOPPED:
            return
        self.state = OrchestratorState.STOPPED

    def degrade(self) -> None:
        self.state = OrchestratorState.DEGRADED
