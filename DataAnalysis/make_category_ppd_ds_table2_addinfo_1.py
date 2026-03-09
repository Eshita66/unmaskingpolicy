
"""
PPD vs DS by Operation (shared / collected) in wide table:
appname | Operation | Location(PPD,DS) | Personal info(PPD,DS) | ...

Adds robust app-name normalization/matching so
"Audiomack_ Music Downloader" == "Audiomack: Music Downloader" == "audiomack music downloader".

Requires:
  pip install xlsxwriter

Relies on your mapping module:
  import category_mapping2 as cm
    - cm.GOOGLE_SCHEMA
    - cm.parse_policy_items_with_trace(policy_dict)
    - cm.parse_label_sections(ds_label_dict)
"""

PPD_JSON_PATH = r"privacify dataset"
DS_JSON_PATH  = r"datsafety dataset"
OUTPUT_XLSX   = r"./ppd_ds_by_operation_addinfo.xlsx"

import json
import os
import sys
import re
import unicodedata
from collections import defaultdict

try:
    import xlsxwriter
except ImportError:
    print("ERROR: xlsxwriter is required. Install with: pip install xlsxwriter")
    sys.exit(1)

# ---- import your mapping module ----
try:
    import category_mapping2 as cm   # change to 'categorymapping' if that's your filename
except Exception as e:
    print("ERROR: Could not import mapping module. Make sure it’s in the same folder (or on PYTHONPATH).")
    print(f"Details: {e}")
    sys.exit(1)

# Exact Excel headers you want
DISPLAY_LABELS = [
    "Location","Personal info","Financial info","Health and fitness","Messages","Photos and videos",
    "Audio","Files and docs","Calendar","Contacts","App activity","Web browsing",
    "App info and performance","Device or other IDs",
]
LABEL_TO_KEY = {
    "Location": "location",
    "Personal info": "personal_info",
    "Financial info": "financial_info",
    "Health and fitness": "health_fitness",
    "Messages": "messages",
    "Photos and videos": "photos_videos",
    "Audio": "audio",
    "Files and docs": "files_docs",
    "Calendar": "calendar",
    "Contacts": "contacts",
    "App activity": "app_activity",
    "Web browsing": "web_browsing",
    "App info and performance": "app_info_perf",
    "Device or other IDs": "device_or_other_ids",
}
DISPLAY_ORDER = [(label, LABEL_TO_KEY[label]) for label in DISPLAY_LABELS if LABEL_TO_KEY[label] in cm.GOOGLE_SCHEMA]


_PUNCT_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)  
_WS_RE    = re.compile(r"\s+")

def strip_emoji(text: str) -> str:
   
    return "".join(ch for ch in text if unicodedata.category(ch) not in {"So"} and not (0x1F300 <= ord(ch) <= 0x1FAFF))

def normalize_app_name(name: str) -> str:
    """
    Normalize names so cosmetic differences don't matter:
    - lowercase
    - unicode NFKC
    - replace separators (:_-·) with spaces
    - map & -> and
    - drop TM/registered and similar symbols
    - remove remaining punctuation
    - collapse whitespace
    """
    if not isinstance(name, str):
        name = str(name or "")
    s = unicodedata.normalize("NFKC", name).lower().strip()

    # Replace common separators with spaces
    s = s.replace("_", " ").replace(":", " ").replace("-", " ").replace("·", " ")

    # Map & to 'and'
    s = re.sub(r"\s*&\s*", " and ", s)

    # Remove trademark-like symbols
    s = s.replace("®", " ").replace("™", " ").replace("©", " ")

    # Strip emoji/symbols
    s = strip_emoji(s)

    # Remove remaining punctuation
    s = _PUNCT_RE.sub(" ", s)

    # Collapse whitespace
    s = _WS_RE.sub(" ", s).strip()

    return s

def title_like(s: str) -> str:
    """Nice fallback for display if we only have normalized form."""
    return " ".join(w.capitalize() for w in s.split())


