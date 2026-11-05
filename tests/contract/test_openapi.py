import json
import pathlib
from app.core.config import Settings
from app.main import create_app

SNAP = pathlib.Path(__file__).with_name("openapi.snapshot.json")


def test_openapi_matches_snapshot():
    app = create_app(Settings(env="test"), check_gates=False)
    assert json.loads(SNAP.read_text()) == json.loads(json.dumps(app.openapi())), \
        "API contract changed: review, then run `python scripts/export_openapi.py`"


def test_contract_has_no_clinical_vocabulary_or_admin_routes():
    text = SNAP.read_text().lower()
    for word in ("diagnos", "risk_level", "severity", "probability", "/admin"):
        assert word not in text.replace("not a medical device, diagnosis or screening tool", "")
    assert "/api/v1/inference/predict" in text  # interface exists; behaviour tested separately
