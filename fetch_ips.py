import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("FHIR_API_KEY")
FHIR_URL = os.getenv("FHIR_BASE_URL", "http://hackathon.siim.org/fhir")
HEADERS = {"apikey": API_KEY}

def fetch_resource(resource_type, patient_id):
    response = requests.get(f"{FHIR_URL}/{resource_type}", headers=HEADERS, params={"patient": patient_id})
    data = response.json()
    return [entry["resource"] for entry in data.get("entry", [])]

def fetch_patient(patient_id):
    response = requests.get(f"{FHIR_URL}/Patient/{patient_id}", headers=HEADERS)
    return response.json()

def fetch_all_patients():
    response = requests.get(f"{FHIR_URL}/Patient", headers=HEADERS, params={"_count": 50})
    data = response.json()
    patients = []
    for entry in data.get("entry", []):
        p = entry["resource"]
        name = p.get("name", [{}])[0]
        full_name = f"{name.get('given', [''])[0]} {name.get('family', '')}".strip()
        patients.append({"id": p["id"], "name": full_name})
    return patients

def fetch_ips(patient_id):
    patient = fetch_patient(patient_id)
    name = patient.get("name", [{}])[0]

    return {
        "patient": {
            "id": patient_id,
            "name": f"{name.get('given', [''])[0]} {name.get('family', '')}".strip(),
            "dob": patient.get("birthDate", "N/A"),
            "gender": patient.get("gender", "N/A").capitalize(),
            "address": _format_address(patient.get("address", [{}])[0]),
        },
        "conditions": fetch_resource("Condition", patient_id),
        "allergies": fetch_resource("AllergyIntolerance", patient_id),
        "medications": fetch_resource("MedicationRequest", patient_id),
        "reports": fetch_resource("DiagnosticReport", patient_id),
        "imaging": fetch_resource("ImagingStudy", patient_id),
    }

def _format_address(addr):
    parts = addr.get("line", []) + [addr.get("city", ""), addr.get("state", ""), addr.get("postalCode", "")]
    return ", ".join(p for p in parts if p)
