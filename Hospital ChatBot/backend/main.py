import re

from fastapi import (
    FastAPI,
    Depends,
    HTTPException
)

from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.database import get_db

from backend.schemas.chat import (
    ChatRequest,
    ChatResponse
)

from backend.services.guardrails import (
    input_guardrail,
    output_guardrail
)

from backend.services.gemini import (
    classify_intent,
    generate_response
)

from backend.services.retrieval import (
    retrieve_documents
)

from backend.services.doctor_service import (
    get_all_doctors,
    find_doctors_by_specialty,
    find_doctor_by_name
)

from backend.services.appointment_service import (
    get_available_slots,
    get_slot_by_id,
    find_slot,
    book_appointment,
    get_appointment,
    cancel_appointment
)


app = FastAPI(
    title="ABC Hospital Chatbot API",
    version="1.0.0"
)


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():

    return {
        "hospital": "ABC Multispeciality Hospital",
        "service": "Hospital Chatbot API",
        "status": "running"
    }


# =========================================================
# DOCTORS
# =========================================================

@app.get("/doctors")
def doctors(
    db: Session = Depends(get_db)
):

    return {
        "doctors": get_all_doctors(db)
    }


# =========================================================
# DOCTOR SLOTS
# =========================================================

@app.get("/doctors/{doctor_id}/slots")
def doctor_slots(
    doctor_id: int,
    date: str,
    db: Session = Depends(get_db)
):

    return {
        "slots": get_available_slots(
            db,
            doctor_id,
            date
        )
    }


# =========================================================
# APPOINTMENT DETAILS
# =========================================================

@app.get("/appointments/{appointment_id}")
def appointment(
    appointment_id: int,
    db: Session = Depends(get_db)
):

    result = get_appointment(
        db,
        appointment_id
    )

    if not result:

        raise HTTPException(
            status_code=404,
            detail="Appointment not found."
        )

    return result


# =========================================================
# CANCEL APPOINTMENT API
# =========================================================

@app.post(
    "/appointments/{appointment_id}/cancel"
)
def cancel(
    appointment_id: int,
    phone: str,
    db: Session = Depends(get_db)
):

    result = cancel_appointment(
        db,
        appointment_id,
        phone
    )

    if not result["success"]:

        raise HTTPException(
            status_code=400,
            detail=result["message"]
        )

    return result


# =========================================================
# BLOCK SLOT
# =========================================================

@app.post(
    "/admin/slots/{slot_id}/block"
)
def block_slot(
    slot_id: int,
    db: Session = Depends(get_db)
):

    result = db.execute(
        text("""
            UPDATE appointment_slots

            SET status = 'BLOCKED'

            WHERE id = :slot_id

            AND status = 'AVAILABLE'
        """),
        {
            "slot_id": slot_id
        }
    )

    db.commit()

    if result.rowcount == 0:

        raise HTTPException(
            status_code=400,
            detail=(
                "Slot does not exist or "
                "is not currently available."
            )
        )

    return {
        "success": True,
        "message": "Slot blocked."
    }


# =========================================================
# UNBLOCK SLOT
# =========================================================

@app.post(
    "/admin/slots/{slot_id}/unblock"
)
def unblock_slot(
    slot_id: int,
    db: Session = Depends(get_db)
):

    result = db.execute(
        text("""
            UPDATE appointment_slots

            SET status = 'AVAILABLE'

            WHERE id = :slot_id

            AND status = 'BLOCKED'
        """),
        {
            "slot_id": slot_id
        }
    )

    db.commit()

    if result.rowcount == 0:

        raise HTTPException(
            status_code=400,
            detail=(
                "Slot does not exist or "
                "is not currently blocked."
            )
        )

    return {
        "success": True,
        "message": "Slot unblocked."
    }


# =========================================================
# HELPER:
# LAST ASSISTANT MESSAGE
# =========================================================

def get_last_assistant_message(
    history
):

    for message in reversed(history):

        if message.get(
            "role"
        ) == "assistant":

            return message.get(
                "content",
                ""
            )

    return ""


# =========================================================
# HELPER:
# REQUESTED SLOT ID
# =========================================================

def get_requested_slot_id(
    message: str
):

    matches = re.findall(
        r"\b(?:slot\s*(?:id)?\s*)?(\d+)\b",
        message.lower()
    )

    if not matches:

        return None

    return int(matches[0])


# =========================================================
# HELPER:
# OFFERED SLOT IDS
# =========================================================

