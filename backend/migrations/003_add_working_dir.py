"""
Migration: Add working_dir column to sessions table for AI coding mode.

Each session can bind to an arbitrary working directory. When NULL,
the session falls back to the global workspace path (legacy behavior).
"""


async def migrate(db):
    """Add working_dir column if it doesn't exist."""
    if db is None:
        return

    cursor = await db.execute("PRAGMA table_info(sessions)")
    columns = await cursor.fetchall()
    column_names = [col[1] for col in columns]

    if "working_dir" not in column_names:
        await db.execute("ALTER TABLE sessions ADD COLUMN working_dir TEXT DEFAULT NULL")
        await db.commit()
