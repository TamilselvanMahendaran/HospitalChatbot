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
    find_slot,
    book_appointment,
    get_appointment,
    cancel_appointment
)


app = FastAPI(
    title="ABC Hospital Chatbot API",
    version="1.0.0"
)


@app.get("/")
def root():

    return {
        "hospital": "ABC Multispeciality Hospital",
        "service": "Hospital Chatbot API",
        "status": "running"
    }


@app.get("/doctors")
def doctors(
    db: Session = Depends(get_db)
):

    return {
        "doctors": get_all_doctors(db)
    }


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


@app.post(
    "/chat",
    response_model=ChatResponse
)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db)
):

    # ----------------------------------
    # 1. INPUT GUARDRAIL
    # ----------------------------------

    allowed, refusal = input_guardrail(
        request.message
    )

    if not allowed:

        return ChatResponse(
            answer=refusal
        )

    # ----------------------------------
    # 2. CONVERSATION HISTORY
    # ----------------------------------

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

    # ----------------------------------
    # 3. INTENT CLASSIFICATION
    # ----------------------------------

    intent = classify_intent(
        request.message,
        history_text
    )

    # ----------------------------------
    # 4. EMERGENCY
    # ----------------------------------

    if intent.intent == "emergency":

        answer = (
            "If you believe this is a medical emergency, "
            "please seek immediate emergency medical care "
            "or contact the hospital emergency department. "
            "I can also help you find the appropriate "
            "hospital department."
        )

        return ChatResponse(
            answer=answer
        )

    # ----------------------------------
    # 5. UNRELATED
    # ----------------------------------

    if intent.intent == "other":

        return ChatResponse(
            answer=(
                "I'm the ABC Multispeciality Hospital "
                "virtual assistant. I can help with doctors, "
                "appointments, hospital information and "
                "insurance questions."
            )
        )

    # ----------------------------------
    # 6. MEDICAL GUIDANCE
    # ----------------------------------

    if intent.intent == "medical_guidance":

        return ChatResponse(
            answer=(
                "I can help you find the appropriate "
                "hospital department or doctor, but I "
                "cannot diagnose conditions or prescribe "
                "medication. Please tell me about the "
                "type of concern you would like help "
                "finding a specialist for."
            )
        )

    # ----------------------------------
    # 7. DOCTOR RECOMMENDATION
    # ----------------------------------

    if intent.intent == "doctor_recommendation":

        if not intent.specialty:

            return ChatResponse(
                answer=(
                    "I can help you find an appropriate "
                    "hospital specialty. Please briefly "
                    "describe the health concern you would "
                    "like help navigating."
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

        doctor_context = "\n".join(
            str(doctor)
            for doctor in doctors
        )

        context += (
            "\n\nDATABASE DOCTOR RESULTS:\n"
            + doctor_context
        )

        answer = generate_response(
            request.message,
            context,
            history_text
        )

        if not output_guardrail(answer):

            answer = (
                "I can help you find a hospital specialist, "
                "but I cannot provide a diagnosis."
            )

        return ChatResponse(
            answer=answer
        )

    # ----------------------------------
    # 8. DOCTOR SEARCH
    # ----------------------------------

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

            doctors = get_all_doctors(db)

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

    # ----------------------------------
    # 9. AVAILABILITY
    # ----------------------------------

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

    # ----------------------------------
    # 10. BOOK APPOINTMENT
    # ----------------------------------

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

    # ----------------------------------
    # 11. INSURANCE
    # ----------------------------------

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
                "I can provide general insurance information "
                "from the hospital's records, but I cannot "
                "guarantee coverage or approval. Please "
                "confirm your specific policy with the "
                "hospital insurance desk."
            )

        return ChatResponse(
            answer=answer
        )

    # ----------------------------------
    # 12. GENERAL HOSPITAL INFORMATION
    # ----------------------------------

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
            "I can only provide information based on "
            "the hospital's approved information."
        )

    return ChatResponse(
        answer=answer
    )
