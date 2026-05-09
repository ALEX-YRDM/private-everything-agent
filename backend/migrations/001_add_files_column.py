"""Migration: Add files column to messages table for file attachment support."""
import aiosqlite
from loguru import logger


async def migrate(db: aiosqlite.Connection) -> None:
    """Add files JSON column to messages table."""
    try:
        # Check if column already exists
        cursor = await db.execute("PRAGMA table_info(messages)")
        columns = await cursor.fetchall()
        column_names = {row[1] for row in columns}

        if "files" in column_names:
            logger.info("Column 'files' already exists in messages table, skipping migration")
            return

        # Add files column
        await db.execute("""
            ALTER TABLE messages ADD COLUMN files JSON DEFAULT NULL
        """)
        await db.commit()
        logger.info("Successfully added 'files' column to messages table")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


async def rollback(db: aiosqlite.Connection) -> None:
    """Rollback: Remove files column from messages table."""
    try:
        # SQLite doesn't support DROP COLUMN directly in older versions
        # For now, we'll just log a message
        logger.warning("Rollback for file column migration not fully supported in SQLite")
        # In production, you might create a new table and migrate data
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        raise
