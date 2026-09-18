"""DEMO MODE data. NOT measurements. NOT from Climatiq. NOT real-world facts.

These illustrative factors exist so the prototype runs end-to-end without an
external API. Every record produced from them is stamped
calculation_source = "demo" and is labelled as DEMO DATA in the UI.
"""

DEMO_DISCLAIMER = (
    "DEMO DATA - illustrative project assumption, not a measurement and not "
    "sourced from Climatiq."
)

# source -> factor per 1 unit, keyed by the unit it applies to.
DEMO_FACTORS: dict[str, dict] = {
    "electricity": {"per_unit": {"kWh": 0.71, "MWh": 710.0}, "co2e_unit": "kg"},
    "fuel": {"per_unit": {"L": 2.68, "kg": 3.17, "m3": 2.02}, "co2e_unit": "kg"},
    "logistics": {"per_unit": {"t.km": 0.11, "km": 0.21}, "co2e_unit": "kg"},
    "production": {"per_unit": {"t": 1850.0, "kg": 1.85}, "co2e_unit": "kg"},
    "waste": {"per_unit": {"t": 458.0, "kg": 0.458}, "co2e_unit": "kg"},
}


def demo_estimate(source: str, activity_value: float, activity_unit: str) -> dict:
    """Deterministic demo calculation. Always stamped as calculation_source=demo."""
    cfg = DEMO_FACTORS.get(source)
    if not cfg:
        raise ValueError("No demo factor configured for source '" + source + "'.")
    factor = cfg["per_unit"].get(activity_unit)
    if factor is None:
        available = ", ".join(cfg["per_unit"].keys())
        raise ValueError(
            "No demo factor for unit '"
            + activity_unit
            + "' in source '"
            + source
            + "'. Available units: "
            + available
        )
    ref = (
        DEMO_DISCLAIMER
        + " ("
        + str(factor)
        + " "
        + cfg["co2e_unit"]
        + " per "
        + activity_unit
        + ")"
    )
    return {
        "co2e": round(activity_value * factor, 4),
        "co2e_unit": cfg["co2e_unit"],
        "emission_factor_reference": ref,
        "calculation_source": "demo",
    }


SEED_DATA_SOURCE = (
    "DEMO DATA - configured project assumption for Stage 1. Cost in INR lakh, "
    "reduction in tCO2e/yr. Not sourced from any published dataset."
)

# Seed rows for reduction_actions. cost = INR lakh, expected_reduction = tCO2e/yr.
# Both are CONFIGURED PROJECT ASSUMPTIONS, not published figures.
SEED_ACTIONS: list[dict] = [
    {
        "source": "electricity",
        "action_name": "Rooftop solar installation",
        "description": "On-site solar PV to displace purchased grid electricity.",
        "cost": 40.0,
        "expected_reduction": 800.0,
        "implementation_time": "6-9 months",
        "availability": "available",
    },
    {
        "source": "electricity",
        "action_name": "Energy-efficiency upgrade",
        "description": "Motor, lighting and HVAC efficiency retrofit.",
        "cost": 15.0,
        "expected_reduction": 300.0,
        "implementation_time": "3-4 months",
        "availability": "available",
    },
    {
        "source": "fuel",
        "action_name": "Fuel switching",
        "description": "Switch boiler fuel to a lower-carbon alternative.",
        "cost": 20.0,
        "expected_reduction": 450.0,
        "implementation_time": "4-6 months",
        "availability": "available",
    },
    {
        "source": "fuel",
        "action_name": "Boiler heat recovery",
        "description": "Recover waste heat from flue gas to cut fuel demand.",
        "cost": 12.0,
        "expected_reduction": 210.0,
        "implementation_time": "3-5 months",
        "availability": "available",
    },
    {
        "source": "logistics",
        "action_name": "Route optimization",
        "description": "Consolidate loads and optimise delivery routing.",
        "cost": 8.0,
        "expected_reduction": 180.0,
        "implementation_time": "1-2 months",
        "availability": "available",
    },
    {
        "source": "logistics",
        "action_name": "EV fleet conversion",
        "description": "Replace part of the owned fleet with electric vehicles.",
        "cost": 30.0,
        "expected_reduction": 500.0,
        "implementation_time": "9-12 months",
        "availability": "available",
    },
    {
        "source": "production",
        "action_name": "Process heat optimisation",
        "description": "Tune furnace and kiln operation to cut process emissions.",
        "cost": 25.0,
        "expected_reduction": 380.0,
        "implementation_time": "6-8 months",
        "availability": "available",
    },
    {
        "source": "production",
        "action_name": "Material substitution",
        "description": "Substitute a lower-carbon input material.",
        "cost": 18.0,
        "expected_reduction": 260.0,
        "implementation_time": "4-6 months",
        "availability": "limited",
    },
    {
        "source": "waste",
        "action_name": "Recycling improvement",
        "description": "Divert segregated waste from landfill to recycling.",
        "cost": 5.0,
        "expected_reduction": 100.0,
        "implementation_time": "1-3 months",
        "availability": "available",
    },
    {
        "source": "waste",
        "action_name": "Organic waste composting",
        "description": "On-site composting of organic waste to avoid landfill methane.",
        "cost": 7.0,
        "expected_reduction": 130.0,
        "implementation_time": "2-4 months",
        "availability": "available",
    },
]
