import base64
import os
from jinja2 import Environment, FileSystemLoader

def image_to_base64(image_path):
    """Convert image file to base64 string for embedding in HTML"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def build_report(ips_data, images, output_path="output/summary.html", lang="en", lang_name="English"):
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("report.html")

    # Embed images as base64 so the HTML is fully self-contained
    embedded_images = []
    for img in images:
        if img.get("path") and os.path.exists(img["path"]):
            embedded_images.append({
                "data": image_to_base64(img["path"]),
                "modality": img["modality"],
                "study_date": img["study_date"],
            })
        else:
            embedded_images.append({
                "data": None,
                "modality": img.get("modality", "UNKNOWN"),
                "study_date": img.get("study_date", "N/A"),
                "error": img.get("error", "Image unavailable")
            })

    html = template.render(ips=ips_data, images=embedded_images, lang=lang, lang_name=lang_name)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Report saved to {output_path}")
    return output_path
