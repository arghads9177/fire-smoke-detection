"""Unit tests for the debounce/cooldown state machine (plan §6: pure functions,
tested directly). Time is passed in, so no sleeps anywhere."""

from typing import Any

from app.alert_logic import Action, AlertState, build_states
from shared.schemas import DetectionSettings


def make_state(**overrides) -> AlertState:
    defaults: dict[str, Any] = dict(threshold=0.80, debounce_frames=3, cooldown_seconds=60.0)
    defaults.update(overrides)
    return AlertState(**defaults)


def feed(state: AlertState, confidences, start=0.0, step=0.33):
    """Feed a sequence of frame confidences; returns the actions per frame."""
    return [state.update(c, start + i * step) for i, c in enumerate(confidences)]


class TestThreshold:
    def test_below_threshold_never_raises(self):
        state = make_state()
        assert feed(state, [0.79] * 20) == [None] * 20

    def test_exactly_at_threshold_is_negative(self):
        # plan §3.2: confidence > 0.80, strictly greater
        state = make_state()
        assert feed(state, [0.80] * 10) == [None] * 10


class TestDebounce:
    def test_raises_on_nth_consecutive_positive(self):
        state = make_state(debounce_frames=3)
        assert feed(state, [0.9, 0.9, 0.9]) == [None, None, Action.RAISE]

    def test_single_frame_flash_discarded(self):
        # welding spark: one hot frame between cold ones
        state = make_state(debounce_frames=3)
        assert feed(state, [0.0, 0.95, 0.0, 0.95, 0.0]) == [None] * 5

    def test_negative_frame_resets_streak(self):
        state = make_state(debounce_frames=3)
        actions = feed(state, [0.9, 0.9, 0.1, 0.9, 0.9, 0.9])
        assert actions == [None, None, None, None, None, Action.RAISE]

    def test_debounce_of_one_raises_immediately(self):
        state = make_state(debounce_frames=1)
        assert feed(state, [0.9]) == [Action.RAISE]

    def test_reports_max_confidence_over_window(self):
        state = make_state(debounce_frames=3)
        feed(state, [0.85, 0.95, 0.88])
        assert state.episode_max_confidence == 0.95


class TestCooldown:
    def test_suppresses_duplicates_within_window(self):
        state = make_state(debounce_frames=1, cooldown_seconds=60.0)
        assert state.update(0.9, now=0.0) is Action.RAISE
        # condition persists: stays quiet until the cooldown elapses
        assert state.update(0.9, now=30.0) is None
        assert state.update(0.9, now=59.9) is None

    def test_reraises_after_cooldown_expires(self):
        state = make_state(debounce_frames=1, cooldown_seconds=60.0)
        assert state.update(0.9, now=0.0) is Action.RAISE
        assert state.update(0.9, now=60.0) is Action.RAISE
        # and the window restarts from the re-raise
        assert state.update(0.9, now=90.0) is None
        assert state.update(0.9, now=120.0) is Action.RAISE


class TestClear:
    def test_clears_after_m_consecutive_negatives(self):
        state = make_state(debounce_frames=2, clear_frames=3)
        feed(state, [0.9, 0.9])  # raise
        assert state.active
        actions = feed(state, [0.1, 0.1, 0.1])
        assert actions == [None, None, Action.CLEAR]
        assert not state.active

    def test_brief_dip_does_not_clear(self):
        state = make_state(debounce_frames=1, clear_frames=3)
        state.update(0.9, 0.0)
        actions = feed(state, [0.1, 0.1, 0.9], start=1.0)
        assert Action.CLEAR not in actions
        assert state.active

    def test_no_clear_when_never_active(self):
        state = make_state()
        assert feed(state, [0.1] * 10) == [None] * 10

    def test_can_raise_again_after_clear(self):
        state = make_state(debounce_frames=2, clear_frames=2, cooldown_seconds=60.0)
        assert feed(state, [0.9, 0.9])[-1] is Action.RAISE
        assert feed(state, [0.0, 0.0], start=1.0)[-1] is Action.CLEAR
        # a new episode is not bound by the previous cooldown window
        assert feed(state, [0.9, 0.9], start=2.0)[-1] is Action.RAISE
        assert state.episode_max_confidence == 0.9


class TestBuildStates:
    def test_per_type_thresholds_from_settings(self):
        settings = DetectionSettings()  # plan defaults
        states = build_states(settings)
        assert states["FIRE"].threshold == 0.80
        assert states["SMOKE"].threshold == 0.75
        assert states["FIRE"].debounce_frames == 3
        assert states["FIRE"].cooldown_seconds == 60.0

    def test_states_are_independent(self):
        states = build_states(DetectionSettings(debounceFrames=1))
        assert states["FIRE"].update(0.9, 0.0) is Action.RAISE
        assert not states["SMOKE"].active
