"""Software Engineer output: file changes + summary."""
from enum import Enum
from pydantic import BaseModel, Field


class FileAction(str, Enum):
    create = "create"
    modify = "modify"
    delete = "delete"


class FileChange(BaseModel):
    path: str
    action: FileAction
    content: str = ""  # full new file content; empty for delete


class ImplementationSummary(BaseModel):
    task_id: str
    files_changed: list[FileChange] = Field(default_factory=list)
    summary: str = ""
    needs_clarification: bool = False
    clarification_question: str | None = None
