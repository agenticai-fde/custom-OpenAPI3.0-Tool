"""
Clinic Appointment API - a teaching example of an OpenAPI 3.0 spec built with FastAPI.

All doctors, patients and appointments below are FAKE sample data kept in memory.
Restarting the server resets everything.
"""
import os
import datetime
from enum import Enum

from fastapi import FastAPI, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, Field

# Set PUBLIC_URL to your ngrok URL so external tools (e.g. Microsoft Foundry) call the right server.
PUBLIC_URL = os.getenv("PUBLIC_URL", "http://127.0.0.1:8000")

tags_metadata = [
    {"name": "Doctors", "description": "Browse doctors and their free appointment slots."},
    {"name": "Patients", "description": "Look up patient records (sample data only)."},
    {"name": "Appointments", "description": "Book, view and cancel appointments."},
]

app = FastAPI(
    title="Clinic Appointment API",
    version="1.0.0",
    description=(
        "A demo API for a small clinic. Find a doctor, check free slots, "
        "and book or cancel appointments for a patient.\n\n"
        "**All data is fictional and resets when the server restarts.**"
    ),
    openapi_tags=tags_metadata,
    servers=[{"url": PUBLIC_URL, "description": "Clinic API server"}],
)
# FastAPI emits OpenAPI 3.1 by default; Microsoft Foundry's OpenAPI tool expects 3.0.
app.openapi_version = "3.0.3"


# ---------------------------------------------------------------------------
# Schemas (these become "components/schemas" in the OpenAPI document)
# ---------------------------------------------------------------------------

class Specialty(str, Enum):
    general = "general"
    cardiology = "cardiology"
    dermatology = "dermatology"
    pediatrics = "pediatrics"


class AppointmentStatus(str, Enum):
    booked = "booked"
    cancelled = "cancelled"


class Doctor(BaseModel):
    id: str = Field(description="Unique doctor ID.")
    name: str = Field(description="Doctor's full name.")
    specialty: Specialty
    working_days: list[str] = Field(description="Days of the week the doctor sees patients.")

    model_config = ConfigDict(json_schema_extra={"example": {
        "id": "D001", "name": "Dr. Asha Rao", "specialty": "cardiology",
        "working_days": ["Monday", "Wednesday", "Friday"],
    }})


class Patient(BaseModel):
    id: str = Field(description="Unique patient ID.")
    name: str
    age: int = Field(ge=0, le=130)
    allergies: list[str] = Field(description="Known allergies. Empty list if none.")

    model_config = ConfigDict(json_schema_extra={"example": {
        "id": "P100", "name": "Ravi Kumar", "age": 42, "allergies": ["penicillin"],
    }})


class AvailableSlots(BaseModel):
    doctor_id: str
    date: datetime.date
    slots: list[str] = Field(description="Free start times in 24-hour HH:MM format.")

    model_config = ConfigDict(json_schema_extra={"example": {
        "doctor_id": "D001", "date": "2026-10-19", "slots": ["09:00", "09:30", "11:00"],
    }})


class AppointmentRequest(BaseModel):
    patient_id: str = Field(description="ID of the patient, e.g. P100.")
    doctor_id: str = Field(description="ID of the doctor, e.g. D001.")
    date: datetime.date = Field(description="Appointment date (YYYY-MM-DD).")
    time: str = Field(pattern=r"^\d{2}:\d{2}$", description="Start time in HH:MM, must be a free slot.")
    reason: str = Field(min_length=3, max_length=200, description="Short reason for the visit.")

    model_config = ConfigDict(json_schema_extra={"example": {
        "patient_id": "P100", "doctor_id": "D001", "date": "2026-10-19",
        "time": "09:30", "reason": "Chest pain follow-up",
    }})


class Appointment(AppointmentRequest):
    id: str = Field(description="Unique appointment ID.")
    status: AppointmentStatus

    model_config = ConfigDict(json_schema_extra={"example": {
        "id": "A1", "patient_id": "P100", "doctor_id": "D001", "date": "2026-10-19",
        "time": "09:30", "reason": "Chest pain follow-up", "status": "booked",
    }})


class ErrorResponse(BaseModel):
    detail: str = Field(description="Human-readable error message.")

    model_config = ConfigDict(json_schema_extra={"example": {"detail": "Doctor D999 not found"}})


# ---------------------------------------------------------------------------
# Fake in-memory data
# ---------------------------------------------------------------------------

DOCTORS = {
    "D001": Doctor(id="D001", name="Dr. Asha Rao", specialty=Specialty.cardiology,
                   working_days=["Monday", "Wednesday", "Friday"]),
    "D002": Doctor(id="D002", name="Dr. Vikram Mehta", specialty=Specialty.general,
                   working_days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]),
    "D003": Doctor(id="D003", name="Dr. Neha Iyer", specialty=Specialty.dermatology,
                   working_days=["Tuesday", "Thursday"]),
    "D004": Doctor(id="D004", name="Dr. Arjun Das", specialty=Specialty.pediatrics,
                   working_days=["Monday", "Thursday", "Saturday"]),
}

