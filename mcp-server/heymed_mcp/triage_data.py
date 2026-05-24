"""
Pharmacist triage question trees and symptom-to-recommendation logic.
Guides pharmacists through structured patient assessment.
"""

TRIAGE_TREES: dict[str, dict] = {
    "headache": {
        "initial_symptom": "headache",
        "questions": [
            {"id": "severity", "question": "How severe is the headache? (mild/moderate/severe)", "type": "choice", "options": ["mild", "moderate", "severe"]},
            {"id": "duration", "question": "How long have you had the headache?", "type": "choice", "options": ["just started", "few hours", "1-2 days", "more than 3 days"]},
            {"id": "fever", "question": "Do you have a fever?", "type": "yes_no"},
            {"id": "stiff_neck", "question": "Do you have a stiff neck?", "type": "yes_no"},
            {"id": "vision", "question": "Any vision changes or sensitivity to light?", "type": "yes_no"},
            {"id": "nausea", "question": "Any nausea or vomiting?", "type": "yes_no"},
            {"id": "head_injury", "question": "Any recent head injury?", "type": "yes_no"},
        ],
        "red_flags": {
            "stiff_neck": "REFER TO DOCTOR: Stiff neck + headache may indicate meningitis",
            "head_injury": "REFER TO DOCTOR: Head injury requires medical evaluation",
            "vision": "REFER TO DOCTOR: Vision changes with headache may indicate serious condition",
        },
        "refer_if": ["severity=severe AND duration=more than 3 days", "stiff_neck=yes", "head_injury=yes"],
    },
    "fever": {
        "initial_symptom": "fever",
        "questions": [
            {"id": "temperature", "question": "What is the temperature? (in °C or °F)", "type": "number"},
            {"id": "duration", "question": "How long have you had the fever?", "type": "choice", "options": ["just started", "1-2 days", "3-5 days", "more than 5 days"]},
            {"id": "cough", "question": "Do you have a cough?", "type": "yes_no"},
            {"id": "sore_throat", "question": "Do you have a sore throat?", "type": "yes_no"},
            {"id": "body_aches", "question": "Any body aches or muscle pain?", "type": "yes_no"},
            {"id": "rash", "question": "Do you have any rash?", "type": "yes_no"},
            {"id": "breathing", "question": "Any difficulty breathing?", "type": "yes_no"},
        ],
        "red_flags": {
            "breathing": "REFER TO DOCTOR: Difficulty breathing requires immediate medical attention",
            "rash": "REFER TO DOCTOR: Fever with rash needs medical evaluation",
        },
        "refer_if": ["duration=more than 5 days", "breathing=yes", "temperature>40"],
    },
    "cough": {
        "initial_symptom": "cough",
        "questions": [
            {"id": "type", "question": "Is the cough dry or productive (with phlegm)?", "type": "choice", "options": ["dry", "productive"]},
            {"id": "duration", "question": "How long have you had the cough?", "type": "choice", "options": ["few days", "1-2 weeks", "more than 2 weeks"]},
            {"id": "phlegm_color", "question": "If productive, what color is the phlegm?", "type": "choice", "options": ["clear/white", "yellow/green", "brown/rust", "blood-tinged", "N/A"]},
            {"id": "fever", "question": "Do you have a fever?", "type": "yes_no"},
            {"id": "shortness_breath", "question": "Any shortness of breath?", "type": "yes_no"},
            {"id": "wheezing", "question": "Any wheezing?", "type": "yes_no"},
            {"id": "chest_pain", "question": "Any chest pain?", "type": "yes_no"},
        ],
        "red_flags": {
            "chest_pain": "REFER TO DOCTOR: Chest pain with cough needs immediate evaluation",
            "shortness_breath": "REFER TO DOCTOR: Shortness of breath may indicate pneumonia or asthma",
        },
        "refer_if": ["phlegm_color=blood-tinged", "duration=more than 2 weeks", "chest_pain=yes"],
    },
    "stomach pain": {
        "initial_symptom": "stomach pain",
        "questions": [
            {"id": "location", "question": "Where is the pain? (upper/lower/all over)", "type": "choice", "options": ["upper", "lower right", "lower left", "all over", "around navel"]},
            {"id": "severity", "question": "How severe? (mild/moderate/severe)", "type": "choice", "options": ["mild", "moderate", "severe"]},
            {"id": "duration", "question": "How long have you had the pain?", "type": "choice", "options": ["just started", "few hours", "1-2 days", "more than 3 days"]},
            {"id": "nausea", "question": "Any nausea or vomiting?", "type": "yes_no"},
            {"id": "diarrhea", "question": "Any diarrhea?", "type": "yes_no"},
            {"id": "blood_stool", "question": "Any blood in stool?", "type": "yes_no"},
            {"id": "eating", "question": "Does eating make it better or worse?", "type": "choice", "options": ["better", "worse", "no change"]},
        ],
        "red_flags": {
            "blood_stool": "REFER TO DOCTOR: Blood in stool requires medical evaluation",
        },
        "refer_if": ["blood_stool=yes", "severity=severe AND location=lower right"],
    },
    "allergy": {
        "initial_symptom": "allergy symptoms",
        "questions": [
            {"id": "symptoms", "question": "What symptoms? (select all)", "type": "multi", "options": ["sneezing", "runny nose", "itchy eyes", "watery eyes", "skin rash/hives", "swelling"]},
            {"id": "duration", "question": "How long have you had these symptoms?", "type": "choice", "options": ["just started", "few days", "seasonal/recurring", "chronic"]},
            {"id": "trigger", "question": "Any known trigger? (pollen, dust, food, pet, medication)", "type": "text"},
            {"id": "breathing", "question": "Any difficulty breathing or throat swelling?", "type": "yes_no"},
            {"id": "severity", "question": "How severe? (mild/moderate/severe)", "type": "choice", "options": ["mild", "moderate", "severe"]},
        ],
        "red_flags": {
            "breathing": "EMERGENCY: Throat swelling/breathing difficulty may indicate anaphylaxis. Call emergency services!",
        },
        "refer_if": ["breathing=yes", "symptoms=swelling"],
    },
    "skin issue": {
        "initial_symptom": "skin problem",
        "questions": [
            {"id": "type", "question": "What does it look like? (rash, spots, dry/flaky, blisters, fungal)", "type": "choice", "options": ["rash/redness", "spots/pimples", "dry/flaky", "blisters", "ring-shaped/fungal", "insect bite"]},
            {"id": "location", "question": "Where on the body?", "type": "text"},
            {"id": "itch", "question": "Is it itchy?", "type": "yes_no"},
            {"id": "duration", "question": "How long have you had it?", "type": "choice", "options": ["just started", "few days", "1-2 weeks", "more than 2 weeks"]},
            {"id": "spreading", "question": "Is it spreading?", "type": "yes_no"},
            {"id": "fever", "question": "Do you have a fever?", "type": "yes_no"},
        ],
        "red_flags": {
            "fever": "REFER TO DOCTOR: Skin issue + fever may indicate infection",
        },
        "refer_if": ["fever=yes AND spreading=yes"],
    },
    "eye problem": {
        "initial_symptom": "eye problem",
        "questions": [
            {"id": "symptoms", "question": "What symptoms? (redness, itching, discharge, pain, blurry vision)", "type": "multi", "options": ["redness", "itching", "discharge", "pain", "blurry vision", "dry/gritty"]},
            {"id": "one_or_both", "question": "One eye or both?", "type": "choice", "options": ["one eye", "both eyes"]},
            {"id": "duration", "question": "How long?", "type": "choice", "options": ["just started", "few days", "more than a week"]},
            {"id": "contact_lenses", "question": "Do you wear contact lenses?", "type": "yes_no"},
            {"id": "injury", "question": "Any recent eye injury or chemical exposure?", "type": "yes_no"},
        ],
        "red_flags": {
            "injury": "REFER TO DOCTOR: Eye injury/chemical exposure needs immediate medical attention",
        },
        "refer_if": ["injury=yes", "symptoms=pain AND symptoms=blurry vision"],
    },
}

