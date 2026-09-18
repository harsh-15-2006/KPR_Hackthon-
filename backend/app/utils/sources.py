"""Registry of the five SU-04 operational emission sources.

Each source declares its OWN activity unit and its own Climatiq parameter
shape. There is deliberately no universal unit: electricity is energy,
logistics is distance x weight, waste is mass, and so on.

`climatiq_activity_id` values are PLACEHOLDERS. Climatiq activity IDs must be
looked up in the Climatiq Data Explorer for your region and data version;
they are not guessed here. Override them in climatiq_activity_map.json.
"""
from typing import Any

ELECTRICITY = "electricity"
FUEL = "fuel"
LOGISTICS = "logistics"
PRODUCTION = "production"
WASTE = "waste"

SOURCES: list[str] = [ELECTRICITY, FUEL, LOGISTICS, PRODUCTION, WASTE]

SOURCE_CONFIG: dict[str, dict[str, Any]] = {
    ELECTRICITY: {
        "label": "Electricity",
        "activity_types": ["grid_electricity"],
        "allowed_units": ["kWh", "MWh"],
        "default_unit": "kWh",
        "climatiq_param": "energy",
        "climatiq_unit_param": "energy_unit",
        "climatiq_activity_id": "",  # set in climatiq_activity_map.json
        "help": "Electricity drawn from the grid over the reporting period.",
    },
    FUEL: {
        "label": "Fuel",
        "activity_types": ["diesel", "petrol", "natural_gas", "furnace_oil", "lpg"],
        "allowed_units": ["L", "kg", "m3"],
        "default_unit": "L",
        "climatiq_param": "volume",
        "climatiq_unit_param": "volume_unit",
        "climatiq_activity_id": "",
        "help": "Fuel combusted on site or in owned vehicles.",
    },
    LOGISTICS: {
        "label": "Logistics",
        "activity_types": ["road_freight", "rail_freight", "sea_freight", "air_freight"],
        "allowed_units": ["t.km", "km"],
        "default_unit": "t.km",
        "climatiq_param": "distance",
        "climatiq_unit_param": "distance_unit",
        "climatiq_activity_id": "",
        "help": "Freight movement. t.km = tonnes carried x kilometres travelled.",
    },
    PRODUCTION: {
        "label": "Production",
        "activity_types": ["steel", "cement", "plastic", "generic_material"],
        "allowed_units": ["t", "kg"],
        "default_unit": "t",
        "climatiq_param": "weight",
        "climatiq_unit_param": "weight_unit",
        "climatiq_activity_id": "",
        "help": "Process/material throughput for the reporting period.",
    },
    WASTE: {
        "label": "Waste",
        "activity_types": ["landfill", "recycled", "incinerated", "organic"],
        "allowed_units": ["t", "kg"],
        "default_unit": "t",
        "climatiq_param": "weight",
        "climatiq_unit_param": "weight_unit",
        "climatiq_activity_id": "",
        "help": "Waste sent to each treatment route.",
    },
}


def is_valid_source(source: str) -> bool:
    return source in SOURCE_CONFIG


def allowed_units(source: str) -> list[str]:
    return SOURCE_CONFIG[source]["allowed_units"] if is_valid_source(source) else []
