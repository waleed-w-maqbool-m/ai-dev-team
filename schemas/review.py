"""QA review output schema."""
from pydantic import BaseModel, Field


class CriterionFinding(BaseModel):
    criterion_id: str
    met: bool
    note: str = ""


class ReviewReport(BaseModel):
    task_id: str
    status: str  # "pass" | "fail"
    findings: list[CriterionFinding] = Field(default_factory=list)
    required_fixes: list[str] = Field(default_factory=list)
    summary: str = ""

    def is_pass(self) -> bool:
        return self.status == "pass"
