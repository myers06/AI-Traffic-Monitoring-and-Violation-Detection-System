import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def load_config(path=None) -> dict:
    load_dotenv(ROOT / ".env")
    cfg_path = Path(path or os.getenv("CONFIG_PATH") or ROOT / "config" / "config.yaml")
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path

    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if os.getenv("MODEL_WEIGHTS"):
        cfg["model"]["weights"] = os.environ["MODEL_WEIGHTS"]
    if os.getenv("DEVICE"):
        cfg["model"]["device"] = os.environ["DEVICE"]
    if os.getenv("OUTPUT_DIR"):
        cfg["output"]["dir"] = os.environ["OUTPUT_DIR"]

    out = Path(cfg["output"]["dir"])
    cfg["output"]["dir"] = str(out if out.is_absolute() else ROOT / out)
    return cfg