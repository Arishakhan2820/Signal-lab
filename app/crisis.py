from __future__ import annotations
import json
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, model_validator

router = APIRouter(tags=["crisis"])
GENERIC = ("If you are struggling or in danger, contact local emergency services or someone you trust. "
           "This app does not monitor you or contact anyone on your behalf.")


class Resource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    label: str
    type: str
    contact: str | None = None
    hours: str | None = None
    languages: list[str] = []
    source_url: str | None = None
    verified_by: str | None = None
    verified_at: str | None = None
    status: Literal["unverified", "verified"] = "unverified"

    @model_validator(mode="after")
    def _verified_needs_evidence(self):
        if self.status == "verified" and not (self.verified_by and self.verified_at and self.source_url):
            raise ValueError("verified resources need verified_by, verified_at and source_url")
        return self


class CountryFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    country: str
    resources: list[Resource]


def load_resources(directory: str, country: str) -> list[Resource]:
    path = Path(directory) / f"crisis_resources.{country}.json"
    if not path.exists():
        return []
    return CountryFile.model_validate(json.loads(path.read_text())).resources


def verified_only(resources: list[Resource]) -> list[Resource]:
    return [r for r in resources if r.status == "verified"]


@router.get("/crisis-resources")
def crisis_resources(request: Request):
    s = request.app.state.settings
    res = verified_only(load_resources(s.crisis_dir, s.country))
    return {"country": s.country, "resources": [r.model_dump() for r in res], "guidance": GENERIC}
