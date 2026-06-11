from flask import Flask, render_template, request, send_file, redirect, url_for
import os

from fetch_ips import fetch_ips, fetch_all_patients, fetch_patient
from fetch_images import download_patient_images
from build_report import build_report
from build_fhir_export import build_fhir_bundle
from generate_qr import generate_qr

app = Flask(__name__)

@app.route("/")
def index():
    patients = fetch_all_patients()
    return render_template("index.html", patients=patients)

@app.route("/generate", methods=["POST"])
def generate():
    patient_id = request.form.get("patient_id")

    # 1. Fetch IPS data
    ips_data = fetch_ips(patient_id)

    # 2. Fetch DICOM images
    images = download_patient_images(patient_id, ips_data["imaging"])

    # 3. Build HTML report
    report_path = f"output/{patient_id}_summary.html"
    build_report(ips_data, images, output_path=report_path)

    # 4. Build FHIR bundle with embedded images
    fhir_path = f"output/{patient_id}_fhir.json"
    build_fhir_bundle(ips_data, images, output_path=fhir_path)

    # 5. Generate QR code pointing to the report URL
    report_url = f"http://localhost:5000/report/{patient_id}"
    qr_path = f"output/{patient_id}_qr.png"
    generate_qr(report_url, output_path=qr_path)

    return redirect(url_for("result", patient_id=patient_id))

@app.route("/result/<patient_id>")
def result(patient_id):
    patient_name = patient_id
    try:
        patient = fetch_patient(patient_id)
        name = patient.get("name", [{}])[0]
        patient_name = f"{name.get('given', [''])[0]} {name.get('family', '')}".strip()
    except:
        pass

    return render_template("result.html",
        patient_id=patient_id,
        patient_name=patient_name,
        report_url=f"/report/{patient_id}",
        qr_url=f"/qr/{patient_id}",
        fhir_url=f"/fhir/{patient_id}"
    )

@app.route("/report/<patient_id>")
def report(patient_id):
    path = f"output/{patient_id}_summary.html"
    if os.path.exists(path):
        return send_file(path)
    return "Report not found", 404

@app.route("/fhir/<patient_id>")
def fhir(patient_id):
    path = f"output/{patient_id}_fhir.json"
    if os.path.exists(path):
        return send_file(
            path,
            mimetype="application/fhir+json",
            as_attachment=True,
            download_name=f"DIPS_{patient_id}.json"
        )
    return "FHIR bundle not found", 404

@app.route("/qr/<patient_id>")
def qr(patient_id):
    path = f"output/{patient_id}_qr.png"
    if os.path.exists(path):
        return send_file(path, mimetype="image/png")
    return "QR not found", 404

if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)
    os.makedirs("output/images", exist_ok=True)
    app.run(debug=True, port=5000)
