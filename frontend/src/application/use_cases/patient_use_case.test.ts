import * as vitestModule from "vitest";

import type * as backendApiPort from "@ports/backend_api_port";

import * as patientUseCaseModule from "./patient_use_case";

vitestModule.describe("PatientUseCase", () => {
  vitestModule.it("delegates patient operations to api port", async () => {
    const getPatientMock = vitestModule.vi.fn(async () => ({
      tenantId: "tenant-1",
      whatsappUserId: "wa-1",
      firstName: "Jane",
      lastName: "Doe",
      email: "jane@example.com",
      age: 29,
      consultationReason: "Ansiedad",
      location: "Bogota",
      phone: "573001112233",
      createdAt: "2026-03-01T10:00:00Z"
    }));
    const apiMock = {
      listPatients: vitestModule.vi.fn(async () => [
        {
          tenantId: "tenant-1",
          whatsappUserId: "wa-1",
          firstName: "Jane",
          lastName: "Doe",
          email: "jane@example.com",
          age: 29,
          consultationReason: "Ansiedad",
          location: "Bogota",
          phone: "573001112233",
          createdAt: "2026-03-01T10:00:00Z"
        }
      ]),
      getPatient: getPatientMock
    } as Partial<backendApiPort.BackendApiPort> as backendApiPort.BackendApiPort;

    const useCase = new patientUseCaseModule.PatientUseCase(apiMock);
    const patients = await useCase.listPatients();
    const patient = await useCase.getPatient("wa-1");

    vitestModule.expect(patients[0]?.whatsappUserId).toBe("wa-1");
    vitestModule.expect(patient.firstName).toBe("Jane");
    vitestModule.expect(getPatientMock).toHaveBeenCalledWith("wa-1");
  });
});
