import json
from pathlib import Path
import pytest
from backend import teams


@pytest.fixture(autouse=True)
def synthetic_roster(monkeypatch):
    config = json.loads((Path(__file__).parent / "fixtures" / "teams.json").read_text("utf-8"))
    roster = {teams.normalize(member): team["id"] for team in config["teams"] for member in team["members"]}
    aliases = {teams.normalize(alias): teams.normalize(person) for alias, person in config["aliases"].items()}
    roster.update({alias: roster[person] for alias, person in aliases.items()})
    monkeypatch.setattr(teams, "ROSTER", roster)
    monkeypatch.setattr(teams, "DEPARTMENTS", {teams.normalize("Example Research"): "AI", teams.normalize("Example Engineering"): "SW"})
    monkeypatch.setattr(teams, "ALIASES", aliases)
    monkeypatch.setattr("backend.browser_import.ALIASES", aliases)
