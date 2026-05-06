import src.adapters.outbound.noop_tracer_adapter as noop_tracer_adapter


def test_noop_tracer_is_not_enabled() -> None:
    tracer = noop_tracer_adapter.NoopTracerAdapter()

    assert tracer.is_enabled() is False


def test_noop_tracer_yields_run_that_swallows_metadata() -> None:
    tracer = noop_tracer_adapter.NoopTracerAdapter()

    with tracer.trace(name="some-span", run_type="chain") as run:
        run.add_metadata({"key": "value"})
        run.set_outputs({"output": "done"})
        # Calling set_error after set_outputs must not raise.
        run.set_error("ignored")


def test_noop_tracer_trace_supports_optional_arguments() -> None:
    tracer = noop_tracer_adapter.NoopTracerAdapter()

    with tracer.trace(
        name="span-with-args",
        run_type="tool",
        inputs={"prompt": "hi"},
        metadata={"environment": "test"},
        tags=["a", "b"],
    ) as run:
        run.set_outputs({"text": "ok"})


def test_noop_tracer_trace_can_be_used_repeatedly() -> None:
    tracer = noop_tracer_adapter.NoopTracerAdapter()

    for index in range(3):
        with tracer.trace(name=f"span-{index}", run_type="chain") as run:
            run.set_outputs({"index": index})
