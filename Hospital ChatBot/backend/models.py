from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Numeric,
    DateTime,
    ForeignKey,
    Text,
)

from sqlalchemy.orm import declarative_base


Base = declarative_base()


class Doctor(Base):

    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True)

    name = Column(String)
    specialty = Column(String)
    department = Column(String)

    qualification = Column(String)

    experience_years = Column(Integer)

    consultation_fee = Column(Numeric)

    active = Column(Boolean)


class Patient(Base):

    __tablename__ = "patients"

    id = Column(Integer, primary_key=True)

    name = Column(String)

    phone = Column(String, unique=True)

    email = Column(String)


class AppointmentSlot(Base):

    __tablename__ = "appointment_slots"

    id = Column(Integer, primary_key=True)

    doctor_id = Column(
        Integer,
        ForeignKey("doctors.id")
    )

    start_time = Column(DateTime)

    end_time = Column(DateTime)

    status = Column(String)


class Appointment(Base):

    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True)

    patient_id = Column(
        Integer,
        ForeignKey("patients.id")
    )

    doctor_id = Column(
        Integer,
        ForeignKey("doctors.id")
    )

    slot_id = Column(
        Integer,
        ForeignKey("appointment_slots.id")
    )

    status = Column(String)

    booked_at = Column(DateTime)


class InsurancePlan(Base):

    __tablename__ = "insurance_plans"

    id = Column(Integer, primary_key=True)

    provider_name = Column(String)

    plan_name = Column(String)

    active = Column(Boolean)


class InsuranceCoverage(Base):

    __tablename__ = "insurance_coverage"

    id = Column(Integer, primary_key=True)

    insurance_plan_id = Column(
        Integer,
        ForeignKey("insurance_plans.id")
    )

    department = Column(String)

    specialty = Column(String)

    covered = Column(Boolean)

    copay = Column(Numeric)

    notes = Column(Text)
