CREATE TABLE doctors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    specialty VARCHAR(100) NOT NULL,
    department VARCHAR(100),
    qualification VARCHAR(255),
    experience_years INTEGER,
    consultation_fee NUMERIC(10,2),
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE patients (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    phone VARCHAR(30) UNIQUE NOT NULL,
    email VARCHAR(150)
);

CREATE TABLE appointment_slots (
    id SERIAL PRIMARY KEY,

    doctor_id INTEGER NOT NULL
        REFERENCES doctors(id),

    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,

    status VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE',

    UNIQUE(doctor_id, start_time)
);

CREATE TABLE appointments (
    id SERIAL PRIMARY KEY,

    patient_id INTEGER NOT NULL
        REFERENCES patients(id),

    doctor_id INTEGER NOT NULL
        REFERENCES doctors(id),

    slot_id INTEGER NOT NULL
        REFERENCES appointment_slots(id),

    status VARCHAR(30) NOT NULL DEFAULT 'CONFIRMED',

    booked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(slot_id)
);

CREATE TABLE insurance_plans (
    id SERIAL PRIMARY KEY,

    provider_name VARCHAR(150) NOT NULL,
    plan_name VARCHAR(150) NOT NULL,

    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE insurance_coverage (
    id SERIAL PRIMARY KEY,

    insurance_plan_id INTEGER NOT NULL
        REFERENCES insurance_plans(id),

    department VARCHAR(100),
    specialty VARCHAR(100),

    covered BOOLEAN NOT NULL,

    copay NUMERIC(10,2),
    notes TEXT
);

CREATE TABLE documents (
    id SERIAL PRIMARY KEY,

    filename VARCHAR(255) NOT NULL,
    document_type VARCHAR(50),

    content TEXT NOT NULL,

    version INTEGER DEFAULT 1,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
