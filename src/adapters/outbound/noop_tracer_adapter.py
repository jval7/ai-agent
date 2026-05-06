"""NoopTracerAdapter — TracerPort que no emite spans.

Para entornos donde no se quiere overhead de tracing (tests offline, dev local
sin LangSmith, deploys donde tracing está deliberadamente desactivado).
"""

import contextlib
import typing

import src.ports.tracer_port as tracer_port


class _NoopTraceRun(tracer_port.TraceRun):
    def add_metadata(self, metadata: dict[str, object]) -> None:
        del metadata

    def set_outputs(self, outputs: dict[str, object]) -> None:
        del outputs

    def set_error(self, error_message: str) -> None:
        del error_message


class NoopTracerAdapter(tracer_port.TracerPort):
    def is_enabled(self) -> bool:
        return False

    @contextlib.contextmanager
    def trace(
        self,
        *,
        name: str,
        run_type: str,
        inputs: typing.Mapping[str, object] | None = None,
        metadata: typing.Mapping[str, object] | None = None,
        tags: list[str] | None = None,
    ) -> typing.Generator[tracer_port.TraceRun, None, None]:
        del name, run_type, inputs, metadata, tags
        yield _NoopTraceRun()
