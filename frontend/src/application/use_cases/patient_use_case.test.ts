import * as vitestModule from "vitest";

import type * as backendApiPort from "@ports/backend_api_port";

import * as patientUseCaseModule from "./patient_use_case";

vitestModule.describe("PatientUseCase", () => {
  vitestModule.it("delegates patient operations to api port", async () => {
    const removePatientMock = vitestModule.vi.fn(async () => Promise.resolve());
    const createPatientMock = vitestModule.vi.fn(async () => ({
      tenantId: "tenant-1",
      whatsappUserId: "wa-2",
      firstName: "John",
      lastName: "Smith",
      email: "john@example.com",
      age: 34,
      consultationReason: "Insomnio",
      location: "Medellin",
      phone: "573001445566",
      createdAt: "2026-03-02T10:00:00Z"
    }));
    const updatePatientMock = vitestModule.vi.fn(async () => ({
      tenantId: "tenant-1",
      whatsappUserId: "wa-1",
      firstName: "Jane Updated",
      lastName: "Doe",
      email: "jane-updated@example.com",
      age: 30,
      consultationReason: "Ansiedad",
      location: "Bogota",
      phone: "573001112233",
      createdAt: "2026-03-01T10:00:00Z"
    }));
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
      getPatient: getPatientMock,
      removePatient: removePatientMock,
      createPatient: createPatientMock,
      updatePatient: updatePatientMock
    } as Partial<backendApiPort.BackendApiPort> as backendApiPort.BackendApiPort;

    const useCase = new patientUseCaseModule.PatientUseCase(apiMock);
    const patients = await useCase.listPatients();
    const patient = await useCase.getPatient("wa-1");
    await useCase.createPatient({
      whatsappUserId: "wa-2",
      firstName: "John",
      lastName: "Smith",
      email: "john@example.com",
      age: 34,
      consultationReason: "Insomnio",
      location: "Medellin",
      phone: "573001445566"
    });
    await useCase.updatePatient("wa-1", {
      firstName: "Jane Updated",
      lastName: "Doe",
      email: "jane-updated@example.com",
      age: 30,
      consultationReason: "Ansiedad",
      location: "Bogota",
      phone: "573001112233"
    });
    await useCase.removePatient("wa-1");

    vitestModule.expect(patients[0]?.whatsappUserId).toBe("wa-1");
    vitestModule.expect(patient.firstName).toBe("Jane");
    vitestModule.expect(getPatientMock).toHaveBeenCalledWith("wa-1");
    vitestModule.expect(createPatientMock).toHaveBeenCalledTimes(1);
    vitestModule.expect(updatePatientMock).toHaveBeenCalledWith("wa-1", {
      firstName: "Jane Updated",
      lastName: "Doe",
      email: "jane-updated@example.com",
      age: 30,
      consultationReason: "Ansiedad",
      location: "Bogota",
      phone: "573001112233"
    });
    vitestModule.expect(removePatientMock).toHaveBeenCalledWith("wa-1");
  });
});
