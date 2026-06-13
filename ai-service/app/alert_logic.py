"""The key false-positive defense (plan §3.2): confidence thresholds
(fire > 0.80 CRITICAL, smoke > 0.75 WARNING), debounce (N consecutive
positive frames, default 3), and per-camera+type cooldown (default 60 s)
with a "cleared" update after M consecutive negative frames.

Pure state machines driven by (confidence, now) — no clocks, I/O, or model
references — so they are unit-tested directly. Temporal validation beyond
debounce is Phase 2 and slots in here.
"""

from enum import Enum

from shared.schemas import DetectionSettings, DetectionType


class Action(Enum):
    """What the caller should do after feeding one sampled frame."""

    RAISE = "raise"  # debounce satisfied (or cooldown expired): POST a DETECTED event
    CLEAR = "clear"  # condition gone for enough frames: POST a CLEARED event


class AlertState:
    """Debounce/cooldown state for one camera + one detection type.

    Feed `update()` the max confidence of that type for every sampled frame
    (0.0 when absent). Strictly-greater threshold comparison per plan §3.2.
    """

    def __init__(
        self,
        threshold: float,
        debounce_frames: int,
        cooldown_seconds: float,
        clear_frames: int | None = None,
    ):
        self.threshold = threshold
        self.debounce_frames = debounce_frames
        self.cooldown_seconds = cooldown_seconds
        # M consecutive negative frames before "cleared"; defaults to the debounce N
        self.clear_frames = clear_frames if clear_frames is not None else debounce_frames

        self.active = False
        self.episode_max_confidence = 0.0
        self._hits = 0
        self._misses = 0
        self._last_raised_at = 0.0

    def update(self, confidence: float, now: float) -> Action | None:
        """Advance the state machine one sampled frame. `now` is a monotonic timestamp."""
        if confidence > self.threshold:
            self._hits += 1
            self._misses = 0
            self.episode_max_confidence = max(self.episode_max_confidence, confidence)
            if not self.active:
                if self._hits >= self.debounce_frames:
                    self.active = True
                    self._last_raised_at = now
                    return Action.RAISE
            elif now - self._last_raised_at >= self.cooldown_seconds:
                # Condition persists past the cooldown window: re-send so the
                # backend refreshes lastSeenAt/maxConfidence (it dedups, §3.3).
                self._last_raised_at = now
                return Action.RAISE
        else:
            self._hits = 0
            self._misses += 1
            if self.active and self._misses >= self.clear_frames:
                self.active = False
                self.episode_max_confidence = 0.0
                return Action.CLEAR
        return None


def build_states(settings: DetectionSettings) -> dict[DetectionType, AlertState]:
    """The per-camera pair of state machines, keyed by detection type."""
    return {
        "FIRE": AlertState(
            settings.fireThreshold, settings.debounceFrames, settings.cooldownSeconds
        ),
        "SMOKE": AlertState(
            settings.smokeThreshold, settings.debounceFrames, settings.cooldownSeconds
        ),
    }
