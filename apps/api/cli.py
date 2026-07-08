"""Command-Line Interface & REPL (M5 Phase 5)."""

import argparse
import sys
import code

from api.app import create_app
from api.container import build_default_subsystems


def trigger_brain(site_id: str) -> None:
    """Trigger the Brain synthesis for a site."""
    app = create_app()
    brain_container = getattr(app.state, "brain", None)
    if not brain_container:
        print("Brain engine is not enabled or not mounted.")
        sys.exit(1)
        
    synthesis = brain_container.seo_brain.generate_synthesis(brain_container.tenant_id, site_id)
    saved = brain_container.seo_brain.save_synthesis(brain_container.tenant_id, synthesis)
    print(f"Brain synthesis generated for site '{site_id}' (version {saved.version})")


def list_schedules() -> None:
    """List all registered schedules."""
    app = create_app()
    brain_container = getattr(app.state, "brain", None)
    if not brain_container:
        print("Brain engine is not enabled or not mounted.")
        sys.exit(1)
        
    schedules = brain_container.schedule_repo.list_schedules(brain_container.tenant_id)
    if not schedules:
        print("No schedules found.")
        return
        
    for sched in schedules:
        print(f"- {sched.schedule_id} | {sched.task_type} | {sched.cron_expression}")


def start_repl() -> None:
    """Start an interactive REPL with application context loaded."""
    app = create_app()
    subsystems = getattr(app.state, "subsystems", None)
    growth = getattr(app.state, "growth", None)
    brain = getattr(app.state, "brain", None)
    
    local_ctx = {
        "app": app,
        "subsystems": subsystems,
        "growth": growth,
        "brain": brain,
    }
    
    banner = (
        "Website Orchestrator REPL\n"
        "Available locals: app, subsystems, growth, brain"
    )
    code.interact(banner=banner, local=local_ctx)


def main() -> None:
    parser = argparse.ArgumentParser(description="Website Orchestrator CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Command: trigger-brain
    parser_trigger = subparsers.add_parser("trigger-brain", help="Trigger brain synthesis")
    parser_trigger.add_argument("site_id", help="The site ID to synthesize")
    
    # Command: list-schedules
    subparsers.add_parser("list-schedules", help="List all registered schedules")
    
    # Command: repl
    subparsers.add_parser("repl", help="Start an interactive Python REPL")

    args = parser.parse_args()

    if args.command == "trigger-brain":
        trigger_brain(args.site_id)
    elif args.command == "list-schedules":
        list_schedules()
    elif args.command == "repl":
        start_repl()


if __name__ == "__main__":
    main()
