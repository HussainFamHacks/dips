import requests
import os
import urllib3
from dotenv import load_dotenv

load_dotenv()

# Suppress SSL warning — hackathon server has an expired certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_KEY = os.getenv("FHIR_API_KEY")
DICOMWEB_URL = os.getenv("DICOMWEB_URL", "https://hackathon.siim.org/dicomweb")
HEADERS = {"apikey": API_KEY, "Accept": "application/json"}

def fetch_series(study_uid):
    url = f"{DICOMWEB_URL}/studies/{study_uid}/series"
    response = requests.get(url, headers=HEADERS, verify=False, timeout=10)
    response.raise_for_status()
    return response.json()

def fetch_instances(study_uid, series_uid):
    url = f"{DICOMWEB_URL}/studies/{study_uid}/series/{series_uid}/instances"
    response = requests.get(url, headers=HEADERS, verify=False, timeout=10)
    response.raise_for_status()
    return response.json()

def download_image(study_uid, series_uid, instance_uid, output_path):
    url = f"{DICOMWEB_URL}/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/rendered"
    headers = {**HEADERS, "Accept": "image/jpeg"}
    response = requests.get(url, headers=headers, verify=False, timeout=10)
    response.raise_for_status()
    with open(output_path, "wb") as f:
        f.write(response.content)

def download_raw_dicom(study_uid, series_uid, instance_uid, output_path):
    """Download a single raw DICOM instance (application/dicom)"""
    url = f"{DICOMWEB_URL}/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}"
    headers = {**HEADERS, "Accept": "application/dicom"}
    response = requests.get(url, headers=headers, verify=False, timeout=15)
    response.raise_for_status()
    with open(output_path, "wb") as f:
        f.write(response.content)
    return output_path

def download_patient_images(patient_id, imaging_studies, output_dir="output/images"):
    os.makedirs(output_dir, exist_ok=True)
    all_images = []

    for study in imaging_studies:
        study_uid = next(
            (i["value"] for i in study.get("identifier", []) if i.get("system") == "urn:dicom:uid"),
            None
        )
        if not study_uid:
            continue

        study_date = study.get("started", "Unknown date")
        modality = "UNKNOWN"

        try:
            series_list = fetch_series(study_uid)
            for series in series_list:
                series_uid = series["0020000E"]["Value"][0]
                modality = series.get("00080060", {}).get("Value", ["UNKNOWN"])[0]
                instances = fetch_instances(study_uid, series_uid)

                for i, instance in enumerate(instances[:3]):
                    instance_uid = instance["00080018"]["Value"][0]
                    filename = os.path.join(output_dir, f"{patient_id}_{modality}_{i+1}.jpg")
                    download_image(study_uid, series_uid, instance_uid, filename)
                    all_images.append({
                        "path": filename,
                        "modality": modality,
                        "study_date": study_date,
                    })

        except Exception as e:
            print(f"DICOMweb unavailable: {e}")
            all_images.append({
                "path": None,
                "modality": modality,
                "study_date": study_date,
                "error": "Image server temporarily unavailable"
            })

    return all_images
