"""Admin command line. Run from backend/:

uv run python -m app.cli seed                 # topics + demo questions (idempotent)
uv run python -m app.cli import-topics [FILE ...]
uv run python -m app.cli seed-questions
uv run python -m app.cli make-admin USERNAME  # sign up in the app first
uv run python -m app.cli remove-admin USERNAME
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import func, select

from app.config import get_settings
from app.db import Database
from app.models import User
from app.services.content import (
    TOPIC_FILES,
    apply_catalog,
    apply_seed_questions,
    load_catalog,
    load_question_files,
)


async def _run(args: argparse.Namespace) -> int:
    db = Database(get_settings())
    try:
        async with db.sessionmaker() as session:
            if args.command in ("seed", "import-topics"):
                paths = [Path(p) for p in getattr(args, "files", [])] or list(TOPIC_FILES)
                stats = await apply_catalog(session, load_catalog(paths))
                print("topics:", stats.as_dict())
            if args.command in ("seed", "seed-questions"):
                qstats = await apply_seed_questions(session, load_question_files())
                print(f"questions: {qstats.created} added, {qstats.skipped} already there")
            if args.command in ("make-admin", "remove-admin"):
                user = await session.scalar(
                    select(User).where(func.lower(User.username) == args.username.lower())
                )
                if user is None:
                    print(f"No user called {args.username!r}. Sign up in the app first.")
                    return 1
                user.is_admin = args.command == "make-admin"
                print(f"{user.username} is {'now' if user.is_admin else 'no longer'} an admin.")
            await session.commit()
    finally:
        await db.dispose()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed", help="Import topics and demo questions (safe to re-run)")
    imp = sub.add_parser("import-topics", help="Import/refresh the subject and topic list")
    imp.add_argument("files", nargs="*", help="Topic JSON files (default: the seed files)")
    sub.add_parser("seed-questions", help="Add the hand-checked demo questions")
    for name in ("make-admin", "remove-admin"):
        p = sub.add_parser(name)
        p.add_argument("username")
    return asyncio.run(_run(parser.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
