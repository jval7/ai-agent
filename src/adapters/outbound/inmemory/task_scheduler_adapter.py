import src.ports.task_scheduler_port as task_scheduler_port


class InMemoryTaskSchedulerAdapter(task_scheduler_port.TaskSchedulerPort):
    def __init__(self) -> None:
        self.scheduled_tasks: list[dict[str, str | int]] = []

    def schedule_auto_close(
        self,
        tenant_id: str,
        scheduling_request_id: str,
        delay_seconds: int,
    ) -> str:
        task_name = f"inmemory-task-{len(self.scheduled_tasks)}"
        self.scheduled_tasks.append(
            {
                "tenant_id": tenant_id,
                "scheduling_request_id": scheduling_request_id,
                "delay_seconds": delay_seconds,
                "task_name": task_name,
            }
        )
        return task_name
