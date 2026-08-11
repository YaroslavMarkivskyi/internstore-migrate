from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HourlyAggregateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hour_bucket: datetime
    avg_temperature: float
    min_temperature: float
    max_temperature: float
    reading_count: int
