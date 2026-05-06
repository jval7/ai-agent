"""TracerPort — abstracción mínima de tracing usada por services y adapters.

Decoupling rationale: services y agentic tools necesitan emitir spans/metadata
para observabilidad, pero NO deben conocer la herramienta concreta (LangSmith,
OpenTelemetry, lo que sea). Este port define el contrato mínimo. La
implementación productiva (LangSmith) vive en `adapters/outbound/`. Para
contextos sin tracing configurado (tests, dev local), `NoopTracerAdapter`
proporciona un tracer que cumple el contrato sin emitir nada.
"""

import abc
import contextlib
import typing


class TraceRun(abc.ABC):
    """Single trace span. Mutable mientras `trace()` está abierto."""

    @abc.abstractmethod
    def add_metadata(self, metadata: dict[str, object]) -> None:
        """Adjuntar metadata estructurada al span actual."""
        raise NotImplementedError

    @abc.abstractmethod
    def set_outputs(self, outputs: dict[str, object]) -> None:
        """Marcar el span como exitoso con los outputs dados.

        Una vez llamado, el span queda cerrado para set_error/set_outputs
        adicionales. Llamadas posteriores son no-op silentes.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def set_error(self, error_message: str) -> None:
        """Marcar el span como fallido. Idempotente con set_outputs (gana
        el primero)."""
        raise NotImplementedError


class TracerPort(abc.ABC):
    @abc.abstractmethod
    def is_enabled(self) -> bool:
        """True si el tracer está activo y emitiendo spans hacia un backend."""
        raise NotImplementedError

    @abc.abstractmethod
    def trace(
        self,
        *,
        name: str,
        run_type: str,
        inputs: typing.Mapping[str, object] | None = None,
        metadata: typing.Mapping[str, object] | None = None,
        tags: list[str] | None = None,
    ) -> contextlib.AbstractContextManager[TraceRun]:
        """Abrir un span con el nombre dado.

        Si el tracer no está habilitado, devuelve un context manager que
        produce un TraceRun no-op — los callers no necesitan chequear
        is_enabled() antes de cada `with`.
        """
        raise NotImplementedError
