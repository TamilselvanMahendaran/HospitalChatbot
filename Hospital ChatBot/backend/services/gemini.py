from typing import Literal, Optional

from google import genai
from google.genai import types

from pydantic import BaseModel

from backend.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL
)


client = genai.Client(
    api_key=GEMINI_API_KEY
)


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

    patient_name: Optional[str] = None

    phone: Optional[str] = None


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
2. A question about which specialist to see is doctor_recommendation.
3. A request to see available times is availability.
4. A request to actually reserve/book an appointment is book_appointment.
5. Insurance questions are insurance.
6. General medical diagnosis or treatment requests are medical_guidance.
7. Emergency concerns are emergency.
8. Anything unrelated to the hospital is other.

Extract these values when explicitly present:

specialty
doctor_name
date
time
patient_name
phone

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

9. Real-time appointment information comes from the database.

10. If information is missing, say that the hospital
does not have that information available.

11. If a user asks something unrelated to the hospital,
politely refuse.

12. If a user asks which doctor they should see,
recommend a hospital specialty rather than diagnosing.

13. Identify yourself as the ABC Multispeciality Hospital
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
