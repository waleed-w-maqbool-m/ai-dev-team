"""Task schema — the unit of work the PM plans and the SWE/QA operate on."""
from enum import Enum
from pydantic import BaseModel, Field

from schemas.review import ReviewReport
from schemas.testing import TestReport


class TaskStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    in_review = "in_review"
    blocked_needs_human = "blocked_needs_human"
    done = "done"


class AcceptanceCriterion(BaseModel):
    id: str
    description: str


class Task(BaseModel):
    id: str
    title: str
    description: str
    depends_on: list[str] = Field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.pending
    review_history: list[ReviewReport] = Field(default_factory=list)
    test_report: TestReport | None = None  # latest Testing Agent run; overwritten each retry

    def latest_review(self) -> ReviewReport | None:
        return self.review_history[-1] if self.review_history else None
