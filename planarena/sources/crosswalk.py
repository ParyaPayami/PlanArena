"""Official land-use codes of each city -> PlanArena's 16 classes (planarena/taxonomy.py).

Each function takes the source's own fields and returns a class key, or "unknown" when the source does not say.
The tables follow each source's published code list (cited in the docstrings); tests check that every code present in
the data maps to a class or is listed as unknown on purpose.
"""
from __future__ import annotations

import math


def _num(x) -> int | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else int(v)


# ----------------------------------------------------------------------------- New York City (MapPLUTO)
def nyc(land_use, bldg_class, units_res) -> str:
    """MapPLUTO LandUse (01-11, NYC DCP) refined by the DOF building class (first letter) and residential units.

    Building classes: A one-family, B two-family, C walk-up, D elevator, E warehouse, F factory, G garage/gas
    station, H hotel, I health, K store, M religious, N asylum/home, O office, P assembly/cultural, W education,
    Y government (NYC Department of Finance building classification glossary).
    """
    lu = _num(land_use)
    bc = bldg_class.strip().upper()[:1] if isinstance(bldg_class, str) else ""
    units = _num(units_res) or 0
    if lu is None:
        return "unknown"
    if lu == 1:
        return "sf" if bc == "A" or units <= 1 else "mf_small"
    if lu == 2:
        return "mf_small" if units <= 4 else "mf"
    if lu == 3:
        return "mf"
    if lu == 4:
        return "mix"
    if lu == 5:
        return {"O": "off", "H": "hot", "G": "ret"}.get(bc, "ret")
    if lu == 6:
        return "whs" if bc == "E" else "ind"
    if lu == 7:
        return "tra"
    if lu == 8:
        return {"W": "edu", "I": "hlt"}.get(bc, "civ")
    return {9: "opn", 10: "prk", 11: "vac"}.get(lu, "unknown")


# ----------------------------------------------------------------------------- Milwaukee (MPROP)
def milwaukee(land_use, group, units_res) -> str:
    """MPROP land-use group (MPROP documentation, Appendix H) refined by the land-use code, which is a Standard
    Industrial Classification code for non-residential property (e.g. 5812 eating places, 4225 warehousing, 8211
    schools, 8062 hospitals, 7011 hotels, 8661 religious organisations) or a city code for homes and vacant land."""
    code, gp, units = _num(land_use) or 0, _num(group) or 0, _num(units_res) or 0
    sic2 = code // 100
    if code in (7521, 7523, 7525):
        return "prk"
    if gp == 1:
        return "sf"
    if gp == 2:
        return "mf_small"
    if gp == 3:
        return "mf" if units >= 5 else "mf_small"
    if gp == 4:
        return "mix"
    if gp == 5:
        return "whs" if sic2 in (50, 51) else "ret"
    if gp == 6:
        if 60 <= sic2 <= 67 or sic2 in (73, 81, 87, 74):
            return "off"
        if code == 7011:
            return "hot"
        if code == 7021:
            return "mf"  # rooming and boarding houses
        if sic2 == 80 or code == 8361:
            return "hlt"
        if sic2 == 82 or code == 8351:
            return "edu"  # schools, colleges; child day care
        if sic2 in (83, 84, 86):
            return "civ"
        return "ret"  # personal, repair, amusement and other consumer services
    if gp == 7:
        return "ret"  # commercial mixed use and commercial condominiums
    if gp == 8:
        return "whs" if code in range(4221, 4227) or sic2 in (50, 51) else "ind"
    if gp == 9:
        return "tra"
    if gp in (10, 12):
        return "opn"
    if gp == 11:
        return "edu" if sic2 == 82 else "hlt" if sic2 == 80 else "civ"
    if gp == 13 or code == 9850:
        return "vac"
    return "unknown"


# ----------------------------------------------------------------------------- Philadelphia (City Planning Commission)
def philadelphia(dig2, dig3, opa_category=None, opa_description=None) -> str:
    """Philadelphia land use (City Planning Commission, two- and three-digit codes). Where only the two-digit code is
    given, the parcel's OPA assessment record splits it: the category for homes (1 single family, 2 multi-family,
    14 apartments of 5+ units) and the building description for institutions, industry and hotels."""
    d2, d3, cat = _num(dig2), _num(dig3), _num(opa_category)
    desc = opa_description.upper() if isinstance(opa_description, str) else ""
    if d3 is not None:
        exact = {111: "sf", 112: "sf", 121: "sf", 119: "sf", 122: "mf_small", 123: "mf_small", 124: "mf_small",
                 125: "mf_small", 129: "mf_small", 131: "mf", 132: "mf", 133: "mf", 135: "hot", 136: "hlt", 137: "mf",
                 138: "civ", 139: "mf", 211: "ret", 212: "ret", 213: "ret", 219: "ret", 221: "off", 222: "off",
                 229: "off", 231: "mix", 232: "mix", 233: "mix", 239: "mix", 314: "tra", 316: "whs", 317: "whs",
                 411: "hlt", 412: "edu", 413: "edu", 514: "prk", 529: "opn", 613: "ret", 621: "opn", 921: "unknown"}
        if d3 in exact:
            return exact[d3]
        d2 = d2 or d3 // 10
    if d2 is None:
        return "unknown"
    if d2 in (11, 12, 13):
        if d2 == 13 or cat == 14:
            return "mf"
        return "mf_small" if cat == 2 else "sf"
    if d2 == 41:
        if any(w in desc for w in ("SCHOOL", "COLLEGE", "UNIVERSITY", "DAY CARE")):
            return "edu"
        if any(w in desc for w in ("HOSPITAL", "MEDICAL", "NURSING", "CLINIC")):
            return "hlt"
    if d2 in (21, 22) and ("HOTEL" in desc or "MOTEL" in desc):
        return "hot"
    if d2 == 31 and "WAREHOUSE" in desc:
        return "whs"
    return {21: "ret", 22: "off", 23: "mix", 31: "ind", 41: "civ", 51: "tra", 52: "opn", 61: "civ", 62: "opn",
            71: "opn", 72: "opn", 81: "opn", 91: "vac"}.get(d2, "unknown")
