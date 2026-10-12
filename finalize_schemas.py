"""Turn raw extracted schemas into the dataset config files the backend loads.

Usage: python tools/finalize_schemas.py raw_schemas/ backend/app/datasets/

Applies manual corrections for places where the CBK guide's field tables and its
sample payloads disagree. Every correction is listed in OVERRIDES so it can be
reviewed against CBK's Excel business-rule templates.
"""
import json, glob, os, re, sys

src, dst = sys.argv[1], sys.argv[2]

GROUPS = {
    "Cards": [2, 3, 4, 5, 6],
    "Accounts & Deposits": [8, 9, 15, 34],
    "Customers & Counterparties": [12, 13, 27],
    "Credit & Loans": [11, 21, 22, 28, 40],
    "Treasury & Securities": [16, 29],
    "Forex & Remittances": [17, 18, 32, 44, 45, 46, 47],
    "Cash": [20, 30, 31],
    "Fraud & Complaints": [14, 19, 35, 39],
    "Agents, Merchants & Outlets": [10, 23, 26, 33, 43],
    "Foreign Subsidiaries": [24, 25],
    "Credit Reference Bureau": [7, 36, 37, 38, 41, 42],
}
FREQUENCY = {30: "weekly", 31: "weekly"}

# (dataset number, field-name prefix) -> fixes
OVERRIDES = {
    (7, "BUSINESS REPORTING"): {"name": "BUSINESS REPORTING DAY, MONTH & YEAR"},
    (7, "DAY, MONTH & YEAR CATEGORY"): {"name": "CATEGORY OF NOTICES ISSUED"},
    (10, "BUSINESS DATE"): {"payload_key": "REPORTING DATE"},
    (14, "DATE OF CLOSURE"): {"payload_key": "CLOSURE DATE"},
    (19, "NATURE OF FRAUD"): {"payload_key": "NATURE OF FRAUD"},
    (23, "PHYSICAL LOCATION OF AGENT"): {"payload_key": "SUB COUNTY CODE"},
    (28, "DESCRIPTION OF REASON FOR RESTRUCTURE"): {"payload_key": "RESTRUCTURE REASON"},
    (28, "DATE WHEN THE LOAN WAS RESTRUCTURED"): {"payload_key": "RESTRUCTURED DATE"},
    (28, "DESCRIPTION OF REASON FOR WRITE"): {"payload_key": "WRITE OFF REASON"},
    (28, "DATE WHEN THE LOAN WAS WRITTEN"): {"payload_key": "WRITTEN OFF DOWN DATE"},
}
SPEC_NOTES = {
    8: "The guide gives this dataset the same endpoint as Deposit Contracts (#15). Confirm the correct endpoint with CBK.",
    36: "The guide gives this dataset the Terminals Information endpoint (#26). Confirm the correct endpoint with CBK.",
    41: "The guide gives this dataset the Terminals Information endpoint (#26). Confirm the correct endpoint with CBK.",
}

def slug(s): return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")

def is_required(name):
    n = name.upper()
    return n.startswith("ROW ID") or n.replace("_", " ") == "ROW ID" or "REPORTING" in n and ("DATE" in n or "DAY" in n)

os.makedirs(dst, exist_ok=True)
index = []
for f in sorted(glob.glob(os.path.join(src, "*.json"))):
    d = json.load(open(f))
    n = d["number"]
    fields = []
    for fl in d["fields"]:
        for (num, prefix), fix in OVERRIDES.items():
            if num == n and fl["name"].upper().startswith(prefix):
                fl.update(fix)
        typ = fl["type"]
        nm = fl["name"].upper()
        if typ == "number" and any(w in nm for w in ("NAME", "CODE", "ID ", "NUMBER OF ID", "PASSPORT", "SEQUENCE", "TYPE", "ROW ID")) and not nm.startswith("NUMBER OF") and nm != "ROW ID":
            typ = "string"  # the guide marks some text fields as Number
        if "DATE" in nm and "UPDATE" not in nm and typ != "number":
            typ = "date"
        fields.append({
            "key": slug(fl["name"])[:60],
            "name": fl["name"],
            "payload_key": fl["payload_key"],
            "type": typ,
            "required": is_required(fl["name"]),
            "description": fl["description"],
            "example": fl["example"],
        })
    for extra in d.get("unmatched_sample_keys", []):
        if any(x["payload_key"] == extra for x in fields):
            continue
        fields.append({"key": slug(extra), "name": extra, "payload_key": extra,
                       "type": "date" if "DATE" in extra else "string", "required": False,
                       "description": "Appears in CBK's sample payload but not in the field table.", "example": ""})
    group = next((g for g, nums in GROUPS.items() if n in nums), "Other")
    code = slug(d["title"].replace("(Above 1M)", "above 1m"))[:64]
    out = {
        "number": n, "code": code, "title": d["title"], "group": group,
        "frequency": FREQUENCY.get(n, "periodic"),
        "endpoint": d["endpoint"], "array_key": d["array_key"],
        "notes": SPEC_NOTES.get(n, ""),
        "source_pages": d["source_pages"], "fields": fields,
    }
    json.dump(out, open(os.path.join(dst, f"{n:02d}_{code}.json"), "w"), indent=2, ensure_ascii=False)
    index.append((n, code, len(fields)))
print(len(index), "datasets written")
