"""
Turn pipeline stages — interpret → resolve → narrate → record.

story_loop.process_player_action follows this order; tests can target each
stage via pure helpers in action_interpreter, action_resolution, skill_check.
"""

STAGES = ("interpret", "resolve", "mechanics", "narrate", "record")
