# Partial-update schema for PUT /settings (plan §3.3 `settings` doc).
# GET /settings returns the shared DetectionSettings model directly.

from pydantic import BaseModel, Field


class SettingsUpdate(BaseModel):
    fireThreshold: float | None = Field(default=None, gt=0.0, lt=1.0)
    smokeThreshold: float | None = Field(default=None, gt=0.0, lt=1.0)
    debounceFrames: int | None = Field(default=None, ge=1)
    cooldownSeconds: float | None = Field(default=None, ge=0.0)
