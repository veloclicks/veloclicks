"""Expose bounded durable work to Zappa scheduling and Docker."""

from time import monotonic, sleep

import click
from flask import current_app
from flask.cli import with_appcontext

from app.models import db
from . import snapshots, synchronisation


def run_batch() -> None:
    """Drain a bounded number of steps within a scheduled invocation."""
    started = monotonic()
    for _ in range(8):
        synced = synchronisation.process_one(current_app.config.get("STRAVA_CLIENT_ID"),
                                               current_app.config.get("STRAVA_CLIENT_SECRET"))
        # Give snapshots a chance even when history continuously has work.
        published = snapshots.process_one() if monotonic() - started < 25 else False
        if not (synced or published) or monotonic() - started >= 25:
            break


def tick(event=None, context=None) -> None:
    """Run the scheduled Zappa entry point in an application context."""
    from app import application

    with application.app_context():
        run_batch()


@click.command("activities-worker")
@click.option("--watch", is_flag=True)
@with_appcontext
def worker_command(watch: bool) -> None:
    """Process durable jobs once or watch the local database for work."""
    while True:
        try:
            run_batch()
        except Exception as error:
            db.session.rollback()
            if not watch:
                raise
            current_app.logger.error("activity_worker_failed error=%s", type(error).__name__)
        finally:
            db.session.remove()
        if not watch:
            return
        sleep(2)


@click.command("seed-activity-snapshot")
@click.argument("user_id", type=int)
@with_appcontext
def seed_command(user_id: int) -> None:
    """Seed one private snapshot before enabling the new UI."""
    try:
        published = snapshots.seed(user_id)
    except (RuntimeError, ValueError) as error:
        raise click.ClickException(str(error)) from error
    if not published:
        raise click.ClickException("Snapshot publication failed or is already in progress.")
    click.echo("Activity snapshot verified.")
