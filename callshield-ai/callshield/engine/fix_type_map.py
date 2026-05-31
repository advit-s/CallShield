"""Quick fix: add new scam categories to type_map in scam_nlp.py"""
path = r"C:\Users\advit\OneDrive\Desktop\CallShield\callshield-ai\callshield\engine\scam_nlp.py"
with open(path, "r", encoding="utf-8", newline="\n") as f:
    text = f.read()

old = '"alternate_number_claim": ScamType.ALTERNATE_NUMBER_CLAIM,\n}\n\nreturn type_map.get'
new = '"alternate_number_claim": ScamType.ALTERNATE_NUMBER_CLAIM,\n    "ecommerce_fraud": ScamType.BANK_KYC_FRAUD,\n    "telecom_scam": ScamType.JOB_INVESTMENT_SCAM,\n    "government_impersonation": ScamType.POLICE_LEGAL_THREAT,\n    "finance_scam": ScamType.JOB_INVESTMENT_SCAM,\n}\n\nreturn type_map.get'

if old in text:
    text = text.replace(old, new)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("OK - type_map updated")
else:
    print("NOT FOUND - showing nearby content:")
    idx = text.find("alternate_number_claim")
    print(repr(text[idx-20:idx+120]))
