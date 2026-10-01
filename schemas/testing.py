"""Testing Agent output: real, executed evidence QA reads alongside the code —
not another LLM judgment. This is what makes QA's pass/fail "evidence-based
rather than purely inspection-based" (architecture doc, Section 20)."""
from pydantic import BaseModel, Field


class TestCheck(BaseModel):
    file: str
    check: str  # "syntax" | "import" | "smoke_run"
    passed: bool
    detail: str = ""


class TestReport(BaseModel):
    task_id: str
    status: str  # "pass" | "fail"
    checks: list[TestCheck] = Field(default_factory=list)
    summary: str = ""

    def is_pass(self) -> bool:
        return self.status == "pass"