PATIENTS = {
    "P100": Patient(id="P100", name="Ravi Kumar", age=42, allergies=["penicillin"]),
    "P101": Patient(id="P101", name="Priya Sharma", age=29, allergies=[]),
    "P102": Patient(id="P102", name="Aarav Singh", age=7, allergies=["peanuts"]),
}

APPOINTMENTS: dict[str, Appointment] = {}

DAILY_SLOTS = ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
               "14:00", "14:30", "15:00", "15:30"]

NOT_FOUND = {404: {"model": ErrorResponse, "description": "Resource not found"}}


def get_doctor_or_404(doctor_id: str) -> Doctor:
    if doctor_id not in DOCTORS:
        raise HTTPException(status_code=404, detail=f"Doctor {doctor_id} not found")
    return DOCTORS[doctor_id]


def get_patient_or_404(patient_id: str) -> Patient:
    if patient_id not in PATIENTS:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
    return PATIENTS[patient_id]


def free_slots(doctor: Doctor, day: datetime.date) -> list[str]:
    if day.strftime("%A") not in doctor.working_days:
        return []
    taken = {a.time for a in APPOINTMENTS.values()
             if a.doctor_id == doctor.id and a.date == day and a.status == AppointmentStatus.booked}
    return [s for s in DAILY_SLOTS if s not in taken]


# ---------------------------------------------------------------------------
# Endpoints (these become "paths" in the OpenAPI document)
# ---------------------------------------------------------------------------

@app.get("/doctors", tags=["Doctors"], operation_id="listDoctors",
         summary="List doctors", response_model=list[Doctor])
def list_doctors(
    specialty: Specialty = Query(Specialty.general, description="Only return doctors with this specialty."),
):
    """Returns doctors for the given specialty (defaults to general medicine)."""
    return [d for d in DOCTORS.values() if d.specialty == specialty]


@app.get("/doctors/{doctor_id}/slots", tags=["Doctors"], operation_id="getAvailableSlots",
         summary="Get free slots for a doctor", response_model=AvailableSlots, responses=NOT_FOUND)
def get_available_slots(
    doctor_id: str = Path(description="Doctor ID, e.g. D001."),
    date: datetime.date = Query(description="Date to check (YYYY-MM-DD)."),
):
    """Returns the free 30-minute slots for a doctor on a date. Empty list if the doctor doesn't work that day."""
    doctor = get_doctor_or_404(doctor_id)
    return AvailableSlots(doctor_id=doctor_id, date=date, slots=free_slots(doctor, date))


@app.get("/patients/{patient_id}", tags=["Patients"], operation_id="getPatient",
         summary="Get a patient", response_model=Patient, responses=NOT_FOUND)
def get_patient(patient_id: str = Path(description="Patient ID, e.g. P100.")):
    """Returns basic patient details, including known allergies."""
    return get_patient_or_404(patient_id)


@app.get("/patients/{patient_id}/appointments", tags=["Patients"], operation_id="listPatientAppointments",
         summary="List a patient's appointments", response_model=list[Appointment], responses=NOT_FOUND)
def list_patient_appointments(patient_id: str = Path(description="Patient ID, e.g. P100.")):
    """Returns all appointments (booked and cancelled) for a patient."""
    get_patient_or_404(patient_id)
    return [a for a in APPOINTMENTS.values() if a.patient_id == patient_id]


@app.post("/appointments", tags=["Appointments"], operation_id="bookAppointment",
          summary="Book an appointment", status_code=201, response_model=Appointment,
          responses={**NOT_FOUND, 409: {"model": ErrorResponse, "description": "Slot is not available"}})
def book_appointment(request: AppointmentRequest):
    """Books a slot for a patient. Call getAvailableSlots first to find a free time."""
    get_patient_or_404(request.patient_id)
    doctor = get_doctor_or_404(request.doctor_id)
    if request.time not in free_slots(doctor, request.date):
        raise HTTPException(status_code=409,
                            detail=f"{request.time} on {request.date} is not available for {doctor.name}")
    appointment = Appointment(id=f"A{len(APPOINTMENTS) + 1}", status=AppointmentStatus.booked,
                              **request.model_dump())
    APPOINTMENTS[appointment.id] = appointment
    return appointment


@app.get("/appointments/{appointment_id}", tags=["Appointments"], operation_id="getAppointment",
         summary="Get an appointment", response_model=Appointment, responses=NOT_FOUND)
def get_appointment(appointment_id: str = Path(description="Appointment ID, e.g. A1.")):
    if appointment_id not in APPOINTMENTS:
        raise HTTPException(status_code=404, detail=f"Appointment {appointment_id} not found")
    return APPOINTMENTS[appointment_id]


@app.delete("/appointments/{appointment_id}", tags=["Appointments"], operation_id="cancelAppointment",
            summary="Cancel an appointment", response_model=Appointment, responses=NOT_FOUND)
def cancel_appointment(appointment_id: str = Path(description="Appointment ID, e.g. A1.")):
    """Marks the appointment as cancelled and frees the slot."""
    appointment = get_appointment(appointment_id)
    appointment.status = AppointmentStatus.cancelled
    return appointment


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
