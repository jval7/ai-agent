import datetime

import pydantic


class PatientDTO(pydantic.BaseModel):
    tenant_id: str
    whatsapp_user_id: str
    first_name: str
    last_name: str
    email: str
    age: int
    consultation_reason: str
    location: str
    phone: str
    created_at: datetime.datetime


class PatientListResponseDTO(pydantic.BaseModel):
    items: list[PatientDTO]


class CreatePatientDTO(pydantic.BaseModel):
    whatsapp_user_id: str
    first_name: str
    last_name: str
    email: str
    age: int
    consultation_reason: str
    location: str
    phone: str


class UpdatePatientDTO(pydantic.BaseModel):
    first_name: str
    last_name: str
    email: str
    age: int
    consultation_reason: str
    location: str
    phone: str
