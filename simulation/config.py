"""Config loading (UTF-8 explicit so Windows code pages never garble the YAML)."""
import os

import yaml

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")


def load(name):
    """load("drainage") -> dict from config/drainage.yaml"""
    path = name if name.endswith(".yaml") else os.path.join(CONFIG_DIR, f"{name}.yaml")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_all():
    return {k: load(k) for k in ("terrain", "drainage", "rainfall", "hydraulics", "simulation")}