SYMPTOM_DRUG_MAP: dict[str, dict] = {
    "headache": {
        "mild": {"drugs": ["acetaminophen"], "notes": "Start with paracetamol. Avoid NSAIDs if stomach issues."},
        "moderate": {"drugs": ["acetaminophen", "ibuprofen"], "notes": "Combine paracetamol + ibuprofen if single agent insufficient."},
        "severe": {"drugs": ["ibuprofen", "naproxen"], "notes": "Severe/persistent headache — consider referral if no improvement in 48h."},
        "with_fever": {"drugs": ["acetaminophen", "ibuprofen"], "notes": "Treat both pain and fever."},
    },
    "fever": {
        "default": {"drugs": ["acetaminophen", "ibuprofen"], "notes": "Alternate paracetamol and ibuprofen every 3-4 hours if needed."},
        "with_cough": {"drugs": ["acetaminophen", "dextromethorphan", "guaifenesin"], "notes": "Add cough suppressant if dry cough, or expectorant if productive."},
        "with_sore_throat": {"drugs": ["acetaminophen", "benzocaine"], "notes": "Paracetamol for fever + throat lozenge for local relief."},
        "with_body_aches": {"drugs": ["ibuprofen", "acetaminophen"], "notes": "NSAID preferred for body aches if no contraindications."},
    },
    "cough": {
        "dry": {"drugs": ["dextromethorphan"], "notes": "Cough suppressant for dry, non-productive cough."},
        "productive": {"drugs": ["guaifenesin"], "notes": "Expectorant to help clear mucus. Increase fluid intake."},
        "with_congestion": {"drugs": ["pseudoephedrine", "guaifenesin"], "notes": "Decongestant + expectorant. Avoid pseudoephedrine if hypertension."},
    },
    "stomach pain": {
        "upper_worse_eating": {"drugs": ["omeprazole", "famotidine"], "notes": "Likely acid-related. PPI or H2 blocker before meals."},
        "upper_better_eating": {"drugs": ["famotidine", "calcium carbonate"], "notes": "May be gastritis. Antacid for immediate relief."},
        "with_nausea": {"drugs": ["bismuth subsalicylate", "dimenhydrinate"], "notes": "Anti-nausea medication. Avoid solid food temporarily."},
        "with_diarrhea": {"drugs": ["loperamide", "bismuth subsalicylate"], "notes": "Anti-diarrheal. Maintain hydration with ORS."},
    },
    "allergy": {
        "mild": {"drugs": ["cetirizine", "loratadine"], "notes": "Non-drowsy antihistamine for mild symptoms."},
        "moderate": {"drugs": ["cetirizine", "fexofenadine"], "notes": "Second-gen antihistamine. Add nasal spray if congestion."},
        "eye_symptoms": {"drugs": ["ketotifen", "olopatadine"], "notes": "Antihistamine eye drops for itchy/watery eyes."},
        "skin_rash": {"drugs": ["cetirizine", "hydrocortisone"], "notes": "Oral antihistamine + topical steroid for skin symptoms."},
    },
    "skin issue": {
        "itch_rash": {"drugs": ["hydrocortisone", "cetirizine", "calamine"], "notes": "Topical steroid + oral antihistamine for itch relief."},
        "fungal": {"drugs": ["clotrimazole", "miconazole", "terbinafine"], "notes": "Antifungal cream. Apply for 2-4 weeks even if symptoms improve."},
        "dry_skin": {"drugs": ["emollient", "hydrocortisone"], "notes": "Moisturizer first. Low-potency steroid if inflamed."},
        "acne": {"drugs": ["benzoyl peroxide", "salicylic acid"], "notes": "Start with benzoyl peroxide 2.5%. Increase if tolerated."},
    },
}

PATIENT_CONTEXT_QUESTIONS = [
    {"id": "age", "question": "How old is the patient?", "type": "number"},
    {"id": "pregnant", "question": "Is the patient pregnant or breastfeeding?", "type": "yes_no"},
    {"id": "allergies", "question": "Any known drug allergies?", "type": "text"},
    {"id": "current_meds", "question": "What medications are they currently taking?", "type": "text"},
    {"id": "conditions", "question": "Any chronic conditions? (diabetes, hypertension, asthma, kidney disease, liver disease)", "type": "text"},
]


def get_triage_tree(symptom: str) -> dict | None:
    key = symptom.lower().strip()
    for tree_key, tree in TRIAGE_TREES.items():
        if key in tree_key or tree_key in key:
            return tree
    return None


def get_available_symptoms() -> list[str]:
    return list(TRIAGE_TREES.keys())
