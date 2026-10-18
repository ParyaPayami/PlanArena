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


# ----------------------------------------------------------------------------- Southern California (SCAG)
def _codes(cls: str, *codes) -> dict:
    return {str(c): cls for c in codes}


# SCAG land-use codes (SCAG 2020 Annual Land Use dataset, code list of fields ALU20, GP19_SCAG and ZN19_SCAG)
SCAG = (_codes("sf", 1110, 1111, 1112, 1113, 1150, 1132)  # 1132 mobile home subdivisions: one home per lot
        | _codes("mf_small", 1122)  # duplexes, triplexes, 2- or 3-unit condominiums and townhouses
        | _codes("mf", 1123, 1124, 1125, 1130, 1131)  # apartments; mobile home and trailer parks (many homes per lot)
        | _codes("ret", 1200, 1220, 1221, 1222, 1223, 1230, 1232)  # 1232 commercial recreation
        | _codes("off", 1210, 1211, 1212, 1213)
        | _codes("hot", 1233)
        | _codes("whs", 1231, 1323, 1340, 1416)  # commercial and open storage, wholesaling, truck terminals
        | _codes("civ", 1240, 1241, 1242, 1243, 1245, 1246, 1250, 1251, 1253, 1270, 1271, 1274)
        | _codes("hlt", 1244, 1252)  # major medical; special care facilities
        | _codes("edu", 1260, 1261, 1262, 1263, 1264, 1265, 1266)
        | _codes("prk", 1247, 1414)  # public parking; park-and-ride lots
        | _codes("ind", 1300, 1310, 1311, 1312, 1313, 1314, 1320, 1321, 1322, 1324, 1325, 1330, 1331, 1332, 1500)
        | _codes("tra", 1273, 1276, 1400, 1410, 1411, 1412, 1413, 1415, 1417, 1418, 1420, 1430, 1431, 1432, 1433,
                 1434, 1435, 1436, 1437, 1438, 1440, 1441, 1442, 1450, 1460)
        | _codes("mix", 1600, 1610, 1620)
        | _codes("opn", 1800, 1810, 1820, 1830, 1840, 1850, 1860, 1870, 1880, 1890, 2000, 2100, 2110, 2120, 2200,
                 2300, 2400, 2500, 2600, 2700, 3400, 4000, 4100, 4200, 4300, 4400, 4500, 8888)
        | _codes("vac", 1272, 1275, 1700, 1900, 3000, 3100, 3200, 3300))
SCAG_UNKNOWN = ("7777", "9999")  # specific plan (its own code is used where given); unknown
SCAG_GENERIC_MF = ("1120", "1121", "1140")  # multi-family / mixed residential without a size


def scag(code, units=None, specific_plan=None) -> str:
    """SCAG land-use code -> class. The same code list describes existing land use (ALU20), the general plan
    (GP19_SCAG) and zoning (ZN19_SCAG). Code 7777 'Specific Plan' takes the specific plan's own code (SP19_SCAG) where
    given. Generic residential codes are split by the assessor's unit count where there is one (1100 residential,
    1120 multi-family, 1121 mixed multi-family, 1140 mixed residential); 1113 rural and 1150 rural residential are
    single-family, unless the assessor records five or more homes on the parcel. Under construction (1700) counts as
    vacant: nothing is in use yet."""
    c = str(code).strip() if code is not None else ""
    if c == "7777" and specific_plan is not None:
        return scag(specific_plan, units)
    n = _num(units)
    if c in ("1110", "1111", "1112", "1113") and n and n >= 5:
        return "mf"  # a condominium or townhouse complex the assessor records as one parcel of five or more homes
    if c == "1100":
        return "sf" if not n or n <= 1 else "mf_small" if n <= 4 else "mf"
    if c in SCAG_GENERIC_MF:
        return "mf_small" if n and n <= 4 else "mf"
    return SCAG.get(c, "unknown")


# ----------------------------------------------------------------------------- City of Los Angeles (plan and zones)
# SCAG's translation of the General Plan and zoning uses generic codes for housing (1110 single-family, 1120 or 1123
# multi-family), so a duplex designation reads as apartments. Residential designations are classed by the city's own
# density categories instead; their corresponding zones are those listed in the Community Plan land-use legends.
LA_PLAN_RESIDENTIAL = {
    **{d: "sf" for d in ("Minimum Residential", "Very Low Residential", "Very Low I Residential",
                         "Very Low II Residential", "Low Residential", "Low I Residential", "Low II Residential",
                         "Low III Residential")},  # A1, A2, RE, RS, R1, RU, RZ, RW1
    **{d: "mf_small" for d in ("Low Medium Residential", "Low Medium I Residential",
                               "Low Medium II Residential")},  # R2, RD, RW2
    **{d: "mf" for d in ("Medium Residential", "High Medium Residential", "High Density Residential",
                         "Very High Residential")},  # R3, R4, R5
}
LA_ZONE_RESIDENTIAL = [("RAS", "mf"), ("RMP", "mf"), ("RW2", "mf_small"), ("RW1", "sf"), ("RD", "mf_small"),
                       ("R2", "mf_small"), ("R3", "mf"), ("R4", "mf"), ("R5", "mf"), ("RZ", "sf"), ("RE", "sf"),
                       ("RS", "sf"), ("RU", "sf"), ("RA", "sf"), ("R1", "sf"), ("A1", "sf"), ("A2", "sf")]


def los_angeles_plan(designation, scag_code, specific_plan=None) -> str:
    """General Plan designation (GP19_CITY) -> class: residential by the city's density category, else SCAG's code."""
    d = designation.strip() if isinstance(designation, str) else ""
    return LA_PLAN_RESIDENTIAL.get(d) or scag(scag_code, specific_plan=specific_plan)


def los_angeles_zone(zone, scag_code, specific_plan=None) -> str:
    """Zone (ZN19_CITY, e.g. RD1.5, R3, C2) -> class: residential zones by family, else SCAG's code."""
    import re

    z = zone.strip().upper() if isinstance(zone, str) else ""
    for prefix, cls in LA_ZONE_RESIDENTIAL:
        if re.match(prefix + r"(?![A-Z])", z):
            return cls
    return scag(scag_code, specific_plan=specific_plan)
