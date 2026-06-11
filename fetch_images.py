import requests
import os
import time
import urllib3
from dotenv import load_dotenv

load_dotenv()

# Suppress SSL warning — hackathon server has an expired certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_KEY = os.getenv("FHIR_API_KEY")
DICOMWEB_URL = os.getenv("DICOMWEB_URL", "https://hackathon.siim.org/dicomweb")
HEADERS = {"apikey": API_KEY, "Accept": "application/json"}

RETRIES = 3
RETRY_DELAY = 2  # seconds between retries

def _get(url, headers=None, retries=RETRIES):
    """GET with automatic retries on 502/503 or connection errors."""
    headers = headers or HEADERS
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=headers, verify=False, timeout=15)
            if response.status_code in (502, 503):
                raise requests.exceptions.HTTPError(f"HTTP {response.status_code}")
            response.raise_for_status()
            return response
        except (requests.exceptions.HTTPError,
                requests.exceptions.SSLError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            last_error = e
            if attempt < retries:
                print(f"  Attempt {attempt} failed ({e}), retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
    raise last_error

def fetch_series(study_uid):
    url = f"{DICOMWEB_URL}/studies/{study_uid}/series"
    return _get(url).json()

def fetch_instances(study_uid, series_uid):
    url = f"{DICOMWEB_URL}/studies/{study_uid}/series/{series_uid}/instances"
    return _get(url).json()

def download_image(study_uid, series_uid, instance_uid, output_path):
    url = f"{DICOMWEB_URL}/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/rendered"
    headers = {**HEADERS, "Accept": "image/jpeg"}
    response = _get(url, headers=headers)
    with open(output_path, "wb") as f:
        f.write(response.content)

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

                # Download up to 3 images per series
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
            print(f"DICOMweb unavailable after {RETRIES} attempts: {e}")
            all_images.append({
                "path": None,
                "modality": modality,
                "study_date": study_date,
                "error": "Image server temporarily unavailable — try again shortly"
            })

    return all_images
