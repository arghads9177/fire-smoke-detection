"""The key false-positive defense (plan §3.2): confidence thresholds
(fire > 0.80 CRITICAL, smoke > 0.75 WARNING), debounce (N consecutive
positive frames, default 3), and per-camera+type cooldown (default 60 s)
with a "cleared" update after M consecutive negative frames.

Keep these pure functions / simple state machines — they are unit-tested
directly. Temporal validation beyond debounce is Phase 2 and slots in here.
"""
