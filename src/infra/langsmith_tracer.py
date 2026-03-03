import contextlib
import typing

import langsmith.client as langsmith_client
import langsmith.run_helpers as langsmith_run_helpers

import src.infra.logs as app_logs

logger = app_logs.get_logger(__name__)


class LangsmithTraceRun:
    def __init__(self, run_tree: typing.Any | None) -> None:
        self._run_tree = run_tree
        self._ended = False

    def add_metadata(self, metadata: dict[str, object]) -> None:
        if self._run_tree is None:
            return
        if not metadata:
            return
        self._run_tree.add_metadata(metadata)

    def set_outputs(self, outputs: dict[str, object]) -> None:
        if self._run_tree is None:
            return
        if self._ended:
            return
        self._run_tree.end(outputs=outputs)
        self._ended = True

    def set_error(self, error_message: str) -> None:
        if self._run_tree is None:
            return
        if self._ended:
            return
        self._run_tree.end(error=error_message)
        self._ended = True


class LangsmithTracer:
    def __init__(
        self,
        *,
        enabled: bool = False,
        project_name: str = "ai-agent",
        api_key: str | None = None,
        api_url: str | None = None,
        workspace_id: str | None = None,
        environment: str | None = None,
        tags: list[str] | None = None,
    ) -> None:
        self._enabled = enabled
        self._project_name = project_name.strip()
        self._environment = self._normalize_optional_text(environment)
        self._default_tags = self._normalize_tags(tags)
        self._client: langsmith_client.Client | None = None

        if not self._enabled:
            return

        if not self._project_name:
            logger.warning(
                "langsmith.disabled",
                extra={
                    "event_data": app_logs.build_log_event(
                        event_name="langsmith.disabled",
                        message="langsmith tracing disabled because project name is empty",
                    )
                },
            )
            self._enabled = False
            return

        normalized_api_url = self._normalize_optional_text(api_url)
        normalized_api_key = self._normalize_optional_text(api_key)
        normalized_workspace_id = self._normalize_optional_text(workspace_id)
        self._client = langsmith_client.Client(
            api_url=normalized_api_url,
            api_key=normalized_api_key,
            workspace_id=normalized_workspace_id,
        )

    def is_enabled(self) -> bool:
        return self._enabled and self._client is not None

    @contextlib.contextmanager
    def trace(
        self,
        *,
        name: str,
        run_type: str,
        inputs: typing.Mapping[str, object] | None = None,
        metadata: typing.Mapping[str, object] | None = None,
        tags: list[str] | None = None,
    ) -> typing.Generator[LangsmithTraceRun, None, None]:
        if not self.is_enabled():
            yield LangsmithTraceRun(None)
            return

        combined_tags = self._combine_tags(tags)
        run_metadata = self._build_metadata(metadata)
        run_inputs: dict[str, object] | None = None
        if inputs is not None:
            run_inputs = dict(inputs)
        tracing_context_manager: contextlib.AbstractContextManager[typing.Any] | None = None
        trace_context: contextlib.AbstractContextManager[typing.Any] | None = None
        run_tree: typing.Any | None = None
        try:
            tracing_context_candidate = langsmith_run_helpers.tracing_context(
                enabled=True,
                project_name=self._project_name,
                client=self._client,
            )
            tracing_context_candidate.__enter__()
            tracing_context_manager = tracing_context_candidate

            trace_context_candidate = langsmith_run_helpers.trace(
                name=name,
                run_type=typing.cast(langsmith_client.RUN_TYPE_T, run_type),
                inputs=run_inputs,
                project_name=self._project_name,
                metadata=run_metadata,
                tags=combined_tags,
                client=self._client,
            )
            run_tree = trace_context_candidate.__enter__()
            trace_context = trace_context_candidate
        except Exception as error:
            self._close_context_safely(
                context_manager=trace_context,
                name=name,
                run_type=run_type,
            )
            self._close_context_safely(
                context_manager=tracing_context_manager,
                name=name,
                run_type=run_type,
            )
            self._log_trace_failure(name=name, run_type=run_type, error=error)
            yield LangsmithTraceRun(None)
            return

        body_error: BaseException | None = None
        try:
            yield LangsmithTraceRun(run_tree)
        except BaseException as error:
            body_error = error
            raise
        finally:
            self._close_context_safely(
                context_manager=trace_context,
                name=name,
                run_type=run_type,
                body_error=body_error,
            )
            self._close_context_safely(
                context_manager=tracing_context_manager,
                name=name,
                run_type=run_type,
                body_error=body_error,
            )

    def _close_context_safely(
        self,
        *,
        context_manager: contextlib.AbstractContextManager[typing.Any] | None,
        name: str,
        run_type: str,
        body_error: BaseException | None = None,
    ) -> None:
        if context_manager is None:
            return
        try:
            if body_error is None:
                context_manager.__exit__(None, None, None)
            else:
                context_manager.__exit__(
                    type(body_error),
                    body_error,
                    body_error.__traceback__,
                )
        except Exception as error:
            self._log_trace_failure(name=name, run_type=run_type, error=error)

    def _log_trace_failure(self, *, name: str, run_type: str, error: BaseException) -> None:
        logger.warning(
            "langsmith.trace_failed",
            extra={
                "event_data": app_logs.build_log_event(
                    event_name="langsmith.trace_failed",
                    message="langsmith trace failed and was skipped",
                    data={
                        "trace_name": name,
                        "run_type": run_type,
                        "error_message": str(error),
                    },
                )
            },
        )

    def _build_metadata(
        self, metadata: typing.Mapping[str, object] | None
    ) -> dict[str, object] | None:
        metadata_payload: dict[str, object] = {}
        if metadata is not None:
            metadata_payload.update(dict(metadata))
        if self._environment is not None:
            metadata_payload["environment"] = self._environment
        if not metadata_payload:
            return None
        return metadata_payload

    def _combine_tags(self, tags: list[str] | None) -> list[str] | None:
        combined: list[str] = []
        for tag in self._default_tags:
            if tag not in combined:
                combined.append(tag)
        if tags is not None:
            for tag in tags:
                if tag not in combined:
                    combined.append(tag)
        if not combined:
            return None
        return combined

    def _normalize_tags(self, tags: list[str] | None) -> list[str]:
        normalized_tags: list[str] = []
        if tags is None:
            return normalized_tags
        for tag in tags:
            normalized_tag = tag.strip()
            if normalized_tag and normalized_tag not in normalized_tags:
                normalized_tags.append(normalized_tag)
        return normalized_tags

    def _normalize_optional_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip()
        if not normalized_value:
            return None
        return normalized_value
