import type * as backendApiPort from "@ports/backend_api_port";

export class BlacklistUseCase {
  private readonly api: backendApiPort.BackendApiPort;

  constructor(api: backendApiPort.BackendApiPort) {
    this.api = api;
  }

  async list() {
    return this.api.listBlacklist();
  }

  async add(whatsappUserId: string) {
    return this.api.addBlacklist(whatsappUserId);
  }

  async remove(whatsappUserId: string) {
    await this.api.removeBlacklist(whatsappUserId);
  }
}
