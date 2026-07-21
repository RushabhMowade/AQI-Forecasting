"""
Source attribution + intervention recommendations for city administrators.

This is a rule-based decision-support layer, NOT a lab-grade source
apportionment model. Real source apportionment requires receptor modeling
(e.g. PMF, CMB) fed by speciated filter samples — well beyond what a
station-average pollutant snapshot can tell you. What this module does
instead: use well-established *indicative* pollutant signatures (ratios and
thresholds commonly cited in CPCB/air-quality-management guidance) to flag
which source categories are *plausibly* dominant right now, and pair that
with real, already-published intervention measures — India's Graded
Response Action Plan (GRAP) for Delhi-NCR — rather than inventing generic
advice. Treat the attribution as a prioritization hint for further
investigation, not a certified finding.
"""

SOURCE_CATEGORIES = ["vehicular", "industrial", "dust_construction", "biomass_agri", "secondary_photochemical"]

SOURCE_LABELS = {
    "vehicular": "Vehicular / traffic combustion",
    "industrial": "Industrial / power-plant combustion",
    "dust_construction": "Road dust / construction & demolition",
    "biomass_agri": "Biomass burning / agricultural & waste burning",
    "secondary_photochemical": "Secondary photochemical (ozone formation)",
}


def attribute_sources(pollutants: dict) -> list:
    """
    Scores each source category 0-100 using indicative pollutant signatures.
    Scores are relative flags for prioritization, not measured contribution
    percentages.
    """
    pm25 = pollutants.get('PM2.5', 0)
    pm10 = pollutants.get('PM10', 0)
    no2 = pollutants.get('NO2', 0)
    no = pollutants.get('NO', 0)
    co = pollutants.get('CO', 0)
    so2 = pollutants.get('SO2', 0)
    nh3 = pollutants.get('NH3', 0)
    o3 = pollutants.get('O3', 0)

    coarse_fraction = max(0.0, pm10 - pm25) / pm10 if pm10 > 0 else 0.0

    scores = {
        # Vehicular: NO2/NO/CO elevated relative to SO2 is a classic tailpipe signature
        "vehicular": min(100, (no2 * 1.2 + no * 1.5 + co * 25) / max(so2, 5) * 8),
        # Industrial: SO2 elevated, typically alongside NOx from combustion stacks
        "industrial": min(100, so2 * 3.2 + (no2 * 0.3 if so2 > 20 else 0)),
        # Dust/construction: a high coarse (PM10 - PM2.5) fraction points to mechanical/dust sources
        "dust_construction": min(100, coarse_fraction * 130),
        # Biomass/agri: NH3 is a strong indicator of burning/agricultural/waste sources
        "biomass_agri": min(100, nh3 * 3.0),
        # Secondary photochemical: high O3 with comparatively low primary NOx/CO
        "secondary_photochemical": min(100, max(0, o3 - (no2 + co * 10)) * 1.4),
    }

    total = sum(scores.values()) or 1.0
    ranked = sorted(
        (
            {
                "source": key,
                "label": SOURCE_LABELS[key],
                "score": round(v, 1),
                "share_pct": round(v / total * 100, 1),
            }
            for key, v in scores.items()
        ),
        key=lambda x: x["score"],
        reverse=True,
    )
    return ranked


# GRAP (Graded Response Action Plan, India's official Delhi-NCR air quality
# response framework) actions, tagged by the AQI stage they apply at and the
# source category they primarily target. Stage thresholds per CPCB/CAQM.
GRAP_ACTIONS = [
    # Stage I — Poor (201-300)
    {"stage": "I", "min_aqi": 201, "source": "dust_construction",
     "action": "Mechanized sweeping and water sprinkling on roads and hotspots; enforce dust control norms at all construction/demolition sites."},
    {"stage": "I", "min_aqi": 201, "source": "biomass_agri",
     "action": "Strict enforcement against open burning of garbage/biomass, including at landfill sites."},
    {"stage": "I", "min_aqi": 201, "source": "vehicular",
     "action": "Intensify Pollution Under Control (PUC) certificate checks and penalize visibly polluting vehicles."},

    # Stage II — Very Poor (301-400)
    {"stage": "II", "min_aqi": 301, "source": "vehicular",
     "action": "Increase public bus/metro frequency; raise parking fees to discourage private vehicle trips."},
    {"stage": "II", "min_aqi": 301, "source": "industrial",
     "action": "Stop use of diesel generator sets except for essential/emergency services; ensure industries are on approved (PNG/cleaner) fuel."},
    {"stage": "II", "min_aqi": 301, "source": "dust_construction",
     "action": "Close or strictly monitor unpaved roads and stockpiling sites; deploy anti-smog guns at major hotspots."},

    # Stage III — Severe (401-450)
    {"stage": "III", "min_aqi": 401, "source": "dust_construction",
     "action": "Ban construction and demolition activities citywide, except for essential/public-safety projects."},
    {"stage": "III", "min_aqi": 401, "source": "vehicular",
     "action": "Restrict entry of non-essential trucks and older (BS-III petrol / BS-IV diesel) vehicles into the city."},
    {"stage": "III", "min_aqi": 401, "source": "biomass_agri",
     "action": "Coordinate with neighboring districts on stubble-burning enforcement; issue public health advisories for outdoor activity."},

    # Stage IV — Severe+ (>450)
    {"stage": "IV", "min_aqi": 450, "source": "vehicular",
     "action": "Consider odd-even vehicle rationing; encourage work-from-home for non-essential offices."},
    {"stage": "IV", "min_aqi": 450, "source": "industrial",
     "action": "Halt industrial operations not running on approved clean fuel; suspend non-essential power-plant operations where feasible."},
    {"stage": "IV", "min_aqi": 450, "source": "dust_construction",
     "action": "Full halt on all construction/demolition and mining/stone-crushing operations."},
]


def recommend_actions(current_aqi: float, ranked_sources: list, top_n_sources: int = 3) -> dict:
    """
    Returns GRAP-stage-appropriate actions, prioritized toward whichever
    source categories are currently scoring highest.
    """
    if current_aqi <= 200:
        return {
            "stage": None,
            "note": "AQI is at or below 'Moderate/Satisfactory' — no GRAP-level intervention triggered. "
                    "Continue routine monitoring and preventive dust/emissions enforcement.",
            "actions": [],
        }

    if current_aqi > 450:
        stage = "IV"
    elif current_aqi > 400:
        stage = "III"
    elif current_aqi > 300:
        stage = "II"
    else:
        stage = "I"

    stage_order = {"I": 1, "II": 2, "III": 3, "IV": 4}
    applicable = [a for a in GRAP_ACTIONS if stage_order[a["stage"]] <= stage_order[stage]]

    priority_sources = {s["source"] for s in ranked_sources[:top_n_sources]}
    applicable.sort(key=lambda a: (a["source"] not in priority_sources, stage_order[a["stage"]]))

    return {
        "stage": stage,
        "note": f"GRAP Stage {stage} actions (AQI {round(current_aqi)}), prioritized toward the "
                f"currently dominant suspected source categories.",
        "actions": [
            {
                "stage": a["stage"],
                "source": a["source"],
                "source_label": SOURCE_LABELS[a["source"]],
                "action": a["action"],
                "priority": a["source"] in priority_sources,
            }
            for a in applicable
        ],
    }