def get_offered_slot_ids(
    history
):

    offered_slot_ids = set()

    for message in reversed(history):

        if message.get(
            "role"
        ) != "assistant":

            continue

        content = message.get(
            "content",
            ""
        )

        matches = re.findall(
            r"slot\s+ID\s+(\d+)",
            content,
            re.IGNORECASE
        )

        for value in matches:

            offered_slot_ids.add(
                int(value)
            )

        if (
            "available appointments"
            in content.lower()
        ):

            break

    return offered_slot_ids


# =========================================================
# HELPER:
# PREVIOUS SLOT SELECTION
# =========================================================

def get_previous_selected_slot_id(
    history
):

    for index in range(
        len(history) - 1,
        -1,
        -1
    ):

        message = history[index]

        if message.get(
            "role"
        ) != "user":

            continue

        content = (
            message.get(
                "content",
                ""
            )
            .strip()
        )

        if not content.isdigit():

            continue

        possible_slot_id = int(
            content
        )

        if index == 0:

            continue

        previous_message = history[
            index - 1
        ]

        if previous_message.get(
            "role"
        ) != "assistant":

            continue

        previous_content = previous_message.get(
            "content",
            ""
        )

        if re.search(
            rf"slot\s+ID\s+{possible_slot_id}\b",
            previous_content,
            re.IGNORECASE
        ):

            return possible_slot_id

    return None


# =========================================================
# HELPER:
# DETECT CANCELLATION FLOW
# =========================================================

def is_cancellation_flow(
    history
):

    last_assistant_message = (
        get_last_assistant_message(
            history
        )
    )

    message = (
        last_assistant_message.lower()
    )

    cancellation_phrases = [

        "cancel your appointment",

        "cancel the appointment",

        "cancel your booking",

        "cancel the booking",

        "appointment id or",

        "appointment id,",

        "phone number used when booking",

        "phone number used for the booking",

        "information so i can locate and cancel",

        "locate and cancel"
    ]

    return any(
        phrase in message
        for phrase in cancellation_phrases
    )


# =========================================================
# HELPER:
# EXTRACT APPOINTMENT ID
# =========================================================

def extract_appointment_id(
    message: str
):

    # Plain number:
    #
    # 2
    #
    cleaned = message.strip()

    if cleaned.isdigit():

        return int(cleaned)

    # Appointment ID 2
    match = re.search(
        r"appointment\s*(?:id|number)?\s*[:#-]?\s*(\d+)",
        message,
        re.IGNORECASE
    )

    if match:

        return int(
            match.group(1)
        )

    return None


# =========================================================
# HELPER:
# EXTRACT PHONE
# =========================================================

def extract_phone(
    message: str
):

    digits = "".join(
        character
        for character in message
        if character.isdigit()
    )

    if len(digits) >= 7:

        return digits

    return None


# =========================================================
# CHAT
# =========================================================

