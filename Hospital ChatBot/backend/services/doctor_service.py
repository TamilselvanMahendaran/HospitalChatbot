from sqlalchemy import text


# =========================================================
# SPECIALTY NORMALIZATION
# =========================================================

SPECIALTY_ALIASES = {
    # Cardiology
    "cardiologist": "Cardiology",
    "cardiologists": "Cardiology",
    "cardiac": "Cardiology",
    "heart doctor": "Cardiology",
    "heart doctors": "Cardiology",
    "heart specialist": "Cardiology",
    "heart specialists": "Cardiology",

    # Dermatology
    "dermatologist": "Dermatology",
    "dermatologists": "Dermatology",
    "skin doctor": "Dermatology",
    "skin doctors": "Dermatology",
    "skin specialist": "Dermatology",
    "skin specialists": "Dermatology",

    # Pediatrics
    "pediatrician": "Pediatrics",
    "pediatricians": "Pediatrics",
    "paediatrician": "Pediatrics",
    "paediatricians": "Pediatrics",
    "child doctor": "Pediatrics",
    "child doctors": "Pediatrics",
    "children doctor": "Pediatrics",
    "children's doctor": "Pediatrics",

    # Orthopedics
    "orthopedic": "Orthopedics",
    "orthopedics": "Orthopedics",
    "orthopaedic": "Orthopedics",
    "orthopaedics": "Orthopedics",
    "orthopedic doctor": "Orthopedics",
    "orthopedic doctors": "Orthopedics",
    "bone doctor": "Orthopedics",
    "bone doctors": "Orthopedics",
    "bone specialist": "Orthopedics",
    "bone specialists": "Orthopedics",

    # General Medicine
    "general physician": "General Medicine",
    "general physicians": "General Medicine",
    "general medicine": "General Medicine",
    "physician": "General Medicine",
    "physicians": "General Medicine",
    "gp": "General Medicine",
}


def normalize_specialty(
    specialty: str
):
    """
    Convert common user terms into the exact specialty
    value used by the database.

    Example:

        cardiologist
        cardiologists
        heart doctor

    become:

        Cardiology
    """

    if not specialty:

        return specialty

    normalized = (
        specialty
        .strip()
        .lower()
    )

    # Direct alias lookup.
    if normalized in SPECIALTY_ALIASES:

        return SPECIALTY_ALIASES[
            normalized
        ]

    # Handle simple plural/singular variations.
    if normalized.endswith("s"):

        singular = normalized[:-1]

        if singular in SPECIALTY_ALIASES:

            return SPECIALTY_ALIASES[
                singular
            ]

    return specialty.strip()


# =========================================================
# GET ALL DOCTORS
# =========================================================


def get_all_doctors(
    db
):

    result = db.execute(
        text("""
            SELECT
                id,
                name,
                specialty,
                department,
                qualification,
                experience_years,
                consultation_fee
            FROM doctors
            WHERE active = TRUE
            ORDER BY name
        """)
    )

    return [
        dict(row._mapping)
        for row in result
    ]


# =========================================================
# FIND DOCTORS BY SPECIALTY
# =========================================================


def find_doctors_by_specialty(
    db,
    specialty: str
):

    normalized_specialty = normalize_specialty(
        specialty
    )

    result = db.execute(
        text("""
            SELECT
                id,
                name,
                specialty,
                department,
                qualification,
                experience_years,
                consultation_fee
            FROM doctors
            WHERE active = TRUE

            AND (
                LOWER(specialty) =
                    LOWER(:specialty)

                OR LOWER(department) =
                    LOWER(:specialty)
            )

            ORDER BY experience_years DESC
        """),
        {
            "specialty": normalized_specialty
        }
    )

    return [
        dict(row._mapping)
        for row in result
    ]


# =========================================================
# FIND DOCTOR BY NAME
# =========================================================


def find_doctor_by_name(
    db,
    doctor_name: str
):

    if not doctor_name:

        return None

    cleaned_name = (
        doctor_name
        .strip()
    )

    # -----------------------------------------------------
    # First try the normal partial match.
    # -----------------------------------------------------

    result = db.execute(
        text("""
            SELECT
                id,
                name,
                specialty,
                department,
                qualification,
                experience_years,
                consultation_fee
            FROM doctors
            WHERE active = TRUE

            AND LOWER(name) LIKE LOWER(:name)

            LIMIT 1
        """),
        {
            "name": f"%{cleaned_name}%"
        }
    )

    row = result.fetchone()

    if row:

        return dict(row._mapping)

    # -----------------------------------------------------
    # If the user didn't include "Dr.", try again.
    # -----------------------------------------------------

    without_dr = cleaned_name

    if without_dr.lower().startswith("dr."):

        without_dr = (
            without_dr[3:]
            .strip()
        )

    result = db.execute(
        text("""
            SELECT
                id,
                name,
                specialty,
                department,
                qualification,
                experience_years,
                consultation_fee
            FROM doctors
            WHERE active = TRUE

            AND LOWER(
                REPLACE(name, 'Dr. ', '')
            ) LIKE LOWER(:name)

            LIMIT 1
        """),
        {
            "name": f"%{without_dr}%"
        }
    )

    row = result.fetchone()

    if not row:

        return None

    return dict(row._mapping)