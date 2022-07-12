#!/usr/bin/env python3
import argparse
import operator
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

MYCROFT_TARGET = "mycroft"
SKILLS_TARGET = "skills"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--service",
        action="append",
        default=[],
        nargs=2,
        metavar=("priority", "dir"),
        help="Priority and path to service directory",
    )
    parser.add_argument(
        "--skill", action="append", default=[], help="Path to skill directory"
    )
    args = parser.parse_args()

    config_home = Path(
        os.environ.get("XDG_CONFIG_HOME", Path("~/.config").expanduser())
    )

    # Directory to write systemd unit files
    unit_dir = config_home / "systemd" / "user"
    unit_dir.mkdir(parents=True, exist_ok=True)

    services: Dict[int, Set[str]] = defaultdict(set)
    for priority, service_dir in args.service:
        services[priority].add(service_dir)

    skills_service_path = None
    sorted_services = sorted(services.items(), key=operator.itemgetter(0))
    all_service_ids = set()
    after_services = set()
    for priority, service_dirs in sorted_services:
        service_ids = set()
        service_paths = []
        for service_dir in service_dirs:
            service_path = Path(service_dir)
            service_id = service_path.name

            if service_id == SKILLS_TARGET:
                skills_service_path = service_path
                service_ids.add(f"{SKILLS_TARGET}.target")
            else:
                service_path = Path(service_dir)
                service_id = f"{service_path.name}.service"
                venv_dir = (
                    config_home / "mycroft" / "services" / service_path.name / ".venv"
                )
                service_paths.append(service_path)
                service_ids.add(service_id)

                with open(
                    unit_dir / f"mycroft-{service_id}", "w", encoding="utf-8"
                ) as f:
                    print("[Unit]", file=f)
                    print(
                        "Description=", "Mycroft service ", service_id, sep="", file=f
                    )
                    print("PartOf=", MYCROFT_TARGET, ".target", sep="", file=f)
                    if after_services:
                        print(
                            "After=",
                            " ".join(f"mycroft-{id}" for id in after_services),
                            sep="",
                            file=f,
                        )

                    print("", file=f)
                    print("[Service]", file=f)
                    print("Type=notify", file=f)
                    print(
                        "Environment=PYTHONPATH=",
                        service_path.absolute(),
                        sep="",
                        file=f,
                    )
                    print(
                        "ExecStart=", venv_dir, "/bin/python -m service", sep="", file=f
                    )
                    print("Restart=always", file=f)
                    print("RestartSec=1", file=f)
                    print("TimeoutSec=10", file=f)
                    print("WatchdogSec=5", file=f)
                    print("StandardOutput=journal", file=f)
                    print("StandardError=journal", file=f)

                    print("", file=f)
                    print("[Install]", file=f)
                    print("WantedBy=", MYCROFT_TARGET, ".target", sep="", file=f)

        after_services = service_ids
        all_service_ids.update(service_ids)

    if args.skill:
        assert skills_service_path, f"No service named {SKILLS_TARGET}"
        _write_skills_target(skills_service_path, args.skill, config_home, unit_dir)

    _write_mycroft_target(all_service_ids, unit_dir)


def _write_mycroft_target(service_ids: Set[str], unit_dir: Path):
    with open(unit_dir / f"{MYCROFT_TARGET}.target", "w", encoding="utf-8") as f:
        print("[Unit]", file=f)
        print("Description=", MYCROFT_TARGET, ".target", sep="", file=f)
        print(
            "Requires=",
            " ".join(f"mycroft-{id}" for id in service_ids),
            sep="",
            file=f,
        )


def _write_skills_target(
    skills_service_path: Path, skill_dirs: List[str], config_home: Path, unit_dir: Path
):
    skill_paths = [Path(d) for d in skill_dirs]
    skill_ids = {p.name for p in skill_paths}
    service_ids = [f"mycroft-skill-{id}.service" for id in skill_ids]

    with open(unit_dir / f"mycroft-{SKILLS_TARGET}.target", "w", encoding="utf-8") as f:
        print("[Unit]", file=f)
        print("Description=", "Mycroft skills", sep="", file=f)
        print("PartOf=", MYCROFT_TARGET, ".target", sep="", file=f)
        print("Requires=", " ".join(service_ids), sep="", file=f)

    for skill_path in skill_paths:
        skill_id = skill_path.name
        venv_dir = config_home / "mycroft" / "skills" / skill_id / ".venv"
        with open(
            unit_dir / f"mycroft-skill-{skill_id}.service", "w", encoding="utf-8"
        ) as f:
            print("[Unit]", file=f)
            print("PartOf=", "mycroft-", SKILLS_TARGET, ".target", sep="", file=f)
            print("Description=", "Mycroft skill ", skill_id, sep="", file=f)

            print("", file=f)
            print("[Service]", file=f)
            print("Type=notify", file=f)
            print(
                "Environment=PYTHONPATH=",
                skills_service_path.absolute(),
                sep="",
                file=f,
            )
            print(
                "ExecStart=",
                venv_dir,
                "/bin/python -m service ",
                "--skill-directory '",
                skill_path.absolute(),
                "' --skill-id '",
                skill_id,
                "'",
                sep="",
                file=f,
            )
            print("Restart=always", file=f)
            print("RestartSec=1", file=f)
            print("TimeoutSec=10", file=f)
            print("WatchdogSec=5", file=f)
            print("StandardOutput=journal", file=f)
            print("StandardError=journal", file=f)

            print("", file=f)
            print("[Install]", file=f)
            print("WantedBy=", SKILLS_TARGET, ".target", sep="", file=f)


if __name__ == "__main__":
    main()
