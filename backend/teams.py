"""Explicit team roster; unknown names never default to a known team."""

import json
import os
from pathlib import Path

def load_config():
    path = Path(os.getenv("TEAM_CONFIG_FILE", ".credentials/teams.json"))
    if not path.exists():
        return {"teams": [{"id": "AI", "name": "AI팀", "members": []},
                          {"id": "SW", "name": "SW팀", "members": []}], "aliases": {}}
    config = json.loads(path.read_text("utf-8-sig"))
    for team in config["teams"]:
        if team["id"] not in {"AI", "SW"} or not isinstance(team["members"], list):
            raise ValueError("Invalid team configuration")
        if not all(isinstance(member, str) and member.strip() for member in team["members"]):
            raise ValueError("Invalid member configuration")
    return config

CONFIG = load_config()
TEAMS = CONFIG["teams"]


def normalize(name):
    return "".join(str(name or "").split()).casefold()


ROSTER = {normalize(member): team["id"] for team in TEAMS for member in team["members"]}
ALIASES = {normalize(alias): normalize(person) for alias, person in CONFIG.get("aliases", {}).items()}
if any(person not in ROSTER for person in ALIASES.values()):
    raise ValueError("Alias must reference a configured member")
ROSTER.update({alias: ROSTER[person] for alias, person in ALIASES.items()})


def team_for(person):
    return ROSTER.get(normalize(person), "unassigned")


def annotate(event):
    if event.get("kind") != "leave":
        return dict(event)
    team = team_for(event.get("person"))
    result = {**event, "team": team, "teamName": {"AI": "AI팀", "SW": "SW팀"}.get(team, "미분류")}
    # Presentation only, after source reconciliation: never infer a source slot.
    if event.get("amount") == 0.5 and not any(
        slot in str(event.get("leaveType", "")) for slot in ("오전", "오후")
    ):
        result.update(
            displayLeaveType="오전반차",
            displayTitle=f'{event.get("person", "")} · 오전반차',
            timeSlotNote="시간대 미명시 · 오전으로 임시 표시",
        )
    return result
