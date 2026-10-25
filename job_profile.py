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
    "tampa": {
        "label": "Tampa Bay, FL",
        "adzuna_where": "Tampa, FL",
        "jsearch_query_suffix": "in Tampa, FL",
        "radius_km": 50,          # Tampa, St. Petersburg, Clearwater, Brandon
        "priority": 1.0,          # primary target
    },
    "jacksonville": {
        "label": "Jacksonville, FL",
        "adzuna_where": "Jacksonville, FL",
        "jsearch_query_suffix": "in Jacksonville, FL",
        "radius_km": 50,
        "priority": 0.9,          # secondary target
    },
    "orlando": {
        "label": "Orlando, FL",
        "adzuna_where": "Orlando, FL",
        "jsearch_query_suffix": "in Orlando, FL",
        "radius_km": 50,          # Orlando, Kissimmee, Sanford, Winter Park
        "priority": 0.9,
    },
    "tallahassee": {
        "label": "Tallahassee, FL",
        "adzuna_where": "Tallahassee, FL",
        "jsearch_query_suffix": "in Tallahassee, FL",
        "radius_km": 40,          # smaller market; state government + FSU anchor it
        "priority": 0.8,
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
            "procurement specialist",
            "vendor management analyst",
            "insurance operations specialist",
            "claims analyst",
        ],
    },
    # OPERATIONS : warehouse, distribution and logistics floor work. The Will
    #              Call half of the Sysco job -- receiving paperwork, order
    #              selection, customer pickup -- is direct experience here.
    "operations": {
        "weight": 1.05,
        "queries": [
            "warehouse supervisor",
            "warehouse lead",
            "inventory control specialist",
            "shipping and receiving clerk",
            "logistics coordinator",
            "dispatcher",
            "distribution center associate",
            "forklift operator",
            "material handler",
            "paid cdl training",
        ],
    },
    # TRADES     : hands-on work with paid training and a rising pay ceiling.
    #              Florida's population growth keeps demand for these high,
    #              and most start as paid apprenticeships -- no degree needed.
    "trades": {
        "weight": 1.05,
        "queries": [
            "hvac apprentice",
            "electrician apprentice",
            "solar installer",
            "industrial maintenance technician",
            "lineworker apprentice",
            "plumber apprentice",
            "fiber optic technician",
            "aircraft maintenance technician trainee",
            "facilities maintenance technician",
            "apprenticeship paid training",
        ],
    },
}

# Job titles that map straight onto a track get a flat bump in scoring.
TITLE_TOKENS = (
    # finance + banking
    "accounts receivable", "cash application", "billing", "finance associate",
    "banker", "branch operations", "aml", "bsa", "fraud", "kyc",
    "revenue cycle", "credit analyst", "operations analyst",
    # warehouse + logistics
    "will call", "warehouse", "inventory", "shipping", "receiving",
    "logistics", "dispatcher", "distribution", "forklift", "material handler",
    # trades
    "apprentice", "hvac", "electrician", "solar", "maintenance technician",
    "lineworker", "lineman", "plumber", "fiber",
)

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

    # warehouse + logistics floor
    "forklift": 6,
    "pallet jack": 4,
    "cycle count": 6,
    "shipping": 5,
    "dispatch": 5,
    "warehouse management system": 5,
    "osha": 4,
    "loading dock": 4,

    # trades + on-ramps -- signals the employer will train you
    "apprenticeship": 6,
    "paid training": 7,
    "will train": 6,
    "no experience required": 4,
    "tuition reimbursement": 4,
    "certification provided": 5,
}

# Schedule language. The current job is six days a week; getting a weekend
# back is a stated reason for the move, so the posting's schedule is scored.
SCHEDULE_SIGNALS = {
    "monday-friday": 7,
    "monday - friday": 7,
    "monday through friday": 7,
    "mon-fri": 7,
    "weekends off": 8,
    "no weekends": 8,
    "4x10": 6,
    "four 10": 6,
    "6 days a week": -8,
    "six days a week": -8,
    "weekends required": -5,
    "mandatory weekends": -6,
}

# Sector tailwind: employers/industries growing in the target metros.
# Matched against company name + description.
SECTOR_BONUS = {
    # Tampa Bay
    "raymond james": 8,
    "citigroup": 5,
    "jabil": 6,
    "baycare": 6,
    "moffitt": 5,
    "adventhealth": 5,
    "publix": 6,
    "suncoast credit union": 6,
    # Jacksonville
    "fis global": 7,
    "fidelity national": 7,
    "vystar": 7,
    "florida blue": 7,
    "csx": 6,
    "mayo clinic": 6,
    "baptist health": 5,
    "deutsche bank": 6,
    # Orlando
    "orlando health": 7,
    "walt disney": 6,
    "universal orlando": 6,
    "darden": 6,
    "lockheed martin": 6,
    "fairwinds": 6,
    "addition financial": 6,
    # Tallahassee
    "state of florida": 6,
    "florida state university": 6,
    "tallahassee memorial": 6,
    "capital city bank": 7,
    "fsu credit union": 5,
    # any metro
    "credit union": 5,
    "health system": 6,
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
# The floor sits below current comp on purpose: changing sectors may mean an
# entry role, and a $45K job with paid training and weekends off can beat $50K
# over six days. Anything under the floor is flagged, not hidden.

SALARY_FLOOR = 45_000        # entry roles in a new sector are acceptable
SALARY_TARGET = 62_000       # the number that makes the move clearly worth it
SALARY_STRETCH = 75_000      # top of the realistic band for these tracks

# Cost-of-living adjustment vs. Albany, NY (approximate, directional only).
# Tampa Bay runs close to par; Jacksonville is somewhat cheaper.
COL_INDEX = {
    "tampa": 0.99,
    "jacksonville": 0.94,
    "orlando": 0.99,
    "tallahassee": 0.90,
}
