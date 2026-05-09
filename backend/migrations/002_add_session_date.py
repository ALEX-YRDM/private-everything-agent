"""
Migration: Add session_date column to sessions table for cache consistency.
This column stores the fixed date when the session was first used,
ensuring consistent timestamps in system prompts for prompt caching.
"""


async def migrate(db):
    """Add session_date column if it doesn't exist."""
    if db is None:
        return

    try:
        # Check if column already exists
        cursor = await db.execute("PRAGMA table_info(sessions)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

        if "session_date" not in column_names:
            await db.execute("ALTER TABLE sessions ADD COLUMN session_date TEXT DEFAULT NULL")
            await db.commit()
    except Exception as e:
        raise Exception(f"Failed to add session_date column: {e}")
