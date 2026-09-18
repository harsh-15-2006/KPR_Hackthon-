from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReductionActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    action_name: str
    description: str
    cost: float | None
    expected_reduction: float | None
    implementation_time: str | None
    availability: str
    data_source: str
    created_at: datetime
    updated_at: datetime
