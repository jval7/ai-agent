import src.ports.memory_admin_port as memory_admin_port
import src.services.use_cases.memory_admin_service as memory_admin_service


class FakeMemoryAdminAdapter(memory_admin_port.MemoryAdminPort):
    def __init__(self) -> None:
        self.reset_called = False

    def reset_state(self) -> None:
        self.reset_called = True


def test_reset_memory_calls_adapter_and_returns_status() -> None:
    fake_adapter = FakeMemoryAdminAdapter()
    service = memory_admin_service.MemoryAdminService(memory_admin=fake_adapter)

    response = service.reset_memory()

    assert fake_adapter.reset_called
    assert response.status == "reset"
