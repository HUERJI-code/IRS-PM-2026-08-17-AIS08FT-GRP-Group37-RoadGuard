"""A's task handoff snapshot, without B-owned crew or planning semantics."""

from typing import Literal, Self

from pydantic import model_validator

from .assessment import DemoOnly
from .common import ContractModel, NonNegativeInt
from .task import Task


class TaskSnapshot(ContractModel):
    contract_version: Literal["a-task-query-v1"] = "a-task-query-v1"
    source: Literal["persisted_workflow", "synthetic_fixture"]
    input_revision: NonNegativeInt
    tasks: list[Task]
    total: NonNegativeInt
    is_demo: DemoOnly = True

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        if self.total != len(self.tasks):
            raise ValueError("snapshot total must match task count")
        if len({task.task_id for task in self.tasks}) != self.total:
            raise ValueError("snapshot task IDs must be unique")
        if len({task.inspection_id for task in self.tasks}) != self.total:
            raise ValueError("snapshot inspection IDs must be unique")
        if any(task.status != "active" or task.is_demo is not True for task in self.tasks):
            raise ValueError("this handoff includes only active demo tasks")
        return self
