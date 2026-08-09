"""
Natural-language-to-structured cohort query builder.

Deliberately NOT backed by an LLM: it's a transparent pattern-matching
parser over a small, documented grammar. This is an honest tradeoff --
it won't understand arbitrary phrasing, but every match is traceable to an
explicit rule, satisfying the brief's requirement for "visible inclusion
and exclusion logic" and no silent guessing. Unmatched/ambiguous terms are
surfaced to the user rather than silently ignored (the abstention behavior
required by the safety section).

Supported patterns (case-insensitive):
    age (over|under|above|below) N
    age between N and M
    gender male|female|M|F
    diagnosis <keyword>              (matches against d_icd_diagnoses.long_title)
    admission type <keyword>
    race <keyword>
    died in hospital / survived
"""

import re
import pandas as pd


class CohortFilter:
    def __init__(self):
        self.clauses = []  # list of (description, predicate_fn(subject_row_bundle) -> bool)
        self.unrecognized = []

    def add(self, description, predicate_fn):
        self.clauses.append((description, predicate_fn))

    def explain(self):
        return [c[0] for c in self.clauses]


AGE_OVER_RE = re.compile(r"age\s+(over|above|greater than|>)\s*(\d+)", re.I)
AGE_UNDER_RE = re.compile(r"age\s+(under|below|less than|<)\s*(\d+)", re.I)
AGE_BETWEEN_RE = re.compile(r"age\s+between\s+(\d+)\s+and\s+(\d+)", re.I)
GENDER_RE = re.compile(r"\b(male|female|\bM\b|\bF\b)\b", re.I)
DIAGNOSIS_RE = re.compile(r"diagnos(?:is|ed with|ed)\s+(?:of\s+)?([a-zA-Z0-9 \-]+)", re.I)
ADMIT_TYPE_RE = re.compile(r"admission type\s+([a-zA-Z0-9 \-\.]+)", re.I)
RACE_RE = re.compile(r"\brace\s+([a-zA-Z /]+)", re.I)
DIED_RE = re.compile(r"\b(died|death|deceased|expired)\b", re.I)
SURVIVED_RE = re.compile(r"\b(survived|discharged alive)\b", re.I)


def parse_query(text: str):
    """
    Parses free-text into a CohortFilter with human-readable clause
    descriptions. Returns (CohortFilter, list_of_unmatched_fragments).
    Any fragment of the input not consumed by a known pattern is reported
    back rather than silently dropped.
    """
    cf = CohortFilter()
    remaining = text

    m = AGE_BETWEEN_RE.search(text)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        cf.add(f"age between {lo} and {hi}", lambda p, lo=lo, hi=hi: p.get("anchor_age") is not None and lo <= p["anchor_age"] <= hi)
        remaining = remaining.replace(m.group(0), "")
    else:
        m = AGE_OVER_RE.search(text)
        if m:
            n = int(m.group(2))
            cf.add(f"age over {n}", lambda p, n=n: p.get("anchor_age") is not None and p["anchor_age"] > n)
            remaining = remaining.replace(m.group(0), "")
        m = AGE_UNDER_RE.search(text)
        if m:
            n = int(m.group(2))
            cf.add(f"age under {n}", lambda p, n=n: p.get("anchor_age") is not None and p["anchor_age"] < n)
            remaining = remaining.replace(m.group(0), "")

    m = GENDER_RE.search(text)
    if m:
        g = m.group(1).upper()[0]  # "male"->"M", "female"->"F", "M"->"M", "F"->"F"
        cf.add(f"gender = {g}", lambda p, g=g: p.get("gender") == g)
        remaining = remaining.replace(m.group(0), "")

    m = DIAGNOSIS_RE.search(text)
    if m:
        kw = m.group(1).strip().rstrip(".")
        cf.add(f"diagnosis contains '{kw}'",
               lambda p, kw=kw.lower(): any(kw in str(d).lower() for d in p.get("_diagnosis_titles", [])))
        remaining = remaining.replace(m.group(0), "")

    m = ADMIT_TYPE_RE.search(text)
    if m:
        kw = m.group(1).strip().rstrip(".")
        cf.add(f"admission type contains '{kw}'",
               lambda p, kw=kw.lower(): any(kw in str(t).lower() for t in p.get("_admission_types", [])))
        remaining = remaining.replace(m.group(0), "")

    m = RACE_RE.search(text)
    if m:
        kw = m.group(1).strip().rstrip(".")
        cf.add(f"race contains '{kw}'",
               lambda p, kw=kw.lower(): any(kw in str(r).lower() for r in p.get("_races", [])))
        remaining = remaining.replace(m.group(0), "")

    if DIED_RE.search(text):
        cf.add("died in hospital (hospital_expire_flag = 1)",
               lambda p: 1 in p.get("_expire_flags", []))
        remaining = DIED_RE.sub("", remaining)

    if SURVIVED_RE.search(text):
        cf.add("survived hospitalization (hospital_expire_flag = 0 for all admissions)",
               lambda p: p.get("_expire_flags") and all(f == 0 for f in p["_expire_flags"]))
        remaining = SURVIVED_RE.sub("", remaining)

    STOPWORDS = {"and", "with", "who", "were", "was", "the", "a", "an", "patients", "patient"}
    tokens = [t for t in re.findall(r"[a-zA-Z0-9]+", remaining) if t.lower() not in STOPWORDS]
    unmatched = [" ".join(tokens)] if tokens else []

    return cf, unmatched


def build_patient_bundle(tables: dict) -> dict:
    """
    Pre-joins per-patient info needed for filtering: age/gender from
    patients, plus lists of diagnosis titles, admission types, races, and
    expire flags pulled from their admissions/diagnoses. Returns
    {subject_id: {...}}.
    """
    bundle = {}
    patients = tables.get("patients", pd.DataFrame())
    admissions = tables.get("admissions", pd.DataFrame())
    diagnoses = tables.get("diagnoses_icd", pd.DataFrame())
    d_icd = tables.get("d_icd_diagnoses", pd.DataFrame())

    for _, p in patients.iterrows():
        sid = p["subject_id"]
        bundle[sid] = {
            "subject_id": sid,
            "anchor_age": p.get("anchor_age"),
            "gender": p.get("gender"),
            "_admission_types": [],
            "_races": [],
            "_expire_flags": [],
            "_diagnosis_titles": [],
        }

    if not admissions.empty:
        for _, a in admissions.iterrows():
            sid = a["subject_id"]
            if sid not in bundle:
                continue
            bundle[sid]["_admission_types"].append(a.get("admission_type"))
            bundle[sid]["_races"].append(a.get("race"))
            if pd.notna(a.get("hospital_expire_flag")):
                bundle[sid]["_expire_flags"].append(int(a["hospital_expire_flag"]))

    if not diagnoses.empty and not d_icd.empty:
        merged = diagnoses.merge(d_icd, on=["icd_code", "icd_version"], how="left")
        for _, d in merged.iterrows():
            sid = d["subject_id"]
            if sid in bundle:
                bundle[sid]["_diagnosis_titles"].append(d.get("long_title"))

    return bundle


def apply_filter(bundle: dict, cf: CohortFilter):
    """Returns (matching_subject_ids, per-clause match counts) for transparency."""
    matches = []
    clause_counts = {desc: 0 for desc, _ in cf.clauses}
    for sid, p in bundle.items():
        ok = True
        for desc, pred in cf.clauses:
            try:
                result = bool(pred(p))
            except Exception:
                result = False
            if result:
                clause_counts[desc] += 1
            ok = ok and result
        if ok:
            matches.append(sid)
    return matches, clause_counts
