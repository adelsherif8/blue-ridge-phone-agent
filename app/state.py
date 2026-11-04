"""Process-wide state shared by the server and the bot (one process on Render)."""

from app.schedule import Board

BOARD = Board()  # a real deployment would use a database
