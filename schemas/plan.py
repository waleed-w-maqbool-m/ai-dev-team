"""Project Manager planning output."""
from pydantic import BaseModel, Field

from schemas.task import Task


class ProjectPlan(BaseModel):
    overview: str
    tasks: list[Task] = Field(default_factory=list)


class PMCheckOutput(BaseModel):
    """Output of the PM's post-review 'what happens next' pass."""
    project_status: str  # ProjectStatus value, kept as str to decouple schema from enum import
    next_task_id: str | None = None
    clarification_answer: str | None = None
    notes: str = ""
