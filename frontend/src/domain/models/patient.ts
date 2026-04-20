export interface Patient {
  tenantId: string;
  whatsappUserId: string;
  firstName: string;
  lastName: string;
  email: string;
  age: number;
  location: string;
  phonePrefix: string | null;
  phone: string;
  createdAt: string;
}

export interface CreatePatientInput {
  whatsappUserId: string;
  firstName: string;
  lastName: string;
  email: string;
  age: number;
  location: string;
  phonePrefix: string | null;
  phone: string;
}

export interface UpdatePatientInput {
  firstName: string;
  lastName: string;
  email: string;
  age: number;
  location: string;
  phonePrefix: string | null;
  phone: string;
}
