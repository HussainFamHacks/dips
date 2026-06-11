from deep_translator import GoogleTranslator

LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "pt": "Portuguese",
    "de": "German",
    "it": "Italian",
    "ar": "Arabic",
    "zh-CN": "Chinese (Simplified)",
    "ja": "Japanese",
    "hi": "Hindi",
}

def translate_text(text, target_lang):
    """Translate a string to the target language. Returns original on failure."""
    if not text or target_lang == "en" or text in ("N/A", "Unknown", ""):
        return text
    try:
        return GoogleTranslator(source="auto", target=target_lang).translate(text)
    except Exception as e:
        print(f"Translation failed for '{text}': {e}")
        return text

def translate_ips(ips_data, target_lang):
    """Translate all human-readable clinical text in the IPS data."""
    if target_lang == "en":
        return ips_data

    def t(text):
        return translate_text(text, target_lang)

    # Deep copy so we don't mutate the original
    import copy
    data = copy.deepcopy(ips_data)

    # Conditions
    for c in data.get("conditions", []):
        if "code" in c and "text" in c["code"]:
            c["code"]["text"] = t(c["code"]["text"])
        for site in c.get("bodySite", []):
            if "text" in site:
                site["text"] = t(site["text"])
        for coding in c.get("severity", {}).get("coding", []):
            if "display" in coding:
                coding["display"] = t(coding["display"])

    # Allergies
    for a in data.get("allergies", []):
        if "code" in a and "text" in a["code"]:
            a["code"]["text"] = t(a["code"]["text"])
        for reaction in a.get("reaction", []):
            for mani in reaction.get("manifestation", []):
                if "concept" in mani and "text" in mani["concept"]:
                    mani["concept"]["text"] = t(mani["concept"]["text"])

    # Medications
    for m in data.get("medications", []):
        if "medicationCodeableConcept" in m and "text" in m["medicationCodeableConcept"]:
            m["medicationCodeableConcept"]["text"] = t(m["medicationCodeableConcept"]["text"])

    # Diagnostic Reports
    for r in data.get("reports", []):
        if "code" in r and "text" in r["code"]:
            r["code"]["text"] = t(r["code"]["text"])
        if r.get("conclusion"):
            r["conclusion"] = t(r["conclusion"])

    return data
