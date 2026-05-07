import typing

import pydantic

import src.infra.logs as app_logs
import src.ports.tracer_port as tracer_port
import src.services.agentic.tool_handlers.base as base
import src.services.dto.llm_dto as llm_dto
import src.services.exceptions as service_exceptions

logger = app_logs.get_logger(__name__)


class ToolHandlerRegistry:
    def __init__(
        self,
        handlers: list[base.ToolHandler],
        tracer: tracer_port.TracerPort,
    ) -> None:
        self._handlers: dict[str, base.ToolHandler] = {}
        for handler in handlers:
            name = handler.tool_name()
            if name in self._handlers:
                msg = f"duplicate tool handler for '{name}'"
                raise ValueError(msg)
            self._handlers[name] = handler
        self._tracer = tracer

    def execute(
        self,
        context: base.ToolExecutionContext,
        function_call: llm_dto.FunctionCallDTO,
    ) -> dict[str, object]:
        trace_inputs = {
            "tenant_id": context.tenant_id,
            "conversation_id": context.conversation_id,
            "whatsapp_user_id": context.whatsapp_user_id,
            "function_name": function_call.name,
            "function_args": _sanitize_trace_object(function_call.args),
        }
        with self._tracer.trace(
            name=f"webhook.function_call.{function_call.name}",
            run_type="tool",
            inputs=trace_inputs,
            tags=["webhook", "tool-call"],
        ) as trace_run:
            try:
                logger.info(
                    "webhook.llm.function_call_received",
                    extra={
                        "event_data": app_logs.build_log_event(
                            event_name="webhook.llm.function_call_received",
                            message="llm requested function execution",
                            data={
                                "tenant_id": context.tenant_id,
                                "conversation_id": context.conversation_id,
                                "function_name": function_call.name,
                            },
                        )
                    },
                )
                handler = self._handlers.get(function_call.name)
                if handler is None:
                    result: dict[str, object] = {
                        "error": f"unknown function: {function_call.name}",
                    }
                    trace_run.set_outputs(_summarize_tool_result_for_trace(result))
                    return result

                result = handler.execute(context, function_call)
                trace_run.set_outputs(_summarize_tool_result_for_trace(result))
                return result

            except pydantic.ValidationError as error:
                logger.warning(
                    "webhook.llm.function_call_validation_error",
                    extra={
                        "event_data": app_logs.build_log_event(
                            event_name="webhook.llm.function_call_validation_error",
                            message="function call validation failed",
                            data={
                                "tenant_id": context.tenant_id,
                                "conversation_id": context.conversation_id,
                                "function_name": function_call.name,
                                "error_message": str(error),
                            },
                        )
                    },
                )
                trace_run.set_error(str(error))
                return {"error": str(error)}

            except service_exceptions.ServiceError as error:
                logger.warning(
                    "webhook.llm.function_call_service_error",
                    extra={
                        "event_data": app_logs.build_log_event(
                            event_name="webhook.llm.function_call_service_error",
                            message="function call failed due service error",
                            data={
                                "tenant_id": context.tenant_id,
                                "conversation_id": context.conversation_id,
                                "function_name": function_call.name,
                                "function_args": _sanitize_trace_object(function_call.args),
                                "error_message": str(error),
                            },
                        )
                    },
                )
                trace_run.set_error(str(error))
                return {"error": str(error)}


def _summarize_tool_result_for_trace(
    result: typing.Mapping[str, object],
) -> dict[str, object]:
    summary: dict[str, object] = {
        "has_error": "error" in result,
    }
    status = result.get("status")
    if isinstance(status, str):
        summary["status"] = status
    request_id = result.get("request_id")
    if isinstance(request_id, str):
        summary["request_id"] = request_id
    return summary


def _sanitize_trace_object(value: object) -> object:
    if isinstance(value, str):
        if len(value) > 500:
            return value[:500] + "..."
        return value
    if isinstance(value, int | float | bool):
        return value
    if value is None:
        return value
    if isinstance(value, dict):
        return {k: _sanitize_trace_object(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_trace_object(item) for item in value]
    return str(value)