def load_json(path: str) -> dict:
    if not os.path.exists(path):
        print(f"ERROR: File not found: {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def merge_policy_entries(dst: dict, src: dict) -> dict:
    """
    dst/src like: {"shared":[...], "collected":[...]}
    Merge lists by union (case-sensitive keep as-is), preserve order roughly.
    """
    for op in ("shared", "collected"):
        dst.setdefault(op, [])
        seen = set(dst[op])
        for item in src.get(op, []) or []:
            if item not in seen:
                dst[op].append(item)
                seen.add(item)
    return dst

def merge_ds_entries(dst: dict, src: dict) -> dict:
    """
    dst/src are the raw DS app objects (with "Data shared" / "Data collected" blocks).
    We'll just shallow-merge keys, preferring union of inner dict keys.
    """
    for k in src.keys():
        if k not in dst or not isinstance(dst[k], dict) or not isinstance(src[k], dict):
            dst[k] = src[k]
        else:
            
            for cat, val in src[k].items():
                if cat not in dst[k]:
                    dst[k][cat] = val
                else:
                   
                    pass
    return dst

-
def canon(s: str) -> str:
    """
    Lowercase, trim, and collapse whitespace.
    Prefer the mapping module's `canon` if present to stay consistent.
    """
    try:
        return cm.canon(s) 
    except AttributeError:
        return re.sub(r"\s+", " ", str(s or "").strip().lower())


def index_and_merge_by_normalized_name(raw_map: dict, is_policy: bool):
    """
    Build: norm_name -> {"display_names": set([...]), "data": merged_entry}
    For policy: merged_entry is the {"shared":[...], "collected":[...]} map.
    For DS:     merged_entry is the raw DS object for that app to feed cm.parse_label_sections.
    """
    idx = {}
    for original_name, payload in (raw_map or {}).items():
        norm = normalize_app_name(original_name)
        if norm not in idx:
            idx[norm] = {"display_names": set(), "data": {} if is_policy else {}}
        idx[norm]["display_names"].add(original_name)

        if is_policy:
          
            idx[norm]["data"] = merge_policy_entries(idx[norm]["data"], payload or {})
        else:
          
            idx[norm]["data"] = merge_ds_entries(idx[norm]["data"], payload or {})

    return idx



def compute_rows(policy_summary_raw: dict, data_safety_raw: dict):
    """
    Build:
      - rows: [(display_appname, operation, ppd_map, ds_map)]
      - subtype_rows: list of (app, operation, top_label, matched, ppd_only, ds_only, ppd_subs_all, ds_subs_all)
      - nonconsidered_rows: list of (kind, app, operation, detail_1, detail_2)
          * kind == "policy_non_schematized": detail_1=item_text, detail_2=""
          * kind == "ds_declared_but_unparsed": detail_1=top_label, detail_2=raw_values_compact
    """
    rows = []
    subtype_rows = []
    nonconsidered_rows = []

    # Normalize + merge both maps
    pol_idx = index_and_merge_by_normalized_name(policy_summary_raw, is_policy=True)
    ds_idx  = index_and_merge_by_normalized_name(data_safety_raw,  is_policy=False)

    # Union of all normalized names
    all_norm_names = set(pol_idx.keys()) & set(ds_idx.keys())

    # Reverse lookup for label by key (for pretty printing)
    KEY_TO_LABEL = {v: k for k, v in LABEL_TO_KEY.items()}

    for norm in sorted(all_norm_names):
        pol_entry = pol_idx.get(norm, {})
        ds_entry  = ds_idx.get(norm, {})

        # Choose a nice display name
        ds_names  = ds_entry.get("display_names", set())
        pol_names = pol_entry.get("display_names", set())
        if ds_names:
            display_appname = sorted(ds_names, key=lambda s: (len(s), s.lower()))[0]
        elif pol_names:
            display_appname = sorted(pol_names, key=lambda s: (len(s), s.lower()))[0]
        else:
            display_appname = title_like(norm)

        # Prepare structures
        pol_data = pol_entry.get("data", {}) or {}
        ds_data  = ds_entry.get("data", {}) or {}

        # --- Policy → mapped and trace ---
        mapped, _mapped_strings, non_schematized = cm.parse_policy_items_with_trace(pol_data)
     
        ds_sections = cm.parse_label_sections(ds_data)
       
        for operation in ("shared", "collected"):
            for it in sorted(_mapped_strings.get(operation, [])):
                nonconsidered_rows.append((
                    "policy_mapped",
                    display_appname,
                    operation,
                    it,  
                    ""
                ))
       
        def ds_raw_section_toplabels_with_text(section_key: str) -> dict:
            raw = ds_data.get(section_key, {}) or {}
            out = {}
            if isinstance(raw, dict):
                for top_label, values in raw.items():
                    # Compact string for display
                    if isinstance(values, str):
                        text = values
                    elif isinstance(values, list):
                        text = ", ".join(map(str, values))
                    elif isinstance(values, dict):
                        text = ", ".join(map(str, values.values()))
                    else:
                        text = str(values)
                    out[str(top_label)] = text
            return out

        raw_shared_map = ds_raw_section_toplabels_with_text("Data shared")
        raw_collect_map = ds_raw_section_toplabels_with_text("Data collected")

       
        def add_ds_declared_but_unparsed(out_key: str, raw_map: dict):
            # out_key is "shared" or "collected"
            parsed_topkeys = set((ds_sections.get(out_key, {}) or {}).keys())
            for top_label, compact_text in raw_map.items():
               
                tk = {
                    "personal info": "personal_info",
                    "location": "location",
                    "financial info": "financial_info",
                    "messages": "messages",
                    "photos and videos": "photos_videos",
                    "audio": "audio",
                    "files and docs": "files_docs",
                    "calendar": "calendar",
                    "contacts": "contacts",
                    "app activity": "app_activity",
                    "web browsing": "web_browsing",
                    "app info and performance": "app_info_perf",
                    "device or other ids": "device_or_other_ids",
                    "health and fitness": "health_fitness",
                }.get(canon(top_label))
                if tk in cm.GOOGLE_SCHEMA:
                    if tk not in parsed_topkeys:
                        nonconsidered_rows.append((
                            "ds_declared_but_unparsed",
                            display_appname,
                            out_key,
                            top_label,           
                            compact_text[:500]    
                        ))

        add_ds_declared_but_unparsed("shared", raw_shared_map)
        add_ds_declared_but_unparsed("collected", raw_collect_map)

        for operation in ("shared", "collected"):
      
            ppd_map = {k: 0 for k in cm.GOOGLE_SCHEMA.keys()}
            ds_map  = {k: 0 for k in cm.GOOGLE_SCHEMA.keys()}

            ppd_dict = (mapped.get(operation, {}) or {})
            ds_dict  = (ds_sections.get(operation, {}) or {})

            # Presence flags
            for top_key in ppd_dict.keys():
                ppd_map[top_key] = 1
            for top_key in ds_dict.keys():
                ds_map[top_key] = 1

            rows.append((display_appname, operation, ppd_map, ds_map))

          
            all_top = sorted(set(ppd_dict.keys()) | set(ds_dict.keys()))
            for tk in all_top:
                ppd_subs = set(ppd_dict.get(tk, set()) or set())
                ds_subs  = set(ds_dict.get(tk, set()) or set())
                matched  = sorted(ppd_subs & ds_subs)
                ppd_only = sorted(ppd_subs - ds_subs)
                ds_only  = sorted(ds_subs - ppd_subs)
                # Pretty category label
                top_label = KEY_TO_LABEL.get(tk, tk)
                subtype_rows.append((
                    display_appname,
                    operation,
                    top_label,
                    ", ".join(matched),
                    ", ".join(ppd_only),
                    ", ".join(ds_only),
                    ", ".join(sorted(ppd_subs)),
                    ", ".join(sorted(ds_subs)),
                ))

           
            for item in (non_schematized.get(operation, []) or []):
                nonconsidered_rows.append((
                    "policy_non_schematized",
                    display_appname,
                    operation,
                    str(item),
                    ""
                ))

    return rows, subtype_rows, nonconsidered_rows



# -----------------------------
# Excel writer
# -----------------------------
def write_excel(rows, out_xlsx: str, subtype_rows=None, nonconsidered_rows=None):
    subtype_rows = subtype_rows or []
    nonconsidered_rows = nonconsidered_rows or []

    wb = xlsxwriter.Workbook(out_xlsx)

  
    ws = wb.add_worksheet("PPD_DS_by_operation")
    fmt_center   = wb.add_format({"align": "center", "valign": "vcenter", "border": 1})
    fmt_header   = wb.add_format({"align": "center", "valign": "vcenter", "bold": True, "border": 1})
    fmt_category = wb.add_format({"align": "center", "valign": "vcenter", "bold": True, "bg_color": "#F0F0F0", "border": 1})

    # Header rows
    ws.merge_range(0, 0, 1, 0, "appname", fmt_header)
    ws.merge_range(0, 1, 1, 1, "Operation", fmt_header)

    col = 2
    for label, _top in DISPLAY_ORDER:
        ws.merge_range(0, col, 0, col+1, label, fmt_category)
        ws.write(1, col,   "PPD", fmt_header)
        ws.write(1, col+1, "DS",  fmt_header)
        col += 2

    # Data rows start at row 2; stable sort by appname then operation
    row_idx = 2
    rows_sorted = sorted(rows, key=lambda r: (str(r[0]).lower(), 0 if r[1] == "shared" else 1))

    for app, operation, ppd_map, ds_map in rows_sorted:
        ws.write(row_idx, 0, app, fmt_center)
        ws.write(row_idx, 1, operation, fmt_center)
        col = 2
        for _label, top_key in DISPLAY_ORDER:
            ws.write(row_idx, col,   ppd_map.get(top_key, 0), fmt_center)
            ws.write(row_idx, col+1, ds_map.get(top_key, 0), fmt_center)
            col += 2
        row_idx += 1

    ws.set_column(0, 0, 36)  # appname
    ws.set_column(1, 1, 12)  # Operation
    for i in range(2, 2 + len(DISPLAY_ORDER) * 2):
        ws.set_column(i, i, 14)

    # ===== Sheet 2: Subtype matches (what exactly matched vs differed) =====
    ws2 = wb.add_worksheet("Subtype_Matches")
    headers2 = [
        "appname", "Operation", "Category",
        "Matched subtypes",
        "PPD-only subtypes",
        "DS-only subtypes",
        "PPD subtypes (all)",
        "DS subtypes (all)",
    ]
    for c, h in enumerate(headers2):
        ws2.write(0, c, h, fmt_header)

    for r, row in enumerate(sorted(subtype_rows, key=lambda x: (x[0].lower(), 0 if x[1]=="shared" else 1, x[2].lower())), start=1):
        for c, val in enumerate(row):
            ws2.write(r, c, val)

    ws2.set_column(0, 0, 36)  # appname
    ws2.set_column(1, 1, 12)  # Operation
    ws2.set_column(2, 2, 26)  # Category
    ws2.set_column(3, 7, 60)  # subtype text columns

    # ===== Sheet 3: Non-considered (debugging coverage gaps) =====
    ws3 = wb.add_worksheet("Non_Considered")
    headers3 = [
        "kind",          # policy_non_schematized | ds_declared_but_unparsed
        "appname",
        "Operation",
        "Detail_1",      # item text OR DS top label
        "Detail_2",      # (optional) raw DS compacted text
    ]
    for c, h in enumerate(headers3):
        ws3.write(0, c, h, fmt_header)

    for r, row in enumerate(sorted(nonconsidered_rows, key=lambda x: (x[1].lower(), 0 if x[2]=="shared" else 1, x[0])), start=1):
        for c, val in enumerate(row):
            ws3.write(r, c, val)

    ws3.set_column(0, 0, 26)  # kind
    ws3.set_column(1, 1, 36)  # appname
    ws3.set_column(2, 2, 12)  # Operation
    ws3.set_column(3, 3, 60)  # Detail_1
    ws3.set_column(4, 4, 80)  # Detail_2

    wb.close()
    print(f"Saved: {out_xlsx}")

# -----------------------------
# Main
def main():
    policy_summary = load_json(PPD_JSON_PATH)
    data_safety    = load_json(DS_JSON_PATH)
    rows, subtype_rows, nonconsidered_rows = compute_rows(policy_summary, data_safety)
    write_excel(rows, OUTPUT_XLSX, subtype_rows=subtype_rows, nonconsidered_rows=nonconsidered_rows)

if __name__ == "__main__":
    main()
