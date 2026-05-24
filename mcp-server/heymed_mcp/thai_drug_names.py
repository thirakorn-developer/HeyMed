"""
Thai drug name mapping: Thai → English generic name.
Covers common drugs used in Thailand pharmacies.

Categories:
- Thai generic names (ชื่อสามัญ)
- Thai brand names popular in Thailand
- Thai transliterations (ทับศัพท์)
- Common Thai abbreviations and slang
"""

THAI_TO_ENGLISH: dict[str, str] = {
    # ── ยาแก้ปวด / ลดไข้ (Analgesics / Antipyretics) ──
    "พาราเซตามอล": "acetaminophen",
    "พารา": "acetaminophen",
    "ยาพารา": "acetaminophen",
    "อะเซตามิโนเฟน": "acetaminophen",
    "ไทลินอล": "acetaminophen",  # Tylenol
    "ซาร่า": "acetaminophen",  # Sara brand
    "เทมป์ร่า": "acetaminophen",  # Tempra brand
    "ไอบูโพรเฟน": "ibuprofen",
    "บรูเฟน": "ibuprofen",  # Brufen brand
    "แอดวิล": "ibuprofen",  # Advil
    "นูโรเฟน": "ibuprofen",  # Nurofen
    "ยาแก้ปวด": "acetaminophen",
    "ยาลดไข้": "acetaminophen",
    "แอสไพริน": "aspirin",
    "ยาต้านการอักเสบ": "ibuprofen",
    "นาพร็อกเซน": "naproxen",
    "ไดโคลฟีแนค": "diclofenac",
    "โวลทาเรน": "diclofenac",  # Voltaren brand
    "เมโลซิแคม": "meloxicam",
    "เซเลบร็อกซ์": "celecoxib",  # Celebrex brand
    "ทรามาดอล": "tramadol",

    # ── ยาปฏิชีวนะ (Antibiotics) ──
    "อะม็อกซิซิลลิน": "amoxicillin",
    "อะม็อกซี่": "amoxicillin",
    "ยาอะม็อกซี่": "amoxicillin",
    "ออกเมนติน": "amoxicillin",  # Augmentin (amox+clav)
    "อะซิโธรมัยซิน": "azithromycin",
    "ซิโธรแมกซ์": "azithromycin",  # Zithromax
    "เซฟาเล็กซิน": "cephalexin",
    "ซิโปรฟล็อกซาซิน": "ciprofloxacin",
    "ด็อกซีไซคลิน": "doxycycline",
    "อิริโธรมัยซิน": "erythromycin",
    "เมโทรนิดาโซล": "metronidazole",
    "แฟลกซิล": "metronidazole",  # Flagyl brand
    "ยาฆ่าเชื้อ": "amoxicillin",
    "ยาแก้อักเสบ": "amoxicillin",
    "คลาริโธรมัยซิน": "clarithromycin",
    "ลีโวฟล็อกซาซิน": "levofloxacin",
    "โคอะม็อกซิคลาฟ": "amoxicillin",  # co-amoxiclav

    # ── ยาแก้แพ้ / ยาภูมิแพ้ (Antihistamines) ──
    "เซทิริซีน": "cetirizine",
    "ยาแก้แพ้": "cetirizine",
    "ลอราทาดีน": "loratadine",
    "คลาริทีน": "loratadine",  # Claritin
    "เฟกโซเฟนาดีน": "fexofenadine",
    "คลอเฟนิรามีน": "chlorpheniramine",
    "ซีพีเอ็ม": "chlorpheniramine",  # CPM abbreviation
    "ไดเฟนไฮดรามีน": "diphenhydramine",

    # ── ยาแก้ไอ / หวัด (Cough & Cold) ──
    "ยาแก้ไอ": "dextromethorphan",
    "เด็กซ์โทรเมทอร์แฟน": "dextromethorphan",
    "ไกวเฟเนซิน": "guaifenesin",
    "ยาละลายเสมหะ": "guaifenesin",
    "ซูโดอีเฟดรีน": "pseudoephedrine",
    "ยาลดน้ำมูก": "pseudoephedrine",
    "ฟีนิลเอฟรีน": "phenylephrine",
    "บรอมเฮกซีน": "bromhexine",

    # ── ยาโรคกระเพาะ (Gastrointestinal) ──
    "โอเมพราโซล": "omeprazole",
    "ยาลดกรด": "omeprazole",
    "แลนโซพราโซล": "lansoprazole",
    "แพนโทพราโซล": "pantoprazole",
    "ฟาโมทิดีน": "famotidine",
    "รานิทิดีน": "ranitidine",
    "อะลูมิเนียมไฮดรอกไซด์": "aluminum hydroxide",
    "ยาเคลือบกระเพาะ": "aluminum hydroxide",
    "โลเพอราไมด์": "loperamide",
    "ยาแก้ท้องเสีย": "loperamide",
    "ดอมเพอริโดน": "domperidone",
    "ยาแก้คลื่นไส้": "domperidone",
    "ไบซาโคดิล": "bisacodyl",
    "ยาระบาย": "bisacodyl",
    "เมทอกโลพราไมด์": "metoclopramide",

    # ── ยาเบาหวาน (Diabetes) ──
    "เมทฟอร์มิน": "metformin",
    "กลูโคฟาจ": "metformin",  # Glucophage brand
    "ไกลพิไซด์": "glipizide",
    "ไกลเบนคลาไมด์": "glyburide",
    "ไกลเมพิไรด์": "glimepiride",
    "ยาเบาหวาน": "metformin",
    "อินซูลิน": "insulin",

    # ── ยาความดัน / หัวใจ (Cardiovascular) ──
    "อะมโลดิปีน": "amlodipine",
    "เอนาลาพริล": "enalapril",
    "ลิซิโนพริล": "lisinopril",
    "ยาความดัน": "amlodipine",
    "โลซาร์แทน": "losartan",
    "วาลซาร์แทน": "valsartan",
    "อะทีโนลอล": "atenolol",
    "โพรพราโนลอล": "propranolol",
    "เมโทโพรลอล": "metoprolol",
    "ไฮโดรคลอโรไทอะไซด์": "hydrochlorothiazide",
    "ฟูโรซีไมด์": "furosemide",
    "ลาซิกซ์": "furosemide",  # Lasix brand
    "วาร์ฟาริน": "warfarin",
    "ยาละลายลิ่มเลือด": "warfarin",

    # ── ยาลดไขมัน (Lipid-lowering) ──
    "อะทอร์วาสแตติน": "atorvastatin",
    "ลิปิทอร์": "atorvastatin",  # Lipitor brand
    "ซิมวาสแตติน": "simvastatin",
    "โรซูวาสแตติน": "rosuvastatin",
    "เครสตอร์": "rosuvastatin",  # Crestor
    "ยาลดไขมัน": "atorvastatin",

    # ── ยาทาภายนอก / ยาผิวหนัง (Topical / Dermatology) ──
    "ไฮโดรคอร์ติโซน": "hydrocortisone",
    "ยาทาแก้คัน": "hydrocortisone",
    "โคลไตรมาโซล": "clotrimazole",
    "ยาทาเชื้อรา": "clotrimazole",
    "เทอร์บินาฟีน": "terbinafine",
    "มิโคนาโซล": "miconazole",
    "เบนซอยล์เปอร์ออกไซด์": "benzoyl peroxide",
    "ยาทาสิว": "benzoyl peroxide",
    "กรดซาลิไซลิก": "salicylic acid",
    "คาลามีน": "calamine",

    # ── ยาจิตเวช / ระบบประสาท (Psychiatric / Neurological) ──
    "ฟลูออกซีทีน": "fluoxetine",
    "โปรแซค": "fluoxetine",  # Prozac
    "เซอร์ทราลีน": "sertraline",
    "โซลอฟท์": "sertraline",  # Zoloft
    "อะมิทริปไทลีน": "amitriptyline",
    "ไดอะซีแพม": "diazepam",
    "วาเลียม": "diazepam",  # Valium
    "อัลพราโซแลม": "alprazolam",
    "ฟีนิโทอิน": "phenytoin",
    "คาร์บามาเซพีน": "carbamazepine",
    "กาบาเพนติน": "gabapentin",

    # ── ยาระบบทางเดินหายใจ (Respiratory) ──
    "ซัลบูทามอล": "albuterol",
    "เวนโทลิน": "albuterol",  # Ventolin brand
    "ยาพ่นหอบหืด": "albuterol",
    "มอนเทลูคาสต์": "montelukast",
    "ซิงกูแลร์": "montelukast",  # Singulair
    "ฟลูทิคาโซน": "fluticasone",

    # ── ยาอื่นๆ ที่ใช้บ่อย (Other Common) ──
    "เพรดนิโซโลน": "prednisolone",
    "ยาสเตียรอยด์": "prednisolone",
    "เดกซาเมทาโซน": "dexamethasone",
    "เมลาโทนิน": "melatonin",
    "ยานอนหลับ": "diphenhydramine",
    "มัลติวิตามิน": "multivitamin",
    "ยาบำรุง": "multivitamin",
    "ธาตุเหล็ก": "ferrous sulfate",
    "แคลเซียม": "calcium carbonate",
    "วิตามินซี": "ascorbic acid",
    "วิตามินบี": "vitamin b complex",
    "โฟลิกแอซิด": "folic acid",
    "เมโทเทร็กเสท": "methotrexate",
    "ไทรอยด์": "levothyroxine",
}


def translate_thai_to_english(drug_name: str) -> str | None:
    return THAI_TO_ENGLISH.get(drug_name.strip())


def search_thai_drugs(query: str) -> list[dict]:
    query_lower = query.lower().strip()
    results = []
    for thai, english in THAI_TO_ENGLISH.items():
        if query_lower in thai or query_lower in english.lower():
            results.append({"thai_name": thai, "english_name": english})
    return results
