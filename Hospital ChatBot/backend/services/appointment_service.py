from sqlalchemy import text


# =========================================================
# GET AVAILABLE SLOTS
# =========================================================

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


# =========================================================
# GET SLOT BY ID
# =========================================================

def get_slot_by_id(
    db,
    slot_id: int
):

    result = db.execute(
        text("""
            SELECT
                s.id AS slot_id,
                s.doctor_id,
                s.start_time,
                s.end_time,
                s.status,
                d.name AS doctor_name,
                d.specialty

            FROM appointment_slots s

            JOIN doctors d
                ON d.id = s.doctor_id

            WHERE s.id = :slot_id

            LIMIT 1
        """),
        {
            "slot_id": slot_id
        }
    )

    row = result.fetchone()

    if not row:
        return None

    return dict(row._mapping)


# =========================================================
# FIND SLOT BY DOCTOR + DATE + TIME
# =========================================================

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
                s.status,
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

            AND s.status = 'AVAILABLE'

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


# =========================================================
# GET APPOINTMENT
# =========================================================

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


# =========================================================
# BOOK APPOINTMENT
# =========================================================

def book_appointment(
    db,
    patient_name: str,
    phone: str,
    doctor_id: int,
    slot_id: int
):

    try:

        # -------------------------------------------------
        # 1. Lock and fetch the slot
        # -------------------------------------------------

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

            db.rollback()

            return {
                "success": False,
                "message": (
                    "Appointment slot does not exist."
                )
            }

        # -------------------------------------------------
        # 2. Check availability
        # -------------------------------------------------

        if slot.status != "AVAILABLE":

            db.rollback()

            return {
                "success": False,
                "message": (
                    "Sorry, this appointment slot "
                    "is no longer available."
                )
            }

        # -------------------------------------------------
        # 3. Verify doctor
        # -------------------------------------------------

        if slot.doctor_id != doctor_id:

            db.rollback()

            return {
                "success": False,
                "message": (
                    "The selected doctor does not "
                    "match this appointment slot."
                )
            }

        # -------------------------------------------------
        # 4. Find existing patient
        # -------------------------------------------------

        patient = db.execute(
            text("""
                SELECT
                    id

                FROM patients

                WHERE phone = :phone
            """),
            {
                "phone": phone
            }
        ).fetchone()

        if patient:

            patient_id = patient.id

            # Update patient's name.
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
                    (
                        name,
                        phone
                    )

                    VALUES
                    (
                        :name,
                        :phone
                    )

                    RETURNING id
                """),
                {
                    "name": patient_name,
                    "phone": phone
                }
            )

            patient_id = result.fetchone().id

        # -------------------------------------------------
        # 5. Mark slot as BOOKED
        # -------------------------------------------------

        update_result = db.execute(
            text("""
                UPDATE appointment_slots

                SET status = 'BOOKED'

                WHERE id = :slot_id

                AND status = 'AVAILABLE'
            """),
            {
                "slot_id": slot_id
            }
        )

        if update_result.rowcount == 0:

            db.rollback()

            return {
                "success": False,
                "message": (
                    "Sorry, this appointment slot "
                    "is no longer available."
                )
            }

        # -------------------------------------------------
        # 6. Create appointment
        # -------------------------------------------------

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

        # -------------------------------------------------
        # 7. Commit
        # -------------------------------------------------

        db.commit()

        return {
            "success": True,
            "appointment_id": appointment_id,
            "start_time": slot.start_time,
            "end_time": slot.end_time
        }

    except Exception:

        db.rollback()

        raise


# =========================================================
# CANCEL APPOINTMENT
# =========================================================

def cancel_appointment(
    db,
    appointment_id: int,
    phone: str
):

    try:

        # -------------------------------------------------
        # 1. Find and lock the appointment
        # -------------------------------------------------

        appointment = db.execute(
            text("""
                SELECT
                    a.id,
                    a.slot_id,
                    a.doctor_id,
                    a.status,

                    p.name AS patient_name,
                    p.phone

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

            db.rollback()

            return {
                "success": False,
                "message": (
                    "Appointment not found."
                )
            }

        # -------------------------------------------------
        # 2. Check appointment status
        # -------------------------------------------------

        if appointment.status != "CONFIRMED":

            db.rollback()

            return {
                "success": False,
                "message": (
                    "This appointment cannot be "
                    "cancelled because it is already "
                    f"{appointment.status}."
                )
            }

        # -------------------------------------------------
        # 3. Lock the appointment slot
        # -------------------------------------------------

        slot = db.execute(
            text("""
                SELECT
                    id,
                    doctor_id,
                    status,
                    start_time,
                    end_time

                FROM appointment_slots

                WHERE id = :slot_id

                FOR UPDATE
            """),
            {
                "slot_id": appointment.slot_id
            }
        ).fetchone()

        if not slot:

            db.rollback()

            return {
                "success": False,
                "message": (
                    "The appointment slot associated "
                    "with this appointment could not "
                    "be found."
                )
            }

        # -------------------------------------------------
        # 4. Cancel appointment
        # -------------------------------------------------

        update_appointment = db.execute(
            text("""
                UPDATE appointments

                SET status = 'CANCELLED'

                WHERE id = :appointment_id

                AND status = 'CONFIRMED'
            """),
            {
                "appointment_id": appointment_id
            }
        )

        if update_appointment.rowcount == 0:

            db.rollback()

            return {
                "success": False,
                "message": (
                    "The appointment could not be "
                    "cancelled."
                )
            }

        # -------------------------------------------------
        # 5. RELEASE THE SLOT
        #
        # This is the important fix.
        # -------------------------------------------------

        update_slot = db.execute(
            text("""
                UPDATE appointment_slots

                SET status = 'AVAILABLE'

                WHERE id = :slot_id
            """),
            {
                "slot_id": appointment.slot_id
            }
        )

        if update_slot.rowcount == 0:

            db.rollback()

            return {
                "success": False,
                "message": (
                    "The appointment was not cancelled "
                    "because its slot could not be "
                    "released."
                )
            }

        # -------------------------------------------------
        # 6. Commit both changes together
        # -------------------------------------------------

        db.commit()

        # -------------------------------------------------
        # 7. Verify slot status after commit
        # -------------------------------------------------

        verification = db.execute(
            text("""
                SELECT
                    status

                FROM appointment_slots

                WHERE id = :slot_id
            """),
            {
                "slot_id": appointment.slot_id
            }
        ).fetchone()

        if not verification:

            return {
                "success": False,
                "message": (
                    "Appointment was cancelled, but "
                    "the slot could not be verified."
                )
            }

        if verification.status != "AVAILABLE":

            return {
                "success": False,
                "message": (
                    "Appointment was cancelled, but "
                    "the appointment slot was not "
                    "released."
                )
            }

        return {
            "success": True,
            "message": (
                "Appointment cancelled successfully."
            ),
            "appointment_id": appointment_id,
            "slot_id": appointment.slot_id
        }

    except Exception:

        db.rollback()

        raise