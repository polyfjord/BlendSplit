"""Session state and redraw scheduling for BlendSplit."""

from __future__ import annotations

from typing import TYPE_CHECKING

import bpy

from .core import RunEngine

if TYPE_CHECKING:
    from .properties import BlendSplitSettings


engine = RunEngine()
active_scene_name: str | None = None
last_gold_index: int | None = None
_best_before_split: list[tuple[int, float] | None] = []
_comparison_pb: list[float] = []
_timer_registered = False


def settings_for_context(context: bpy.types.Context) -> "BlendSplitSettings":
    if engine.is_active or engine.state.value == "FINISHED":
        scene = bpy.data.scenes.get(active_scene_name) if active_scene_name else None
        if scene is not None:
            return scene.blendsplit
    return context.scene.blendsplit


def begin_run(scene: bpy.types.Scene) -> None:
    global active_scene_name, last_gold_index, _pb_before_finish
    settings = scene.blendsplit
    # With no split setup, behave as a simple start/finish timer. Keeping the
    # synthetic segment in the engine (rather than the scene) leaves starter
    # splits and random challenges entirely optional.
    engine.start(max(1, len(settings.splits)))
    settings.attempts += 1
    active_scene_name = scene.name
    last_gold_index = None
    _pb_before_finish = None
    _best_before_split.clear()
    _comparison_pb[:] = (
        [item.pb_time for item in settings.splits]
        if settings.splits
        else [settings.timer_only_pb]
    )
    _persist_profile(settings)
    tag_view3d_redraw()


def comparison_pb_time(index: int) -> float:
    """Return the PB captured when this attempt began, or -1 if unavailable."""
    return _comparison_pb[index] if 0 <= index < len(_comparison_pb) else -1.0


def comparison_segment_pb_time(index: int) -> float:
    """Return the captured segment duration when this attempt began, or -1 if unavailable."""
    if not 0 <= index < len(_comparison_pb):
        return -1.0
    
    current = _comparison_pb[index]

    if current < 0:
        return -1.0
    
    previous = _comparison_pb[index - 1] if index > 0 else 0.0

    if previous < 0:
        return -1.0
    
    return current - previous


def current_segment_elapsed_ns() -> int:
    """Return the current elapsed time for the active segment"""
    elapsed = engine.elapsed_ns()

    if engine.current_index == 0:
        return elapsed
    
    previous = engine.results[engine.current_index - 1]

    if previous.cumulative_ns is None:
        return elapsed

    return max(0, elapsed - previous.cumulative_ns)


def record_split(settings: "BlendSplitSettings") -> None:
    global last_gold_index, _pb_before_finish
    result = engine.split()
    if result.index >= len(settings.splits):
        finish = result.cumulative_ns
        old_pb = settings.timer_only_pb
        if finish is not None and (old_pb < 0 or finish < seconds_to_ns(old_pb)):
            _pb_before_finish = [old_pb]
            settings.timer_only_pb = finish / 1_000_000_000
        else:
            _pb_before_finish = None
        _persist_profile(settings)
        tag_view3d_redraw()
        return

    item = settings.splits[result.index]
    old_best = item.best_segment
    if result.segment_ns is not None and (old_best < 0 or result.segment_ns < seconds_to_ns(old_best)):
        item.best_segment = result.segment_ns / 1_000_000_000
        _best_before_split.append((result.index, old_best))
        last_gold_index = result.index
    else:
        _best_before_split.append(None)
        last_gold_index = None

    if engine.state.value == "FINISHED":
        _complete_run(settings)
    _persist_profile(settings)
    tag_view3d_redraw()


def record_skip() -> None:
    global last_gold_index
    engine.skip()
    _best_before_split.append(None)
    last_gold_index = None
    tag_view3d_redraw()


def undo_split(settings: "BlendSplitSettings") -> None:
    global last_gold_index
    was_finished = engine.state.value == "FINISHED"
    engine.undo()
    previous = _best_before_split.pop() if _best_before_split else None
    if previous is not None:
        index, old_best = previous
        settings.splits[index].best_segment = old_best

    # A finished run may have become the PB. Undoing it must not leave partial
    # PB data. The previous PB is cached only for the duration of completion.
    if was_finished and _pb_before_finish is not None:
        if settings.splits:
            for item, value in zip(settings.splits, _pb_before_finish, strict=False):
                item.pb_time = value
        else:
            settings.timer_only_pb = _pb_before_finish[0]
    last_gold_index = None
    _persist_profile(settings)
    tag_view3d_redraw()


_pb_before_finish: list[float] | None = None


def _complete_run(settings: "BlendSplitSettings") -> None:
    global _pb_before_finish
    results = engine.results
    if any(result.skipped for result in results):
        _pb_before_finish = None
        return
    finish = engine.finished_elapsed_ns
    old_finish = settings.splits[-1].pb_time
    if finish is None or (old_finish >= 0 and finish >= seconds_to_ns(old_finish)):
        _pb_before_finish = None
        return
    _pb_before_finish = [item.pb_time for item in settings.splits]
    for item, result in zip(settings.splits, results, strict=True):
        assert result.cumulative_ns is not None
        item.pb_time = result.cumulative_ns / 1_000_000_000


def reset_run() -> None:
    global active_scene_name, last_gold_index, _pb_before_finish
    engine.reset()
    active_scene_name = None
    last_gold_index = None
    _pb_before_finish = None
    _best_before_split.clear()
    _comparison_pb.clear()
    tag_view3d_redraw()


def abandon_run() -> None:
    """Reset session state without touching any Blender UI.

    Used during unregistration, when contexts and windows may already be in
    teardown.
    """
    global active_scene_name, last_gold_index, _pb_before_finish
    engine.reset()
    active_scene_name = None
    last_gold_index = None
    _pb_before_finish = None
    _best_before_split.clear()
    _comparison_pb.clear()


def seconds_to_ns(value: float) -> int:
    return round(value * 1_000_000_000)


def _persist_profile(settings: "BlendSplitSettings") -> None:
    from . import profiles
    from .profile_store import ProfileStoreError

    try:
        profiles.save_linked_profile(settings)
    except ProfileStoreError as error:
        print(f"BlendSplit: could not save profile: {error}")


def tag_view3d_redraw() -> None:
    window_manager = getattr(bpy.context, "window_manager", None)
    if window_manager is None:
        return
    for window in window_manager.windows:
        screen = window.screen
        if screen is None:
            continue
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def _redraw_timer() -> float:
    tag_view3d_redraw()
    return 1.0 / 30.0 if engine.is_active else 0.25


def register_timer() -> None:
    global _timer_registered
    if not bpy.app.timers.is_registered(_redraw_timer):
        bpy.app.timers.register(_redraw_timer, first_interval=0.1, persistent=True)
    _timer_registered = True


def unregister_timer() -> None:
    global _timer_registered
    if bpy.app.timers.is_registered(_redraw_timer):
        bpy.app.timers.unregister(_redraw_timer)
    _timer_registered = False
    abandon_run()
