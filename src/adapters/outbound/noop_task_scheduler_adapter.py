import logging

import src.ports.task_scheduler_port as task_scheduler_port

logger = logging.getLogger(__name__)


class NoopTaskSchedulerAdapter(task_scheduler_port.TaskSchedulerPort):
    def schedule_auto_close(
        self,
        tenant_id: str,
        scheduling_request_id: str,
        delay_seconds: int,
    ) -> str:
        logger.info(
            "noop_task_scheduler.auto_close_skipped",
            extra={
                "tenant_id": tenant_id,
                "scheduling_request_id": scheduling_request_id,
                "delay_seconds": delay_seconds,
            },
        )
        return "noop-task"
