"""ProjectState: the single shared blackboard every agent reads/writes."""
from enum import Enum
from pydantic import BaseModel, Field

from schemas.task import Task, TaskStatus
from schemas.messages import AgentMessage
from schemas.documentation import DocumentationOutput


class ProjectStatus(str, Enum):
    planning = "planning"
    in_progress = "in_progress"
    blocked_on_clarification = "blocked_on_clarification"
    documenting = "documenting"
    complete = "complete"


class RunConfig(BaseModel):
    max_review_iterations: int = 3
    max_clarification_rounds: int = 2
    model_name: str = "qwen3:8b"
    temperature_pm: float = 0.1
    temperature_swe: float = 0.3
    temperature_qa: float = 0.1
    temperature_docs: float = 0.2


class ProjectState(BaseModel):
    user_request: str
    tasks: list[Task] = Field(default_factory=list)
    current_task_id: str | None = None
    project_status: ProjectStatus = ProjectStatus.planning
    review_iterations: dict[str, int] = Field(default_factory=dict)
    clarification_rounds: int = 0
    pending_clarification: str | None = None
    messages: list[AgentMessage] = Field(default_factory=list)
    documentation: DocumentationOutput | None = None
    final_summary: str | None = None
    config: RunConfig = Field(default_factory=RunConfig)

    # ---- convenience helpers used by nodes/routing (kept here so agents
    # don't re-implement state-reading logic independently) ----

    @classmethod
    def new(cls, user_request: str, config: RunConfig | None = None) -> "ProjectState":
        return cls(user_request=user_request, config=config or RunConfig())

    def get_task(self, task_id: str) -> Task:
        return next(t for t in self.tasks if t.id == task_id)

    def get_current_task(self) -> Task | None:
        if self.current_task_id is None:
            return None
        return self.get_task(self.current_task_id)

    def next_pending_task(self, preferred_id: str | None = None) -> Task | None:
        """Next task whose dependencies are all done — `preferred_id` if that
        one is runnable, otherwise the first runnable task in list order."""
        done_ids = {t.id for t in self.tasks if t.status == TaskStatus.done}
        runnable = [
            t for t in self.tasks
            if t.status == TaskStatus.pending and set(t.depends_on).issubset(done_ids)
        ]
        for t in runnable:
            if t.id == preferred_id:
                return t
        return runnable[0] if runnable else None

    def tasks_with_unrunnable_blocked(self) -> list[Task]:
        """If tasks are still pending but none of them can ever start — a
        dependency was set aside for human review, or the plan has a cycle or
        an unknown task id — mark them blocked_needs_human too. Without this
        they'd count as remaining forever and the run would never finish."""
        if self.next_pending_task() is not None:
            return self.tasks
        return [
            t.model_copy(update={"status": TaskStatus.blocked_needs_human})
            if t.status == TaskStatus.pending else t
            for t in self.tasks
        ]

    def has_remaining_tasks(self) -> bool:
        return any(
            t.status in (TaskStatus.pending, TaskStatus.in_progress, TaskStatus.in_review)
            for t in self.tasks
        )

    def with_task_updated(self, updated: Task) -> list[Task]:
        """Return a new tasks list with `updated` swapped in by id."""
        return [updated if t.id == updated.id else t for t in self.tasks]

    def append_message(self, msg: AgentMessage) -> list[AgentMessage]:
        return [*self.messages, msg]
