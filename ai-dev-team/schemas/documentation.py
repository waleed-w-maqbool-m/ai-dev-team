"""Documentation Agent output."""
from pydantic import BaseModel, Field


class DocumentationOutput(BaseModel):
    readme_updates: str = ""
    changelog_entries: list[str] = Field(default_factory=list)
    docstring_updates: dict[str, str] = Field(default_factory=dict)
    user_summary: str = ""
