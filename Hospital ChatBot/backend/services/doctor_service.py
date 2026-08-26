from sqlalchemy import text


def get_all_doctors(db):

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


def find_doctors_by_specialty(
    db,
    specialty: str
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
            AND LOWER(specialty) = LOWER(:specialty)
            ORDER BY experience_years DESC
        """),
        {
            "specialty": specialty
        }
    )

    return [
        dict(row._mapping)
        for row in result
    ]


def find_doctor_by_name(
    db,
    doctor_name: str
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
            AND LOWER(name) LIKE LOWER(:name)
            LIMIT 1
        """),
        {
            "name": f"%{doctor_name}%"
        }
    )

    row = result.fetchone()

    if not row:
        return None

    return dict(row._mapping)
