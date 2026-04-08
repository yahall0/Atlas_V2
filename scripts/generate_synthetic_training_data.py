"""Generate a synthetic labelled FIR training corpus for IndicBERT fine-tuning.

Usage
-----
    python scripts/generate_synthetic_training_data.py
    python scripts/generate_synthetic_training_data.py --output_dir data --samples_per_class 30

Output
------
data/
    synthetic_fir_training.csv   -- full corpus (text, category, language, district)
    synthetic_fir_test.csv       -- held-out 20% test split
    label_map.json               -- {"theft": 0, "assault": 1, ...} (sorted alphabetically)

Categories (11): theft, assault, fraud, murder, rape_sexoff, cybercrime,
                 narcotics, kidnapping, dacoity_robbery, domestic_violence, other

Rationale
---------
No annotated FIR data exists at Sprint 3 start.  This script provides a
bootstrapped corpus from template narratives seeded with BNS/IPC section
numbers, Gujarati keywords, and realistic FIR language patterns.  Sprint 4
replaces/augments this with Label Studio-annotated real FIRs.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Narrative templates per category
# Each template supports Python str.format() placeholders:
#   {date}, {place}, {name}, {officer}, {section}, {district}
# ─────────────────────────────────────────────────────────────────────────────

DISTRICTS = [
    "Ahmedabad", "Surat", "Vadodara", "Rajkot", "Bhavnagar",
    "Jamnagar", "Junagadh", "Gandhinagar",
]

PLACES = [
    "Maninagar", "Vastrapur", "Kalupur", "Paldi", "Naranpura",
    "Katargam", "Adajan", "Alkapuri", "Sayajigunj", "Raopura",
    "Bhavnagar Road", "Rajkot Road", "Gondal", "Morbi",
]

NAMES = [
    "Rameshbhai Patel", "Sureshbhai Shah", "Jayaben Desai", "Nilesh Kumar",
    "Priyanka Sharma", "Arjun Singh", "Kavita Ben", "Dinesh Chauhan",
    "Harishbhai Modi", "Fatima Shaikh", "Rajubhai Parmar", "Geeta Devi",
]

OFFICERS = [
    "PI A.K. Sharma", "PSI R.B. Patel", "PI Sunil Dave",
    "ASI Harish Thakor", "PI Nilesh Mehta", "PSI Bharat Solanki",
]

DATES = [
    "01/01/2025", "15/03/2025", "22/06/2025", "10/09/2025",
    "03/11/2025", "28/12/2025", "07/02/2026", "19/04/2026",
]

_TEMPLATES: dict[str, list[str]] = {

    "theft": [
        "ફરિયાદ: {name} એ જણાવ્યું કે {date} ના રોજ {place} ખાતે ઘરનો દરવાજો તોડીને ચોરી કરી. "
        "ઘરમાંથી રોકડ રૂ.50000 અને સોના-ચાંદીના ઘરેણાં ચોરી ગઈ. "
        "ગુન્હો BNS કલમ 303 મુજબ નોંધ્યો. {officer} ની ફરિયાદ.",

        "On {date} at approximately 11 PM, the complainant {name} reported that theft occurred "
        "at {place}. A motorcycle (GJ-01-AB-1234) was stolen from outside the house. "
        "Offence registered under section 379 BNS. Investigating officer: {officer}.",

        "{date} ना दिन {place} में चोरी की घटना हुई। {name} ने बताया कि घर से "
        "नकदी और गहने चोरी हो गए। धारा 380 BNS के तहत मामला दर्ज। {officer} द्वारा जांच।",

        "Complaint filed by {name} on {date}. Unknown persons broke into the shop at {place} "
        "and stole electronic goods worth Rs.2,00,000. Broken locks found. "
        "Case registered under BNS 305 (house-trespass to commit theft). {officer} investigating.",

        "{date} ના રોજ {name} ની સ્કૂટી {place} ની દુકાન સામેથી ચોરી ગઈ. "
        "CCTVમાં અજાણ્યો ઈસમ ભાગતો જોવા મળ્યો. IPC 379 - ચોરી. {officer}.",

        "The complainant {name} stated that on {date} while working at {place}, "
        "his mobile phone (OnePlus, IMEI: 123456789) was snatched by two unknown persons. "
        "Registered under BNS 304 (snatching). Officer: {officer}.",
    ],

    "assault": [
        "{date} ના રોજ {place} ખાતે {name} સાથે ઝઘડો થયો. સામેના ઈસમે ઘૂંસા મારીને "
        "ઈજા પહોંચાડી. BNS 115 (voluntarily causing hurt) મુજબ ગુન્હો. {officer}.",

        "On {date}, {name} was assaulted by a group of four persons at {place}. "
        "The accused used a stick and caused simple hurt. FIR registered under section 323 IPC. "
        "Complainant taken to Civil Hospital. Investigating officer {officer}.",

        "{date} को {place} में {name} पर हमला किया गया। चार व्यक्तियों ने लाठी से प्रहार किया। "
        "धारा 324 BNS के अंतर्गत मामला। पुलिस जांच जारी। {officer}.",

        "Complainant {name} states that on {date} at {place} a dispute over property led to "
        "a physical altercation. Accused caused grievous hurt using iron rod. "
        "Sections 326 BNS invoked. {officer} on case.",

        "{name} એ {date} ના રોજ ફરિયાદ નોંધાવી. {place} ની ગલ્લી ઝઘડામાં ધારદાર હથિયારથી "
        "ઘા કર્યો. BNS 118 - ગંભીર ઈજા. {officer} ની તપાસ.",

        "On {date} at {place}, a road rage incident escalated into assault. "
        "{name} was punched and kicked by two persons. Ribs fractured. "
        "Case under BNS 116 (voluntarily causing grievous hurt). Arrested under {officer}.",
    ],

    "fraud": [
        "{name} ને {date} ના રોજ ફોન આવ્યો. સામેના ઈસમે બેન્ક KYC અપડેટ બહાને "
        "ઓટીપી લઈ ખાતામાંથી રૂ.1,20,000 ઉપાડ્યા. IPC 420 - છેતરપિંડી. {officer}.",

        "The complainant {name} on {date} fell victim to a cheating scheme at {place}. "
        "A fake property dealer collected Rs.5,00,000 advance for a flat that did not exist. "
        "FIR under sections 417 and 420 IPC. Officer: {officer}.",

        "{date} को {name} ने शिकायत की कि {place} में एक व्यक्ति ने नौकरी दिलाने के नाम पर "
        "रु.3,00,000 ठग लिए। धारा 420 IPC के तहत FIR। {officer}.",

        "Complainant {name} reported on {date} that accused posed as a government official "
        "and collected Rs.15,000 as bribe for a certificate at {place}. "
        "Sections 419, 420 BNS filed. {officer}.",

        "{name} એ {date} ના રોજ જણાવ્યું: {place} ના ઈ-કોમર્સ સ્કૅમ થઈ. "
        "ઓનલાઈન ઓર્ડર કર્યા બાદ ખાલી ડબ્બો આવ્યો. BNS 316 - fraud. {officer}.",

        "On {date}, {name} was defrauded of Rs.8,000 through a lottery scam at {place}. "
        "The accused claimed {name} had won a prize and demanded tax payment. "
        "FIR under section 420 IPC filed by {officer}.",
    ],

    "murder": [
        "{date} ના રોજ {place} ખાતે {name} ની હત્યા થઈ. ધારદાર હથિયારથી ગળે ઘા કર્યો. "
        "શરીર ખળામાં મળ્યું. IPC 302 - murder. {officer} ની FIR.",

        "On {date} at {place}, deceased {name} was found with fatal stab wounds. "
        "Post-mortem report confirms homicide. Suspect identified. "
        "FIR registered under BNS 101 (murder). Investigating officer: {officer}.",

        "{date} को {place} में {name} की हत्या की गई। धारदार हथियार से हमला। "
        "धारा 302 IPC के तहत मामला दर्ज। संदिग्ध गिरफ्तार। {officer}.",

        "Informant {name} reported on {date} that at {place} an unidentified body was found "
        "with multiple gunshot wounds. Identity being established. "
        "Case under BNS 101. {officer} leading investigation.",

        "{name} ની {date} ઘરના ઓરડામાં ચીસ સૅ ઘટના. ખૂનને IPC 302 મુજબ ઈ-FIR. "
        "ઘટનાસ્થળ {place}. {officer}.",

        "On {date}, {name} and the accused had an altercation at {place} over a land dispute "
        "which ended in the accused striking {name} with a stone repeatedly causing death. "
        "Murder charge under BNS 103. {officer}.",
    ],

    "rape_sexoff": [
        "ભોગ બનનારે (ઓળઘ ગોપ) {date} ના રોજ ફરિયાદ: {place} ખાતે અજાણ્યા ઈસમ "
        "દ્વારા જાતીય સતામણી. BNS 75 - sexual harassment. {officer}.",

        "The survivor (identity protected under BNS 73) filed a complaint on {date}. "
        "The accused, known to the family, committed the offence at {place}. "
        "FIR under BNS 63 (rape). Survivor medically examined. Officer: {officer}.",

        "{date} को {place} में एक पीड़िता (नाम गोपनीय) ने रिपोर्ट दर्ज कराई। "
        "धारा 376 IPC के तहत मामला। {officer} द्वारा जांच।",

        "Complaint filed on {date}. Survivor (minor, age 15) at {place} assaulted by "
        "a neighbour. Case registered under POCSO Act Section 6 and BNS 65. {officer}.",

        "ઓળઘ ગોપ ફરિયાદી {date} ના રોજ {place}. BNS 77 - stalking, BNS 79 - voyeurism. "
        "ઈ-ફ.ર.ઈ. {officer}.",

        "Survivor lodged complaint on {date} at {place} police station. "
        "The accused sent obscene messages and threatened the survivor. "
        "FIR registered under BNS 79, BNS 73 prohibition applied. {officer}.",
    ],

    "cybercrime": [
        "{name} ના ફોન પર {date} ફિશિંગ મૅસૅજ આવ્યો. OTP આપ્યા પછી ખાતામાંથી ચોરી. "
        "IT Act 66C, 66D - cyber fraud. {officer}.",

        "On {date}, {name} reported that their social media account was hacked at {place}. "
        "The accused used the account to send fake loan messages. "
        "FIR under IT Act Section 66C. {officer}.",

        "{date} को {name} ने साइबर धोखाधड़ी की शिकायत दर्ज कराई। "
        "ऑनलाइन बैंकिंग से रु.78,000 का नुकसान। IT Act 66D। {officer}.",

        "Complainant {name} on {date} received a call from unknown person pretending to be "
        "bank officer and obtained the OTP. Rs.45,000 debited. "
        "Cybercrime FIR under IT Act 66C filed by {officer}.",

        "{name} ને {date} ઓનલાઈન ગ્રૂમ. ખૉટી ઓળઘ આપી ₹2.5 લાખ ઉઘડ. "
        "IT Act 66D + BNS 316. {place}. {officer}.",

        "On {date}, {name} found that fake e-commerce website at {place} (online) "
        "collected payment but never delivered goods. IP traced. "
        "IT Act 66 registered. Cyber cell {officer}.",
    ],

    "narcotics": [
        "{date} ના રોજ {place} ખાતે {name} ની ઝડ્ઘ. 200gm ગાંજો અને 10gm સ્મૅક "
        "જ½ સ્ઘ. NDPS Act 20, 21 - ડ્ ˛ . {officer}.",

        "On {date} at {place}, accused {name} was apprehended in possession of 500 grams "
        "of cannabis (ganja) and drug paraphernalia. "
        "FIR under NDPS Act Section 20(b). Officer: {officer}.",

        "{date} को {place} में {name} के पास से 5 ग्राम हेरोइन बरामद। "
        "NDPS Act धारा 21 के तहत गिरफ्तार। {officer}.",

        "Acting on tipoff on {date}, police raided {place} and arrested {name}. "
        "Recovered: 2kg ganja, 50ml liquor (illicit). "
        "NDPS Act 20(b)(ii), Gujarat Prohibition Act invoked. {officer}.",

        "{date}. {place} ચૅક-નૅ{officer} ½ {name} ½ ¼ (¼¼¼¼¼). "
        "NDPS Act 21. ½ ½ ½.",

        "Recovery memo dated {date}: {name} arrested at {place} with brown sugar (smack) "
        "weighing 3.2 grams, valued at approx Rs.32,000. "
        "NDPS Section 21(a). Arrested by {officer}.",
    ],

    "kidnapping": [
        "{date} ณ {place} ½ {name} ½ ³ ³ ³. "
        "BNS 137 - kidnapping. {officer}.",

        "On {date}, {name} (age 8) went missing from {place}. "
        "Witness saw a white van take the child. "
        "FIR registered under BNS 137 (kidnapping from lawful guardianship). {officer}.",

        "{date} को {place} से {name} का अपहरण। मांग पत्र मिला। "
        "धारा 363 IPC, 365 IPC। {officer} जांच में।",

        "Complainant {name} reported on {date} that her daughter was lured away "
        "by the accused from {place} with intent to marry. "
        "Sections 366 IPC (kidnapping for marriage). {officer}.",

        "{name} ½ {date} {place} ½ ³ ³ ³ ³ ³. "
        "BNS 140 (abduction). {officer}.",

        "A ransom call was received by {name} on {date}. The accused had abducted "
        "the son from {place}. Rs.10 lakh demanded. "
        "FIR under BNS 140 abduction + BNS 308 (extortion). {officer}.",
    ],

    "dacoity_robbery": [
        "{date} ½ {place} ½ {name} ½ ½ ½ ½. "
        "BNS 309 - robbery. {officer}.",

        "On {date}, five armed men entered the jewellery shop at {place}. "
        "They threatened {name} at gunpoint and fled with gold worth Rs.30 lakh. "
        "FIR under BNS 310 (robbery) and BNS 311 (dacoity). {officer}.",

        "{date} को {place} में डकैती। पांच व्यक्तियों ने {name} के घर में घुसकर "
        "3 लाख नकद और गहने लूटे। धारा 395 IPC। {officer}.",

        "Bank robbery reported on {date} at {place}. Armed gang of 6 held "
        "{name} and bank staff at gunpoint. Rs.15 lakh stolen. "
        "Sections 395, 396 IPC (dacoity). ATS and {officer} on case.",

        "{name} ½ {date} {place} ½ ½ ½ ½. "
        "BNS 312 - ½ robbery/dacoity. {officer}.",

        "Complainant {name} on {date}: at {place} a group on two bikes snatched gold chain "
        "and assaulted to prevent resistance. Robbery with hurt. "
        "BNS 309 proviso (grievous hurt). {officer}.",
    ],

    "domestic_violence": [
        "{name} ½ {date}  {place} ½ ½ ½ ½ ½. "
        "IPC 498A - ½ ½ ½. {officer}.",

        "On {date}, complainant {name} filed complaint against husband and in-laws at {place}. "
        "Physical abuse and demands for additional dowry. "
        "FIR under section 498A IPC and Domestic Violence Act. {officer}.",

        "{date} को {name} ने {place} में घरेलू हिंसा की शिकायत दर्ज कराई। "
        "पति और सास ने दहेज के लिए प्रताड़ित किया। धारा 498A, 406 IPC। {officer}.",

        "Complainant {name} appeared at {place} police station on {date}. "
        "Sustained injuries on arms and face. Husband refused medical care. "
        "DV Act Section 3, IPC 323 filed. {officer}.",

        "{name} ½ {date} ½ ½ ½ ½ 498A ½. "
        "{place}. {officer}.",

        "On {date}, protection order sought by {name} at {place}. "
        "History of mental cruelty and economic abuse by husband. "
        "FIR under BNS 85 (cruelty by husband or relatives) and PWDVA. {officer}.",
    ],

    "other": [
        "{date} ½ {place} ½ {name} ½ ½ ½ ½. "
        "BNS  ½ ½ ½ ½. {officer}.",

        "On {date}, {name} filed a miscellaneous complaint at {place} police station. "
        "Two neighbours had a dispute over boundary wall leading to verbal altercation. "
        "Preventive action taken under Section 151 CrPC. {officer}.",

        "{date} को {place} में {name} ने शिकायत दर्ज कराई। विवाद। "
        "धारा 107 CrPC के तहत कार्रवाई। {officer}.",

        "Complaint on {date} regarding nuisance at {place}. "
        "{name} alleges neighbour plays loud music nightly causing disturbance. "
        "Action under IPC 268 (public nuisance) and local municipal act. {officer}.",

        "{name} ½ {date} ½ ½ ½ ½. {place}. "
        "½ ½ ½ ½. {officer}.",

        "Found dead body of unknown male at {place} on {date}. "
        "No injuries visible. Inquest drawn. "
        "Registered as unnatural death under Section 174 CrPC. {officer}.",
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# Language tags for metadata
# ─────────────────────────────────────────────────────────────────────────────

def _detect_lang(text: str) -> str:
    """Simple heuristic: check for Gujarati Unicode block."""
    for ch in text:
        cp = ord(ch)
        if 0x0A80 <= cp <= 0x0AFF:
            return "gu"
        if 0x0900 <= cp <= 0x097F:
            return "hi"
    return "en"


# ─────────────────────────────────────────────────────────────────────────────
# Generator
# ─────────────────────────────────────────────────────────────────────────────

def generate_corpus(
    samples_per_class: int = 30,
    seed: int = 42,
) -> list[dict]:
    """Return a list of row dicts: text, category, language, district."""
    rng = random.Random(seed)
    rows: list[dict] = []

    for category, templates in _TEMPLATES.items():
        generated = 0
        template_pool = list(templates)

        while generated < samples_per_class:
            tmpl = rng.choice(template_pool)
            text = tmpl.format(
                name=rng.choice(NAMES),
                date=rng.choice(DATES),
                place=rng.choice(PLACES),
                officer=rng.choice(OFFICERS),
                section="",
                district=rng.choice(DISTRICTS),
            )
            rows.append(
                {
                    "text": text.strip(),
                    "category": category,
                    "language": _detect_lang(text),
                    "district": rng.choice(DISTRICTS),
                }
            )
            generated += 1

    rng.shuffle(rows)
    return rows


def split_and_write(
    rows: list[dict],
    output_dir: Path,
    test_fraction: float = 0.2,
    seed: int = 42,
) -> None:
    """Write train CSV, test CSV, and label_map JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)
    shuffled = rows[:]
    rng.shuffle(shuffled)
    split = int(len(shuffled) * (1 - test_fraction))
    train_rows = shuffled[:split]
    test_rows = shuffled[split:]

    fieldnames = ["text", "category", "language", "district"]
    for fname, subset in [
        ("synthetic_fir_training.csv", train_rows),
        ("synthetic_fir_test.csv", test_rows),
    ]:
        path = output_dir / fname
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(subset)
        print(f"  Wrote {len(subset):4d} rows → {path}")

    # label_map: alphabetically sorted category -> int
    categories = sorted({r["category"] for r in rows})
    label_map = {cat: i for i, cat in enumerate(categories)}
    lm_path = output_dir / "label_map.json"
    lm_path.write_text(json.dumps(label_map, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Wrote label_map  → {lm_path}")
    print(f"\nCategories ({len(label_map)}): {list(label_map.keys())}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate synthetic FIR training data for IndicBERT fine-tuning."
    )
    parser.add_argument(
        "--output_dir",
        default="data",
        help="Directory to write CSV and JSON files (default: data/)",
    )
    parser.add_argument(
        "--samples_per_class",
        type=int,
        default=30,
        help="Number of examples per crime category (default: 30)",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    print(f"Generating {args.samples_per_class} samples × 11 categories …")
    corpus = generate_corpus(samples_per_class=args.samples_per_class, seed=args.seed)
    print(f"Total rows before split: {len(corpus)}")
    split_and_write(corpus, Path(args.output_dir), seed=args.seed)
    print("\nDone.")
