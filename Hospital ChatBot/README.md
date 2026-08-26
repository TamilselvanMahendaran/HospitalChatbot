# ABC Multispeciality Hospital Chatbot

A local hospital chatbot built with:

- FastAPI
- Streamlit
- PostgreSQL
- Gemini 2.5 Flash
- SQL appointment management
- Hospital document retrieval
- Input/output guardrails

## Features

- Doctor search
- Doctor recommendation
- Appointment availability
- Appointment booking
- Appointment cancellation
- Insurance information
- Hospital information
- Block appointment slots
- Scope guardrails
- Medical safety guardrails
- Database transaction protection against double booking

## Start PostgreSQL

docker start hospital-postgres

## Activate Python environment

Windows:

.venv\Scripts\activate

macOS/Linux:

source .venv/bin/activate

## Install packages

pip install -r requirements.txt

## Start FastAPI

uvicorn backend.main:app --reload --port 8000

## Start Streamlit

streamlit run frontend/app.py
