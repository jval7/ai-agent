import type * as evaluationModel from "@domain/models/evaluation";
import type * as backendApiPort from "@ports/backend_api_port";

export class EvaluationUseCase {
  private readonly api: backendApiPort.BackendApiPort;

  constructor(api: backendApiPort.BackendApiPort) {
    this.api = api;
  }

  async listShapes(): Promise<evaluationModel.EvalShape[]> {
    return this.api.listEvalShapes();
  }

  async listPersonas(): Promise<evaluationModel.EvalPersona[]> {
    return this.api.listEvalPersonas();
  }

  async listPromptVersions(): Promise<evaluationModel.EvalPromptVersion[]> {
    return this.api.listEvalPromptVersions();
  }

  async listRuns(limit?: number): Promise<evaluationModel.EvalRunListItem[]> {
    return this.api.listEvalRuns(limit);
  }

  async getRun(runDocId: string): Promise<evaluationModel.EvalRunDetail> {
    return this.api.getEvalRun(runDocId);
  }

  async deleteRun(runId: string, adminSecret: string): Promise<evaluationModel.EvalDeleteResult> {
    return this.api.deleteEvalRun(runId, adminSecret);
  }

  async listCapabilities(): Promise<evaluationModel.EvalCapabilityDoc[]> {
    return this.api.listEvalCapabilities();
  }
}
