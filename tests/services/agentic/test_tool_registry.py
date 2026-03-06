import src.services.agentic.tool_registry as tool_registry


def test_build_tool_definitions_filters_enabled_tool_names() -> None:
    registry = tool_registry.ToolDefinitionRegistry()

    tool_definitions = registry.build_tool_definitions(
        enabled_tool_names=[
            "submit_consultation_reason_for_review",
            "handoff_to_human",
        ]
    )

    tool_names = [tool_definition.name for tool_definition in tool_definitions]
    assert tool_names == [
        "submit_consultation_reason_for_review",
        "handoff_to_human",
    ]


def test_build_waiting_state_tool_definitions_returns_two_tools() -> None:
    registry = tool_registry.ToolDefinitionRegistry()

    tool_definitions = registry.build_waiting_state_tool_definitions()

    tool_names = [tool_definition.name for tool_definition in tool_definitions]
    assert tool_names == [
        "handoff_to_human",
        "cancel_active_scheduling_request",
    ]
