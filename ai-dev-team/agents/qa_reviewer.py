"""QA / Code Reviewer: evaluates the current task's implementation against
its acceptance criteria and produces a pass/fail verdict. This agent never
decides what node runs next — it only writes status/iteration-count fields
onto ProjectState; graph/routing.py reads those fields to route."""
from agents.base import BaseAgent
from schemas.state import ProjectState
from schemas.task import TaskStatus
from schemas.review import ReviewReport
from schemas.messages import AgentMessage, MessageType
from utils import context as ctx

SENDER = "qa_reviewer"


def qa_node(state: ProjectState) -> dict:
    agent = BaseAgent("qa_reviewer.md")
    task = state.get_current_task()

    impl_payload = ctx.latest_implementation_payload(state, task.id)
    prompt_ctx = ctx.qa_context(state, files_changed=impl_payload.get("files_changed", []))

    review: ReviewReport = agent.run(
        prompt_ctx, output_model=ReviewReport, temperature=state.config.temperature_qa
    )
    review.task_id = task.id  # trust our own bookkeeping over the model's echo

    iterations = dict(state.review_iterations)
    if review.is_pass():
        new_status = TaskStatus.done
    else:
        iterations[task.id] = iterations.get(task.id, 0) + 1
        if iterations[task.id] >= state.config.max_review_iterations:
            # Retry cap reached: stop looping this task. Recorded here (not
            # in routing.py) so ProjectState stays the single source of
            # truth — routing only ever reads status, never sets it.
            new_status = TaskStatus.blocked_needs_human
        else:
            new_status = TaskStatus.in_progress

    updated_task = task.model_copy(
        update={
            "status": new_status,
            "review_history": [*task.review_history, review],
        }
    )

    msg = AgentMessage(
        sender=SENDER,
        message_type=MessageType.review,
        payload=review.model_dump(mode="json"),
    )

    return {
        "tasks": state.with_task_updated(updated_task),
        "review_iterations": iterations,
        "messages": state.append_message(msg),
    }
