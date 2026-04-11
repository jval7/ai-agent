import abc


class TaskSchedulerPort(abc.ABC):
    @abc.abstractmethod
    def schedule_auto_close(
        self,
        tenant_id: str,
        scheduling_request_id: str,
        delay_seconds: int,
    ) -> str:
        raise NotImplementedError
