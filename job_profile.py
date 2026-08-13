"""
Candidate profile: what we're looking for and how much each signal is worth.

Everything a human would tune lives in this file. Editing this is how you
change what the scanner considers a good job -- you should not need to touch
scoring.py.
"""

# ---------------------------------------------------------------------------
# Where
# ---------------------------------------------------------------------------

METROS = {
    "san_antonio": {
        "label": "San Antonio, TX",
        "adzuna_where": "San Antonio, TX",
        "jsearch_query_suffix": "in San Antonio, TX",
        "radius_km": 40,
        "priority": 1.0,          # primary target
    },
    "dallas": {
        "label": "Dallas-Fort Worth, TX",
        "adzuna_where": "Dallas, TX",
        "jsearch_query_suffix": "in Dallas, TX",
        "radius_km": 60,
        "priority": 0.9,          # secondary target
    },
}

# ---------------------------------------------------------------------------
# What -- three tracks, searched separately so results stay legible
# ---------------------------------------------------------------------------
# DIRECT   : roles the current resume already wins on
# STRETCH  : roles one credible step up; existing experience gets you screened in
# GROWTH   : roles in sectors projected to expand, reachable with transferable skills

SEARCH_TRACKS = {
    "direct": {
        "weight": 1.00,
        "queries": [
            "accounts receivable specialist",
            "cash application specialist",
            "billing specialist",
            "finance associate",
            "accounting clerk",
            "branch operations specialist",
            "relationship banker",
            "personal banker",
            "will call coordinator",
            "customer account representative",
        ],
    },
    "stretch": {
        "weight": 1.15,   # slight boost: better pay ceiling, same skill base
        "queries": [
            "bsa aml analyst",
            "financial crimes analyst",
            "fraud analyst",
            "kyc analyst",
            "compliance analyst bank",
            "credit analyst",
            "treasury operations analyst",
            "revenue cycle specialist",
            "accounts receivable supervisor",
            "operations analyst",
        ],
    },
    "growth": {
        "weight": 1.10,   # sector tailwind, may need a cert or a lateral entry
        "queries": [
            "patient financial services representative",
            "healthcare revenue cycle analyst",
            "grc analyst entry level",
            "security compliance analyst",
            "supply chain analyst",
            "logistics coordinator",
            "procurement specialist",
            "vendor management analyst",
            "insurance operations specialist",
            "claims analyst",
        ],
    },
}

# ---------------------------------------------------------------------------
# Skill keywords -- matched against title + description.
# Points are additive; a job hitting many of these is a job the resume answers.
# ---------------------------------------------------------------------------

SKILL_KEYWORDS = {
    # core finance ops -- the strongest part of the resume
    "cash application": 9,
    "accounts receivable": 8,
    "payment application": 8,
    "check processing": 7,
    "reconciliation": 7,
    "invoice": 6,
    "billing": 6,
    "deposits": 5,
    "aging report": 5,
    "collections": 5,
    "general ledger": 4,
    "erp": 3,
    "sap": 3,
    "oracle": 3,
    "excel": 4,

    # banking / compliance -- Regions + Wells Fargo history
    "kyc": 7,
    "bsa": 7,
    "aml": 7,
    "suspicious activity": 6,
    "fraud": 6,
    "compliance": 5,
    "risk": 4,
    "account opening": 6,
    "consumer banking": 6,
    "branch": 4,
    "teller": 3,

    # operations / distribution -- the Sysco half
    "will call": 9,
    "order selection": 7,
    "warehouse": 5,
    "inventory": 5,
    "receiving": 5,
    "distribution": 5,
    "fulfillment": 4,
    "logistics": 4,
    "supply chain": 4,

    # transferable soft signals
    "customer service": 4,
    "client relationship": 5,
    "dispute resolution": 5,
    "high volume": 4,
    "detail-oriented": 2,
    "bilingual": 4,
    "french": 6,
}

# Sector tailwind: employers/industries growing in the target metros.
# Matched against company name + description.
SECTOR_BONUS = {
    "usaa": 8,
    "frost bank": 8,
    "h-e-b": 6,
    "heb": 5,
    "rackspace": 6,
    "toyota": 6,
    "credit union": 5,
    "health system": 6,
    "methodist": 5,
    "baptist": 4,
    "medical center": 5,
    "hospital": 4,
    "cybersecurity": 5,
    "defense": 4,
    "aerospace": 4,
    "biosciences": 4,
    "life sciences": 4,
    "sysco": 10,        # internal transfer beats an external hire, every time
    "insurance": 4,
    "fintech": 5,
    "bank": 4,
}

# Phrases that mean this job is not actually reachable right now.
# Each one subtracts; enough of them and the job drops out of the digest.
DISQUALIFIERS = {
    "cpa required": -25,
    "cpa certification required": -25,
    "master's degree required": -20,
    "10+ years": -18,
    "8+ years": -12,
    "7+ years": -10,
    "active security clearance": -20,
    "ts/sci": -25,
    "rn license": -30,
    "registered nurse": -30,
    "commission only": -20,
    "unpaid": -40,
    "internship": -15,
    "must have own vehicle": -5,
    "door to door": -25,
}

# ---------------------------------------------------------------------------
# Compensation
# ---------------------------------------------------------------------------
# Current comp is the floor, not the target. A move should buy either money or
# time back -- ideally both. Anything at or under the floor is flagged, not hidden,
# because a 5-day week at equal pay is still a raise per hour.

SALARY_FLOOR = 50_000        # do not go backwards
SALARY_TARGET = 62_000       # the number that makes the move clearly worth it
SALARY_STRETCH = 75_000      # top of the realistic band for these tracks

# Cost-of-living adjustment vs. Albany, NY (approximate, directional only).
# San Antonio is materially cheaper; Dallas is closer to par.
COL_INDEX = {
    "san_antonio": 0.88,
    "dallas": 0.97,
}
