from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.sources import SOURCE_CONFIG, allowed_units, is_valid_source


class EmissionCalculateRequest(BaseModel):
    source: str = Field(..., description="One of: electricity, fuel, logistics, production, waste")
    activity_type: str = Field(..., min_length=1, max_length=128)
    activity_value: float = Field(..., gt=0, description="Must be greater than zero")
    activity_unit: str = Field(..., min_length=1, max_length=32)
    period: str | None = Field(default=None, max_length=32)

    @field_validator("source")
    @classmethod
    def _valid_source(cls, v: str) -> str:
        v = v.strip().lower()
        if not is_valid_source(v):
            raise ValueError(
                f"Unsupported source '{v}'. Supported: {', '.join(SOURCE_CONFIG)}"
            )
        return v

    @field_validator("activity_unit")
    @classmethod
    def _unit_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Activity unit is required.")
        return v.strip()

    def validate_unit_for_source(self) -> None:
        units = allowed_units(self.source)
        if self.activity_unit not in units:
            raise ValueError(
                f"Unit '{self.activity_unit}' is not valid for source "
                f"'{self.source}'. Allowed units: {', '.join(units)}"
            )


class EmissionRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    activity_type: str
    activity_value: float
    activity_unit: str
    co2e: float
    co2e_unit: str
    emission_factor_reference: str | None
    calculation_source: str
    period: str | None
    created_at: datetime


class SourceBreakdown(BaseModel):
    source: str
    label: str
    co2e: float
    co2e_unit: str
    contribution_pct: float
    record_count: int


class HotspotSummary(BaseModel):
    total_co2e: float
    co2e_unit: str
    record_count: int
    by_source: list[SourceBreakdown]
    highest_source: str | None
    highest_source_label: str | None
    highest_source_co2e: float | None
    highest_source_pct: float | None
    calculation_note: str


class SourceMeta(BaseModel):
    source: str
    label: str
    activity_types: list[str]
    allowed_units: list[str]
    default_unit: str
    help: str
