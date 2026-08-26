from datetime import datetime

from sqlalchemy import text


def get_available_slots(
    db,
    doctor_id: int,
    date: str
):

    result = db.execute(
        text("""
            SELECT
                s.id AS slot_id,
                d.id AS doctor_id,
                d.name AS doctor_name,
                d.specialty,
                s.start_time,
                s.end_time
            FROM appointment_slots s

            JOIN doctors d
                ON d.id = s.doctor_id

            WHERE s.doctor_id = :doctor_id

            AND DATE(s.start_time) = :date

            AND s.status = 'AVAILABLE'

            ORDER BY s.start_time
        """),
        {
            "doctor_id": doctor_id,
            "date": date
        }
    )

    return [
        dict(row._mapping)
        for row in result
    ]


def find_slot(
    db,
    doctor_id: int,
    date: str,
    time: str
):

    result = db.execute(
        text("""
            SELECT
                s.id AS slot_id,
                s.doctor_id,
                s.start_time,
                s.end_time,
                d.name AS doctor_name,
                d.specialty
            FROM appointment_slots s

            JOIN doctors d
                ON d.id = s.doctor_id

            WHERE s.doctor_id = :doctor_id

            AND DATE(s.start_time) = :date

            AND TO_CHAR(
                s.start_time,
                'HH24:MI'
            ) = :time

            LIMIT 1
        """),
        {
            "doctor_id": doctor_id,
            "date": date,
            "time": time
        }
    )

    row = result.fetchone()

    if not row:
        return None

    return dict(row._mapping)


def get_appointment(
    db,
    appointment_id: int
):

    result = db.execute(
        text("""
            SELECT
                a.id AS appointment_id,
                a.status,
                a.booked_at,

                p.name AS patient_name,
                p.phone,

                d.name AS doctor_name,
                d.specialty,

                s.start_time,
                s.end_time

            FROM appointments a

            JOIN patients p
                ON p.id = a.patient_id

            JOIN doctors d
                ON d.id = a.doctor_id

            JOIN appointment_slots s
                ON s.id = a.slot_id

            WHERE a.id = :appointment_id
        """),
        {
            "appointment_id": appointment_id
        }
    )

    row = result.fetchone()

    if not row:
        return None

    return dict(row._mapping)


def book_appointment(
    db,
    patient_name: str,
    phone: str,
    doctor_id: int,
    slot_id: int
):

    try:

        # IMPORTANT:
        # Start transaction.
        with db.begin():

            # Lock the exact slot.
            slot = db.execute(
                text("""
                    SELECT
                        id,
                        doctor_id,
                        start_time,
                        end_time,
                        status

                    FROM appointment_slots

                    WHERE id = :slot_id

                    FOR UPDATE
                """),
                {
                    "slot_id": slot_id
                }
            ).fetchone()

            if not slot:

                return {
                    "success": False,
                    "message": "Appointment slot does not exist."
                }

            # This is the critical check.
            if slot.status != "AVAILABLE":

                return {
                    "success": False,
                    "message": (
                        "Sorry, this appointment slot "
                        "is no longer available."
                    )
                }

            # Check doctor.
            if slot.doctor_id != doctor_id:

                return {
                    "success": False,
                    "message": (
                        "The selected doctor does not "
                        "match this appointment slot."
                    )
                }

            # Find existing patient.
            patient = db.execute(
                text("""
                    SELECT id
                    FROM patients
                    WHERE phone = :phone
                """),
                {
                    "phone": phone
                }
            ).fetchone()

            if patient:

                patient_id = patient.id

                db.execute(
                    text("""
                        UPDATE patients
                        SET name = :name
                        WHERE id = :patient_id
                    """),
                    {
                        "name": patient_name,
                        "patient_id": patient_id
                    }
                )

            else:

                result = db.execute(
                    text("""
                        INSERT INTO patients
                        (name, phone)
                        VALUES
                        (:name, :phone)
                        RETURNING id
                    """),
                    {
                        "name": patient_name,
                        "phone": phone
                    }
                )

                patient_id = result.fetchone().id

            # Mark slot BOOKED.
            db.execute(
                text("""
                    UPDATE appointment_slots
                    SET status = 'BOOKED'
                    WHERE id = :slot_id
                """),
                {
                    "slot_id": slot_id
                }
            )

            # Create appointment.
            result = db.execute(
                text("""
                    INSERT INTO appointments
                    (
                        patient_id,
                        doctor_id,
                        slot_id,
                        status
                    )
                    VALUES
                    (
                        :patient_id,
                        :doctor_id,
                        :slot_id,
                        'CONFIRMED'
                    )
                    RETURNING id
                """),
                {
                    "patient_id": patient_id,
                    "doctor_id": doctor_id,
                    "slot_id": slot_id
                }
            )

            appointment_id = result.fetchone().id

        return {
            "success": True,
            "appointment_id": appointment_id,
            "start_time": slot.start_time,
            "end_time": slot.end_time
        }

    except Exception:

        db.rollback()

        raise


def cancel_appointment(
    db,
    appointment_id: int,
    phone: str
):

    try:

        with db.begin():

            appointment = db.execute(
                text("""
                    SELECT
                        a.id,
                        a.slot_id,
                        a.status

                    FROM appointments a

                    JOIN patients p
                        ON p.id = a.patient_id

                    WHERE a.id = :appointment_id
                    AND p.phone = :phone

                    FOR UPDATE
                """),
                {
                    "appointment_id": appointment_id,
                    "phone": phone
                }
            ).fetchone()

            if not appointment:

                return {
                    "success": False,
                    "message": (
                        "Appointment not found."
                    )
                }

            if appointment.status != "CONFIRMED":

                return {
                    "success": False,
                    "message": (
                        "This appointment cannot be cancelled."
                    )
                }

            db.execute(
                text("""
                    UPDATE appointments
                    SET status = 'CANCELLED'
                    WHERE id = :appointment_id
                """),
                {
                    "appointment_id": appointment_id
                }
            )

            db.execute(
                text("""
                    UPDATE appointment_slots
                    SET status = 'AVAILABLE'
                    WHERE id = :slot_id
                """),
                {
                    "slot_id": appointment.slot_id
                }
            )

        return {
            "success": True,
            "message": "Appointment cancelled successfully."
        }

    except Exception:

        db.rollback()

        raise
