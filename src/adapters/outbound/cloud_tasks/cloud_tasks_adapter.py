import datetime
import json
import logging

import google.cloud.tasks_v2 as cloud_tasks_v2
import google.protobuf.timestamp_pb2 as timestamp_pb2  # type: ignore[import-untyped]

import src.ports.task_scheduler_port as task_scheduler_port
import src.services.exceptions as service_exceptions

logger = logging.getLogger(__name__)


class CloudTasksSchedulerAdapter(task_scheduler_port.TaskSchedulerPort):
    def __init__(
        self,
        project_id: str,
        location: str,
        queue_id: str,
        cloud_run_base_url: str,
    ) -> None:
        self._client = cloud_tasks_v2.CloudTasksClient()
        self._queue_path = self._client.queue_path(project_id, location, queue_id)
        self._cloud_run_base_url = cloud_run_base_url.rstrip("/")

    def schedule_auto_close(
        self,
        tenant_id: str,
        scheduling_request_id: str,
        delay_seconds: int,
    ) -> str:
        url = (
            f"{self._cloud_run_base_url}"
            f"/v1/internal/scheduling-requests/{scheduling_request_id}/auto-close"
        )
        payload = json.dumps({"tenant_id": tenant_id}).encode()

        schedule_time = timestamp_pb2.Timestamp()
        schedule_time.FromDatetime(
            datetime.datetime.now(tz=datetime.UTC) + datetime.timedelta(seconds=delay_seconds)
        )

        task = cloud_tasks_v2.Task(
            http_request=cloud_tasks_v2.HttpRequest(
                http_method=cloud_tasks_v2.HttpMethod.POST,
                url=url,
                headers={"Content-Type": "application/json"},
                body=payload,
                # TODO: agregar oidc_token cuando se implemente validación OIDC en el endpoint
            ),
            schedule_time=schedule_time,
        )

        try:
            created_task = self._client.create_task(
                parent=self._queue_path,
                task=task,
            )
            task_name: str = created_task.name
            logger.info(
                "cloud_tasks.auto_close_scheduled",
                extra={
                    "task_name": task_name,
                    "scheduling_request_id": scheduling_request_id,
                    "delay_seconds": delay_seconds,
                },
            )
            return task_name
        except Exception as exc:
            raise service_exceptions.ExternalProviderError(
                f"failed to create Cloud Task for auto-close: {exc}"
            ) from exc
