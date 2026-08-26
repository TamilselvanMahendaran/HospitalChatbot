from typing import Literal, Optional

from google import genai
from google.genai import types

from pydantic import BaseModel

from backend.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL
)


# =========================================================
# GEMINI CLIENT
# =========================================================

client = genai.Client(
    api_key=GEMINI_API_KEY
)


# =========================================================
# INTENT RESULT
# =========================================================

class IntentResult(BaseModel):

    intent: Literal[
        "hospital_info",
        "doctor_recommendation",
        "doctor_search",
        "availability",
        "book_appointment",
        "cancel_appointment",
        "appointment_details",
        "insurance",
        "medical_guidance",
        "emergency",
        "other"
    ]

    specialty: Optional[str] = None

    doctor_name: Optional[str] = None

    date: Optional[str] = None

    time: Optional[str] = None

    slot_id: Optional[int] = None

    patient_name: Optional[str] = None

    phone: Optional[str] = None

    appointment_id: Optional[int] = None


# =========================================================
# CLASSIFY INTENT
# =========================================================

def classify_intent(
    message: str,
    history: str = ""
):

    prompt = f"""
You are the intent classifier for ABC Multispeciality Hospital.

Classify the user's request.

Allowed intents:

hospital_info
doctor_recommendation
doctor_search
availability
book_appointment
cancel_appointment
appointment_details
insurance
medical_guidance
emergency
other

Rules:

1. Never diagnose the patient.

2. A question about which specialist to see is
doctor_recommendation.

3. A request to see available appointment times is
availability.

4. A request to reserve or book an appointment is
book_appointment.

5. A request to cancel, remove, delete, or terminate
an existing appointment is cancel_appointment.

6. If the previous assistant message asks the user
for an appointment ID or phone number in order to
cancel an appointment, the next user message is
cancel_appointment.

7. If the conversation is already in a cancellation
flow, DO NOT classify the user's response as
book_appointment.

8. If the previous assistant message displayed
appointment slots and the user selects one of those
slots, classify it as book_appointment.

9. If the previous assistant message asks for the
patient's full name during booking, interpret the
next user message as patient_name.

10. If the previous assistant message asks for the
patient's phone number during booking, interpret the
next user message as phone.

11. Insurance questions are insurance.

12. General medical diagnosis or treatment requests
are medical_guidance.

13. Emergency concerns are emergency.

14. Anything unrelated to the hospital is other.

15. Use conversation history when continuing an
appointment conversation.

16. For cancellation, extract appointment_id when
the user provides a numeric appointment ID.

17. Do not interpret a numeric response as a slot ID
when the conversation is currently in a cancellation
flow.

Extract these values when explicitly present:

specialty
doctor_name
date
time
slot_id
patient_name
phone
appointment_id

Date must use YYYY-MM-DD if possible.

Time should use HH:MM 24-hour format if possible.

Conversation history:
{history}

User message:
{message}
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema=IntentResult,
        )
    )

    if response.parsed:

        return response.parsed

    return IntentResult.model_validate_json(
        response.text
    )


# =========================================================
# GENERATE RESPONSE
# =========================================================

def generate_response(
    user_message: str,
    context: str,
    history: str = ""
):

    system_prompt = """
You are the official virtual assistant for
ABC Multispeciality Hospital.

Your job is ONLY to help with:

- Hospital information
- Doctors
- Departments
- Appointment availability
- Appointment booking
- Appointment cancellation
- Appointment details
- Insurance information
- Hospital policies

IMPORTANT RULES:

1. Never diagnose a disease.

2. Never prescribe medicine.

3. Never recommend medication dosage.

4. Never invent doctors.

5. Never invent appointment times.

6. Never claim that an unavailable slot is available.

7. Never guarantee insurance approval.

8. Use only the hospital context provided.

9. Real-time appointment information comes from
the database.

10. If information is missing, say that the hospital
does not have that information available.

11. If a user asks something unrelated to the hospital,
politely explain that you can only answer questions
related to ABC Multispeciality Hospital.

12. If a user asks which doctor they should see,
recommend a hospital specialty rather than diagnosing.

13. When appointment information is provided by the
database, do not change or invent the appointment
times or slot IDs.

14. If an appointment cancellation has been completed
by the backend, clearly tell the user that the
appointment was cancelled and that the slot is
available again.

15. Identify yourself as the ABC Multispeciality Hospital
virtual assistant when appropriate.
"""

    prompt = f"""
{system_prompt}

HOSPITAL INFORMATION:

{context}

CONVERSATION:

{history}

USER:

{user_message}

Answer clearly and concisely.
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1
        )
    )

    return response.text