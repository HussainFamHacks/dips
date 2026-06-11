import base64
import json
import uuid
import os
import tempfile
from datetime import datetime, timezone
from fetch_images import fetch_series, fetch_instances, download_raw_dicom


def make_id():
    return str(uuid.uuid4())


def encode_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def build_fhir_bundle(ips_data, images, output_path=None):
    """
    Build a FHIR R5 Bundle (type: document) containing:
      - Composition (IPS document header)
      - Patient
      - Condition resources
      - AllergyIntolerance resources
      - MedicationRequest resources
      - ImagingStudy resources
      - Binary resources (base64 DICOM images)
      - DocumentReference resources (linking images into the document)
    """

    bundle_id = make_id()
    composition_id = make_id()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    patient = ips_data["patient"]
    patient_ref = f"Patient/{patient['id']}"

    entries = []

    # ── 1. Patient ────────────────────────────────────────────────────────────
    patient_resource = {
        "resourceType": "Patient",
        "id": patient["id"],
        "name": [{"use": "official", "text": patient["name"]}],
        "birthDate": patient["dob"],
        "gender": patient["gender"].lower(),
        "address": [{"text": patient["address"]}]
    }
    entries.append(_entry("Patient", patient["id"], patient_resource))

    # ── 2. Conditions ─────────────────────────────────────────────────────────
    condition_refs = []
    for c in ips_data["conditions"]:
        res = {**c, "subject": {"reference": patient_ref}}
        entries.append(_entry("Condition", c["id"], res))
        condition_refs.append({"reference": f"Condition/{c['id']}"})

    # ── 3. Allergies ──────────────────────────────────────────────────────────
    allergy_refs = []
    for a in ips_data["allergies"]:
        res = {**a, "patient": {"reference": patient_ref}}
        entries.append(_entry("AllergyIntolerance", a["id"], res))
        allergy_refs.append({"reference": f"AllergyIntolerance/{a['id']}"})

    # ── 4. Medications ────────────────────────────────────────────────────────
    med_refs = []
    for m in ips_data["medications"]:
        res = {**m, "subject": {"reference": patient_ref}}
        entries.append(_entry("MedicationRequest", m["id"], res))
        med_refs.append({"reference": f"MedicationRequest/{m['id']}"})

    # ── 5. ImagingStudy resources ─────────────────────────────────────────────
    imaging_refs = []
    for study in ips_data["imaging"]:
        res = {**study, "subject": {"reference": patient_ref}}
        entries.append(_entry("ImagingStudy", study["id"], res))
        imaging_refs.append({"reference": f"ImagingStudy/{study['id']}"})

    # ── 6. Binary + DocumentReference for rendered JPEG images ───────────────
    docref_refs = []
    for img in images:
        if not img.get("path") or not os.path.exists(img["path"]):
            continue

        # Binary resource — holds the rendered JPEG
        binary_id = make_id()
        binary_resource = {
            "resourceType": "Binary",
            "id": binary_id,
            "contentType": "image/jpeg",
            "data": encode_image(img["path"])
        }
        entries.append(_entry("Binary", binary_id, binary_resource))

        # DocumentReference — metadata wrapper pointing to the Binary
        docref_id = make_id()
        docref_resource = {
            "resourceType": "DocumentReference",
            "id": docref_id,
            "status": "current",
            "type": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": "18748-4",
                    "display": "Diagnostic imaging study"
                }]
            },
            "subject": {"reference": patient_ref},
            "date": now,
            "description": f"{img.get('modality', 'UNKNOWN')} image — {img.get('study_date', 'N/A')}",
            "content": [{
                "attachment": {
                    "contentType": "image/jpeg",
                    "url": f"Binary/{binary_id}",
                    "title": f"{img.get('modality', 'UNKNOWN')} — {img.get('study_date', 'N/A')}"
                }
            }]
        }
        entries.append(_entry("DocumentReference", docref_id, docref_resource))
        docref_refs.append({"reference": f"DocumentReference/{docref_id})"})

    # ── 7. Raw DICOM — fetch one instance and embed as application/dicom ─────
    raw_dicom_refs = []
    for study in ips_data["imaging"]:
        study_uid = next(
            (i["value"] for i in study.get("identifier", []) if i.get("system") == "urn:dicom:uid"),
            None
        )
        if not study_uid:
            continue
        try:
            series_list = fetch_series(study_uid)
            if not series_list:
                continue
            # Just grab the first series, first instance
            series_uid = series_list[0]["0020000E"]["Value"][0]
            instances = fetch_instances(study_uid, series_uid)
            if not instances:
                continue
            instance_uid = instances[0]["00080018"]["Value"][0]
            modality = series_list[0].get("00080060", {}).get("Value", ["UNKNOWN"])[0]

            # Download raw DICOM to a temp file
            with tempfile.NamedTemporaryFile(suffix=".dcm", delete=False) as tmp:
                tmp_path = tmp.name
            download_raw_dicom(study_uid, series_uid, instance_uid, tmp_path)

            # Encode and embed
            with open(tmp_path, "rb") as f:
                dicom_b64 = base64.b64encode(f.read()).decode("utf-8")
            os.unlink(tmp_path)

            # Binary resource — raw DICOM
            dicom_binary_id = make_id()
            entries.append(_entry("Binary", dicom_binary_id, {
                "resourceType": "Binary",
                "id": dicom_binary_id,
                "contentType": "application/dicom",
                "data": dicom_b64
            }))

            # DocumentReference pointing to the raw DICOM Binary
            dicom_docref_id = make_id()
            entries.append(_entry("DocumentReference", dicom_docref_id, {
                "resourceType": "DocumentReference",
                "id": dicom_docref_id,
                "status": "current",
                "type": {
                    "coding": [{
                        "system": "http://loinc.org",
                        "code": "18748-4",
                        "display": "Diagnostic imaging study"
                    }]
                },
                "subject": {"reference": patient_ref},
                "date": now,
                "description": f"Raw DICOM — {modality} — {study.get('started', 'N/A')}",
                "content": [{
                    "attachment": {
                        "contentType": "application/dicom",
                        "url": f"Binary/{dicom_binary_id}",
                        "title": f"DICOM Instance — {modality}"
                    }
                }]
            }))
            raw_dicom_refs.append({"reference": f"DocumentReference/{dicom_docref_id}"})

        except Exception as e:
            print(f"Could not fetch raw DICOM: {e}")

    # ── 8. Composition (IPS document header — ties everything together) ───────
    composition = {
        "resourceType": "Composition",
        "id": composition_id,
        "status": "final",
        "type": {
            "coding": [{
                "system": "http://loinc.org",
                "code": "60591-5",
                "display": "Patient summary Document"
            }]
        },
        "subject": {"reference": patient_ref},
        "date": now,
        "author": [{"display": "DIPS — DICOM International Patient Summary"}],
        "title": f"DIPS Summary — {patient['name']}",
        "section": [
            _section("Conditions", "11450-4", condition_refs),
            _section("Allergies", "48765-2", allergy_refs),
            _section("Medications", "10160-0", med_refs),
            _section("Imaging Studies", "18748-4", imaging_refs),
            _section("DICOM Images", "18748-4", docref_refs),
            _section("Raw DICOM", "18748-4", raw_dicom_refs),
        ]
    }
    # Composition goes first in the bundle
    entries.insert(0, _entry("Composition", composition_id, composition))

    # ── 9. Assemble Bundle ────────────────────────────────────────────────────
    bundle = {
        "resourceType": "Bundle",
        "id": bundle_id,
        "meta": {
            "profile": ["http://hl7.org/fhir/uv/ips/StructureDefinition/Bundle-uv-ips"]
        },
        "identifier": {
            "system": "urn:dips:hackathon",
            "value": bundle_id
        },
        "type": "document",
        "timestamp": now,
        "entry": entries
    }

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(bundle, f, indent=2)
        print(f"FHIR bundle saved to {output_path}")

    return bundle


# ── Helpers ───────────────────────────────────────────────────────────────────

def _entry(resource_type, resource_id, resource):
    return {
        "fullUrl": f"urn:uuid:{resource_id}",
        "resource": resource
    }


def _section(title, loinc_code, entry_refs):
    return {
        "title": title,
        "code": {
            "coding": [{
                "system": "http://loinc.org",
                "code": loinc_code,
                "display": title
            }]
        },
        "entry": entry_refs if entry_refs else []
    }
