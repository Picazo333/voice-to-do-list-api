from fastapi import APIRouter, HTTPException, status

from src.app.schemas.voice import Task, TaskCreate, TaskReplace, TaskUpdate
from src.app.services.task_store import (
    create_task,
    delete_task,
    list_tasks,
    replace_task,
    update_task,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[Task])
def get_tasks() -> list[Task]:
    return [Task(**item) for item in list_tasks()]


@router.post("", response_model=Task, status_code=status.HTTP_201_CREATED)
def post_task(payload: TaskCreate) -> Task:
    created = create_task(payload.title, payload.done)
    return Task(**created)


@router.put("/{task_id}", response_model=Task)
def put_task(task_id: int, payload: TaskReplace) -> Task:
    if task_id < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Task id must be a positive integer.",
        )
    replaced = replace_task(task_id, payload.title, payload.done)
    return Task(**replaced)


@router.patch("/{task_id}", response_model=Task)
def patch_task(task_id: int, payload: TaskUpdate) -> Task:
    if task_id < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Task id must be a positive integer.",
        )
    updated = update_task(task_id, title=payload.title, done=payload.done)
    return Task(**updated)


@router.delete("/{task_id}")
def remove_task(task_id: int) -> dict[str, str]:
    if task_id < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Task id must be a positive integer.",
        )
    return delete_task(task_id)
