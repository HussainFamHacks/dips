from flask import Flask, render_template, request, send_file, redirect, url_for
import os

from fetch_ips import fetch_ips, fetch_all_patients, fetch_patient
from fetch_images import download_patient_images
from build_report import build_report
from build_fhir_export import build_fhir_bundle
from generate_qr import generate_qr
from translate import translate_ips, LANGUAGES

app = Flask(__name__)

@app.route("/")
def index():
    patients = fetch_all_patients()
    return render_template("index.html", patients=patients, languages=LANGUAGES)

@app.route("/generate", methods=["POST"])
def generate():
    patient_id = request.form.get("patient_id")
    lang = request.form.get("language", "en")

    # 1. Fetch IPS data
    ips_data = fetch_ips(patient_id)

    # 2. Translate clinical text
    translated_ips = translate_ips(ips_data, lang)

    # 3. Fetch DICOM images
    images = download_patient_images(patient_id, ips_data["imaging"])

    # 4. Build HTML report in chosen language
    report_path = f"output/{patient_id}_{lang}_summary.html"
    build_report(translated_ips, images, output_path=report_path,
                 lang=lang, lang_name=LANGUAGES.get(lang, "English"))

    # 5. Build FHIR bundle
    fhir_path = f"output/{patient_id}_fhir.json"
    build_fhir_bundle(ips_data, images, output_path=fhir_path)

    # 6. Generate QR code
    report_url = f"http://dips.techiemaestro.com/report/{patient_id}/{lang}"
    qr_path = f"output/{patient_id}_{lang}_qr.png"
    generate_qr(report_url, output_path=qr_path)

    return redirect(url_for("result", patient_id=patient_id, lang=lang))

@app.route("/result/<patient_id>")
def result(patient_id):
    lang = request.args.get("lang", "en")
    lang_name = LANGUAGES.get(lang, "English")
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
        lang=lang,
        lang_name=lang_name,
        report_url=f"/report/{patient_id}/{lang}",
        qr_url=f"/qr/{patient_id}/{lang}",
        fhir_url=f"/fhir/{patient_id}"
    )

@app.route("/report/<patient_id>/<lang>")
def report(patient_id, lang):
    path = f"output/{patient_id}_{lang}_summary.html"
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

@app.route("/qr/<patient_id>/<lang>")
def qr(patient_id, lang):
    path = f"output/{patient_id}_{lang}_qr.png"
    if os.path.exists(path):
        return send_file(path, mimetype="image/png")
    return "QR not found", 404

if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)
    os.makedirs("output/images", exist_ok=True)
    app.run(debug=True, port=5000)
