import src.ports.memory_admin_port as memory_admin_port
import src.services.use_cases.memory_admin_service as memory_admin_service


class FakeMemoryAdminAdapter(memory_admin_port.MemoryAdminPort):
    def __init__(self) -> None:
        self.reset_called = False
        self.reset_chat_called = False

    def reset_state(self) -> None:
        self.reset_called = True

    def reset_chat_state(self) -> None:
        self.reset_chat_called = True


def test_reset_memory_calls_adapter_and_returns_status() -> None:
    fake_adapter = FakeMemoryAdminAdapter()
    service = memory_admin_service.MemoryAdminService(memory_admin=fake_adapter)

    response = service.reset_memory()

    assert fake_adapter.reset_called
    assert response.status == "reset"


def test_reset_chat_memory_calls_adapter_and_returns_status() -> None:
    fake_adapter = FakeMemoryAdminAdapter()
    service = memory_admin_service.MemoryAdminService(memory_admin=fake_adapter)

    response = service.reset_chat_memory()

    assert fake_adapter.reset_chat_called
    assert response.status == "chat_reset"