@app.post(
    "/chat",
    response_model=ChatResponse
)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db)
):

    # =====================================================
    # 1. INPUT GUARDRAIL
    # =====================================================

    allowed, refusal = input_guardrail(
        request.message
    )

    if not allowed:

        return ChatResponse(
            answer=refusal
        )

    # =====================================================
    # 2. HISTORY
    # =====================================================

    history_text = ""

    for message in request.history[-10:]:

        role = message.get(
            "role",
            "user"
        )

        content = message.get(
            "content",
            ""
        )

        history_text += (
            f"{role}: {content}\n"
        )

    # =====================================================
    # 3. CLASSIFY INTENT
    # =====================================================

    intent = classify_intent(
        request.message,
        history_text
    )

    # =====================================================
    # 3A. CANCELLATION FLOW OVERRIDE
    #
    # This MUST happen before slot selection.
    # =====================================================

    cancellation_flow = (
        is_cancellation_flow(
            request.history
        )
    )

    if cancellation_flow:

        intent.intent = (
            "cancel_appointment"
        )

        # -----------------------------------------------
        # If user gives appointment ID.
        # -----------------------------------------------

        appointment_id = (
            extract_appointment_id(
                request.message
            )
        )

        if appointment_id is not None:

            intent.appointment_id = (
                appointment_id
            )

        # -----------------------------------------------
        # If user gives phone number.
        # -----------------------------------------------

        else:

            phone = extract_phone(
                request.message
            )

            if phone:

                intent.phone = phone

    # =====================================================
    # 3B. SLOT SELECTION
    #
    # IMPORTANT:
    # Do NOT run this when cancellation flow is active.
    # =====================================================

    if not cancellation_flow:

        requested_slot_id = (
            get_requested_slot_id(
                request.message
            )
        )

        last_assistant_message = (
            get_last_assistant_message(
                request.history
            )
        )

        offered_slot_ids = (
            get_offered_slot_ids(
                request.history
            )
        )

        if (
            requested_slot_id is not None
            and (
                "slot ID"
                in last_assistant_message

                or "available appointments"
                in last_assistant_message.lower()
            )
        ):

            intent.intent = (
                "book_appointment"
            )

            intent.slot_id = (
                requested_slot_id
            )

            if (
                offered_slot_ids
                and requested_slot_id
                not in offered_slot_ids
            ):

                return ChatResponse(
                    answer=(
                        f"Slot {requested_slot_id} "
                        "is not one of the currently "
                        "available appointments. "
                        "Please choose one of the "
                        "slot IDs shown above."
                    )
                )

    # =====================================================
    # 3C. RECOVER PREVIOUS SLOT
    # =====================================================

    if (
        not cancellation_flow
        and intent.intent == "book_appointment"
        and intent.slot_id is None
    ):

        previous_slot_id = (
            get_previous_selected_slot_id(
                request.history
            )
        )

        if previous_slot_id is not None:

            intent.slot_id = (
                previous_slot_id
            )

    # =====================================================
    # 3D. PATIENT NAME
    # =====================================================

    last_assistant_message = (
        get_last_assistant_message(
            request.history
        )
    )

    if (
        not cancellation_flow
        and "patient's full name"
        in last_assistant_message.lower()
        and not intent.patient_name
    ):

        intent.patient_name = (
            request.message.strip()
        )

        intent.intent = (
            "book_appointment"
        )

    # =====================================================
    # 3E. PHONE DURING BOOKING
    # =====================================================

    if (
        not cancellation_flow
        and "phone number"
        in last_assistant_message.lower()
        and not intent.phone
    ):

        phone_digits = extract_phone(
            request.message
        )

        if phone_digits:

            intent.phone = (
                request.message.strip()
            )

            intent.intent = (
                "book_appointment"
            )

    # =====================================================
    # 3F. RESOLVE SELECTED SLOT
    # =====================================================

    if (
        not cancellation_flow
        and intent.intent == "book_appointment"
        and intent.slot_id is not None
    ):

        selected_slot = get_slot_by_id(
            db,
            intent.slot_id
        )

        if not selected_slot:

            return ChatResponse(
                answer=(
                    "I couldn't find the selected "
                    "appointment slot."
                )
            )

        if selected_slot["status"] != "AVAILABLE":

            return ChatResponse(
                answer=(
                    "Sorry, that appointment slot "
                    "is no longer available. Please "
                    "choose another available slot."
                )
            )

        if not intent.doctor_name:

            intent.doctor_name = (
                selected_slot["doctor_name"]
            )

        if not intent.date:

            intent.date = (
                selected_slot["start_time"]
                .strftime("%Y-%m-%d")
            )

        if not intent.time:

            intent.time = (
                selected_slot["start_time"]
                .strftime("%H:%M")
            )

    # =====================================================
    # 4. EMERGENCY
    # =====================================================

    if intent.intent == "emergency":

        return ChatResponse(
            answer=(
                "If you believe this is a medical "
                "emergency, please seek immediate "
                "emergency medical care or contact "
                "the hospital emergency department. "
                "I can also help you find the "
                "appropriate hospital department."
            )
        )

    # =====================================================
    # 5. OUT OF SCOPE
    # =====================================================

    if intent.intent == "other":

        return ChatResponse(
            answer=(
                "I can only answer questions related "
                "to ABC Multispeciality Hospital, "
                "such as doctors, appointments, "
                "hospital information, departments, "
                "and insurance. How can I help you?"
            )
        )

    # =====================================================
    # 6. MEDICAL GUIDANCE
    # =====================================================

    if intent.intent == "medical_guidance":

        return ChatResponse(
            answer=(
                "I can help you find the appropriate "
                "hospital department or doctor, but "
                "I cannot diagnose conditions or "
                "prescribe medication. Please tell "
                "me about the type of concern you "
                "would like help finding a specialist for."
            )
        )

    # =====================================================
    # 7. CANCEL APPOINTMENT
    # =====================================================

    if intent.intent == "cancel_appointment":

        # -------------------------------------------------
        # A. Get appointment ID from intent/message.
        # -------------------------------------------------

        appointment_id = (
            intent.appointment_id
        )

        if appointment_id is None:

            appointment_id = (
                extract_appointment_id(
                    request.message
                )
            )

        # -------------------------------------------------
        # B. If no appointment ID, try phone.
        # -------------------------------------------------

        phone = intent.phone

        if not phone:

            phone = extract_phone(
                request.message
            )

        # -------------------------------------------------
        # C. We need some identifier.
        # -------------------------------------------------

        if (
            appointment_id is None
            and not phone
        ):

            return ChatResponse(
                answer=(
                    "Please provide your appointment "
                    "ID or the phone number used when "
                    "booking the appointment so I can "
                    "locate and cancel it."
                )
            )

        # -------------------------------------------------
        # D. Cancellation by appointment ID.
        # -------------------------------------------------

        if appointment_id is not None:

            appointment = get_appointment(
                db,
                appointment_id
            )

            if not appointment:

                return ChatResponse(
                    answer=(
                        f"I couldn't find appointment "
                        f"{appointment_id} in the "
                        "hospital database."
                    )
                )

            # The get_appointment() query returns the
            # patient's phone number.

            appointment_phone = (
                appointment.get("phone")
            )

            if not appointment_phone:

                return ChatResponse(
                    answer=(
                        "I found the appointment, but "
                        "I couldn't verify the patient's "
                        "phone number. Please provide "
                        "the phone number used for booking."
                    )
                )

            result = cancel_appointment(
                db=db,
                appointment_id=appointment_id,
                phone=appointment_phone
            )

            if not result["success"]:

                return ChatResponse(
                    answer=result["message"]
                )

            # ---------------------------------------------
            # Use the appointment information that we
            # already retrieved before cancellation.
            # ---------------------------------------------

            doctor_name = (
                appointment["doctor_name"]
            )

            patient_name = (
                appointment["patient_name"]
            )

            start_time = (
                appointment["start_time"]
            )

            return ChatResponse(
                answer=(
                    f"Your appointment with "
                    f"{doctor_name} on "
                    f"{start_time.strftime('%Y-%m-%d')} "
                    f"at "
                    f"{start_time.strftime('%H:%M')} "
                    f"(Appointment ID: "
                    f"{appointment_id}) "
                    f"for {patient_name} has been "
                    "successfully cancelled.\n\n"
                    "The appointment slot is now "
                    "available again."
                )
            )

        # -------------------------------------------------
        # E. Cancellation by phone.
        # -------------------------------------------------

        result = db.execute(
            text("""
                SELECT
                    a.id AS appointment_id,
                    a.status,
                    a.slot_id,
                    a.doctor_id,

                    p.name AS patient_name,
                    p.phone,

                    d.name AS doctor_name,

                    s.start_time,
                    s.end_time

                FROM appointments a

                JOIN patients p
                    ON p.id = a.patient_id

                JOIN doctors d
                    ON d.id = a.doctor_id

                JOIN appointment_slots s
                    ON s.id = a.slot_id

                WHERE p.phone = :phone

                AND a.status = 'CONFIRMED'

                ORDER BY s.start_time ASC

                LIMIT 1
            """),
            {
                "phone": phone
            }
        )

        appointment = result.fetchone()

        if not appointment:

            return ChatResponse(
                answer=(
                    "I couldn't find a confirmed "
                    "appointment associated with that "
                    "phone number."
                )
            )

        cancel_result = cancel_appointment(
            db=db,
            appointment_id=appointment.appointment_id,
            phone=phone
        )

        if not cancel_result["success"]:

            return ChatResponse(
                answer=cancel_result["message"]
            )

        return ChatResponse(
            answer=(
                f"Your appointment with "
                f"{appointment.doctor_name} on "
                f"{appointment.start_time.strftime('%Y-%m-%d')} "
                f"at "
                f"{appointment.start_time.strftime('%H:%M')} "
                f"(Appointment ID: "
                f"{appointment.appointment_id}) "
                f"for {appointment.patient_name} "
                "has been successfully cancelled.\n\n"
                "The appointment slot is now "
                "available again."
            )
        )

    # =====================================================
    # 8. DOCTOR RECOMMENDATION
    # =====================================================

    if intent.intent == "doctor_recommendation":

        if not intent.specialty:

            message_lower = (
                request.message.lower()
            )

            if any(
                keyword in message_lower
                for keyword in [
                    "knee",
                    "joint",
                    "bone",
                    "fracture",
                    "back pain",
                    "neck pain",
                    "shoulder pain",
                    "hip pain"
                ]
            ):

                intent.specialty = (
                    "Orthopedics"
                )

            elif any(
                keyword in message_lower
                for keyword in [
                    "skin",
                    "rash",
                    "acne",
                    "skin problem"
                ]
            ):

                intent.specialty = (
                    "Dermatology"
                )

            elif any(
                keyword in message_lower
                for keyword in [
                    "heart",
                    "cardiac"
                ]
            ):

                intent.specialty = (
                    "Cardiology"
                )

            elif any(
                keyword in message_lower
                for keyword in [
                    "child",
                    "children",
                    "baby",
                    "pediatric"
                ]
            ):

                intent.specialty = (
                    "Pediatrics"
                )

            elif any(
                keyword in message_lower
                for keyword in [
                    "cold",
                    "fever",
                    "cough",
                    "flu"
                ]
            ):

                intent.specialty = (
                    "General Medicine"
                )

        if not intent.specialty:

            return ChatResponse(
                answer=(
                    "I can help you find an appropriate "
                    "hospital specialty. Please briefly "
                    "describe the health concern you "
                    "would like help navigating."
                )
            )

        doctors = find_doctors_by_specialty(
            db,
            intent.specialty
        )

        if not doctors:

            return ChatResponse(
                answer=(
                    f"I couldn't find an active hospital "
                    f"doctor for the {intent.specialty} "
                    "specialty in the hospital database."
                )
            )

        context = retrieve_documents(
            request.message
        )

        context += (
            "\n\nDATABASE DOCTOR RESULTS:\n"
            + str(doctors)
        )

        answer = generate_response(
            request.message,
            context,
            history_text
        )

        if not output_guardrail(answer):

            answer = (
                f"For this concern, the "
                f"{intent.specialty} department "
                "would be the appropriate place "
                "to start."
            )

        return ChatResponse(
            answer=answer
        )

    # =====================================================
    # 9. DOCTOR SEARCH
    # =====================================================

    if intent.intent == "doctor_search":

        if intent.doctor_name:

            doctor = find_doctor_by_name(
                db,
                intent.doctor_name
            )

            doctors = (
                [doctor]
                if doctor
                else []
            )

        elif intent.specialty:

            doctors = find_doctors_by_specialty(
                db,
                intent.specialty
            )

        else:

            doctors = get_all_doctors(
                db
            )

        if not doctors:

            return ChatResponse(
                answer=(
                    "I couldn't find a matching doctor "
                    "in the hospital database."
                )
            )

        context = retrieve_documents(
            request.message
        )

        context += (
            "\n\nDATABASE RESULTS:\n"
            + str(doctors)
        )

        answer = generate_response(
            request.message,
            context,
            history_text
        )

        return ChatResponse(
            answer=answer
        )

    # =====================================================
    # 10. AVAILABILITY
    # =====================================================

    if intent.intent == "availability":

        doctor = None

        if intent.doctor_name:

            doctor = find_doctor_by_name(
                db,
                intent.doctor_name
            )

        elif intent.specialty:

            doctors = find_doctors_by_specialty(
                db,
                intent.specialty
            )

            if doctors:

                doctor = doctors[0]

        if not doctor:

            return ChatResponse(
                answer=(
                    "Please tell me which doctor or "
                    "specialty you would like to check."
                )
            )

        if not intent.date:

            return ChatResponse(
                answer=(
                    f"I found {doctor['name']}. "
                    "What date would you like to check? "
                    "Please use YYYY-MM-DD."
                )
            )

        slots = get_available_slots(
            db,
            doctor["id"],
            intent.date
        )

        if not slots:

            return ChatResponse(
                answer=(
                    f"There are currently no available "
                    f"slots for {doctor['name']} on "
                    f"{intent.date}."
                )
            )

        slot_text = "\n".join(
            [
                f"{slot['start_time'].strftime('%H:%M')} "
                f"(slot ID {slot['slot_id']})"
                for slot in slots
            ]
        )

        return ChatResponse(
            answer=(
                f"Available appointments with "
                f"{doctor['name']} on {intent.date}:\n\n"
                f"{slot_text}\n\n"
                "Tell me which time you would like to book."
            )
        )

    # =====================================================
    # 11. BOOK APPOINTMENT
    # =====================================================

    if intent.intent == "book_appointment":

        if not intent.doctor_name:

            return ChatResponse(
                answer=(
                    "Which doctor would you like to "
                    "book an appointment with?"
                )
            )

        doctor = find_doctor_by_name(
            db,
            intent.doctor_name
        )

        if not doctor:

            return ChatResponse(
                answer=(
                    "I couldn't find that doctor in "
                    "the hospital database."
                )
            )

        if not intent.date:

            return ChatResponse(
                answer=(
                    "What date would you like "
                    "the appointment?"
                )
            )

        if not intent.time:

            slots = get_available_slots(
                db,
                doctor["id"],
                intent.date
            )

            if not slots:

                return ChatResponse(
                    answer=(
                        "There are no available slots "
                        "for that doctor on that date."
                    )
                )

            times = ", ".join(
                [
                    slot["start_time"].strftime(
                        "%H:%M"
                    )
                    for slot in slots
                ]
            )

            return ChatResponse(
                answer=(
                    f"Available times for "
                    f"{doctor['name']} on "
                    f"{intent.date}: {times}. "
                    "Which time would you like?"
                )
            )

        if not intent.patient_name:

            return ChatResponse(
                answer=(
                    "Please provide the patient's full name."
                )
            )

        if not intent.phone:

            return ChatResponse(
                answer=(
                    "Please provide the patient's phone "
                    "number so I can complete the booking."
                )
            )

        slot = None

        if intent.slot_id is not None:

            slot = get_slot_by_id(
                db,
                intent.slot_id
            )

            if not slot:

                return ChatResponse(
                    answer=(
                        "I couldn't find the selected "
                        "appointment slot."
                    )
                )

            if slot["status"] != "AVAILABLE":

                return ChatResponse(
                    answer=(
                        "Sorry, that appointment slot "
                        "is no longer available. Please "
                        "choose another available slot."
                    )
                )

        else:

            slot = find_slot(
                db,
                doctor["id"],
                intent.date,
                intent.time
            )

        if not slot:

            return ChatResponse(
                answer=(
                    "I couldn't find that exact appointment "
                    "time in the hospital schedule."
                )
            )

        result = book_appointment(
            db=db,
            patient_name=intent.patient_name,
            phone=intent.phone,
            doctor_id=doctor["id"],
            slot_id=slot["slot_id"]
        )

        if not result["success"]:

            return ChatResponse(
                answer=result["message"]
            )

        return ChatResponse(
            answer=(
                "Appointment confirmed!\n\n"
                f"Appointment ID: "
                f"{result['appointment_id']}\n"
                f"Doctor: {doctor['name']}\n"
                f"Date: {intent.date}\n"
                f"Time: {intent.time}\n"
                f"Patient: {intent.patient_name}"
            ),
            appointment_id=result[
                "appointment_id"
            ]
        )

    # =====================================================
    # 12. INSURANCE
    # =====================================================

    if intent.intent == "insurance":

        insurance_context = retrieve_documents(
            request.message
        )

        result = db.execute(
            text("""
                SELECT
                    ip.provider_name,
                    ip.plan_name,
                    ic.department,
                    ic.specialty,
                    ic.covered,
                    ic.copay,
                    ic.notes

                FROM insurance_plans ip

                JOIN insurance_coverage ic
                    ON ip.id = ic.insurance_plan_id

                WHERE ip.active = TRUE

                ORDER BY ip.provider_name
            """)
        )

        insurance_rows = [
            dict(row._mapping)
            for row in result
        ]

        insurance_context += (
            "\n\nDATABASE INSURANCE RESULTS:\n"
            + str(insurance_rows)
        )

        answer = generate_response(
            request.message,
            insurance_context,
            history_text
        )

        if not output_guardrail(answer):

            answer = (
                "I can provide general insurance "
                "information from the hospital's "
                "records, but I cannot guarantee "
                "coverage or approval. Please confirm "
                "your specific policy with the hospital "
                "insurance desk."
            )

        return ChatResponse(
            answer=answer
        )

    # =====================================================
    # 13. GENERAL HOSPITAL INFORMATION
    # =====================================================

    context = retrieve_documents(
        request.message
    )

    answer = generate_response(
        request.message,
        context,
        history_text
    )

    if not output_guardrail(answer):

        answer = (
            "I can only provide information based "
            "on the hospital's approved information."
        )

    return ChatResponse(
        answer=answer
    )