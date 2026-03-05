export interface Patient {
  tenantId: string;
  whatsappUserId: string;
  firstName: string;
  lastName: string;
  email: string;
  age: number;
  consultationReason: string;
  location: string;
  phone: string;
  createdAt: string;
}

export interface CreatePatientInput {
  whatsappUserId: string;
  firstName: string;
  lastName: string;
  email: string;
  age: number;
  consultationReason: string;
  location: string;
  phone: string;
}

export interface UpdatePatientInput {
  firstName: string;
  lastName: string;
  email: string;
  age: number;
  consultationReason: string;
  location: string;
  phone: string;
}
