import src.ports.memory_admin_port as memory_admin_port
import src.services.dto.dev_dto as dev_dto


class MemoryAdminService:
    def __init__(self, memory_admin: memory_admin_port.MemoryAdminPort) -> None:
        self._memory_admin = memory_admin

    def reset_memory(self) -> dev_dto.MemoryResetResponseDTO:
        self._memory_admin.reset_state()
        return dev_dto.MemoryResetResponseDTO(status="reset")
