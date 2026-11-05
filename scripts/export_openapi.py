"""Regenerate the API contract snapshot:  python scripts/export_openapi.py"""
import json
import pathlib
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.core.config import Settings
from app.main import create_app

app = create_app(Settings(env="test"), check_gates=False)
out = pathlib.Path(__file__).resolve().parents[1] / "tests/contract/openapi.snapshot.json"
out.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")
print("wrote", out)
