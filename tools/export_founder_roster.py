"""Print the twenty founders' stable IDs and gameplay-derived identities.

Usage:
    python tools/export_founder_roster.py --seed 16
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
from campaign import Campaign

ROLES = ("수호형", "무인형", "사수형", "주술형", "치유형", "암살형")


def export(seed):
    campaign = Campaign(seed=seed)
    members = sorted(campaign.guild.fighters, key=lambda f: f.fid)
    return {
        "seed": seed, "guild": campaign.guild.name,
        "founders": [
            {"fid": f.fid, "name": f.name, "role_id": f.role,
             "role": ROLES[f.role], "age": f.age, "level": f.lv}
            for f in members
        ]
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=16)
    args = parser.parse_args()
    data = export(args.seed)
    print("FOUNDER_ROSTER_JSON=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
