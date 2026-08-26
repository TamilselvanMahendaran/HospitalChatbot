import os

from dotenv import load_dotenv


load_dotenv()


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

DATABASE_URL = os.getenv("DATABASE_URL")

GEMINI_MODEL = "gemini-2.5-flash"


if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing from .env"
    )

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is missing from .env"
    )
