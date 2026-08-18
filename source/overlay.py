"""High-contrast 2D overlay drawn over the 3D Viewport."""

from __future__ import annotations

import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader

from . import icon_atlas, runtime
from .core import format_time, format_delta


_draw_handle: object | None = None
_shader: gpu.types.GPUShader | None = None

BG = (0.025, 0.028, 0.035, 0.95)
HEADER_BG = (0.055, 0.061, 0.075, 0.98)
ROW_CURRENT = (0.055, 0.20, 0.34, 0.95)
DIVIDER = (0.24, 0.27, 0.32, 0.8)
TEXT = (0.94, 0.95, 0.97, 1.0)
MUTED = (0.56, 0.59, 0.64, 1.0)
GREEN = (0.25, 0.95, 0.45, 1.0)
RED = (1.0, 0.32, 0.35, 1.0)
GOLD = (1.0, 0.78, 0.18, 1.0)


def _rect(x: float, y: float, width: float, height: float, color: tuple[float, float, float, float]) -> None:
    global _shader
    if _shader is None:
        _shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    vertices = ((x, y), (x + width, y), (x + width, y + height), (x, y + height))
    batch = batch_for_shader(_shader, "TRI_FAN", {"pos": vertices})
    _shader.bind()
    _shader.uniform_float("color", color)
    batch.draw(_shader)


def _text(
    value: str,
    x: float,
    y: float,
    size: int,
    color: tuple[float, float, float, float] = TEXT,
    *,
    right: float | None = None,
) -> None:
    font_id = 0
    blf.size(font_id, size)
    if right is not None:
        width, _height = blf.dimensions(font_id, value)
        x = right - width
    blf.position(font_id, x, y, 0)
    blf.color(font_id, *color)
    blf.draw(font_id, value)


def _fit_text(value: str, max_width: float, size: int) -> str:
    blf.size(0, size)
    if blf.dimensions(0, value)[0] <= max_width:
        return value
    shortened = value
    while shortened and blf.dimensions(0, shortened + "…")[0] > max_width:
        shortened = shortened[:-1]
    return shortened + "…" if shortened else ""


def _visible_range(total: int, current: int, count: int) -> range:
    if total <= count:
        return range(total)
    start = max(0, min(current - count // 2, total - count))
    return range(start, start + count)


def _row_label_width(
    width: float,
    pad: float,
    icon_space: float,
    value_width: float,
    relative_width: float,
    scale: float,
) -> float:
    """Use all row space except what an icon and visible time actually need."""
    space_value = 0.0

    if value_width > 0:
        space_value += value_width
    if relative_width > 0:
        space_value += relative_width + 10 * scale 
    if space_value > 0:
        space_value += 10 * scale

    return max(0.0, width - 2 * pad - icon_space - space_value)

def _overlay_position(
    region_width: float,
    region_height: float,
    anchor: str,
    margin_x: float,
    margin_y: float,
    width: float,
    height: float,
    left_inset: float = 0.0,
) -> tuple[float, float]:
    """Calculate a clamped overlay origin for all four viewport anchors."""
    x = region_width - margin_x - width if anchor.endswith("RIGHT") else margin_x + left_inset
    y = region_height - margin_y - height if anchor.startswith("TOP") else margin_y
    return (
        min(max(0.0, x), max(0.0, region_width - width)),
        min(max(0.0, y), max(0.0, region_height - height)),
    )


def _visible_toolbar_width(area: bpy.types.Area | None) -> int:
    """Return the visible left Tool System width, or zero when it is hidden."""
    if area is None:
        return 0
    tools = next((region for region in area.regions if region.type == "TOOLS"), None)
    return tools.width if tools is not None and tools.width > 1 else 0


def _draw_overlay() -> None:
    context = bpy.context
    if context.area is None or context.area.type != "VIEW_3D" or context.region is None:
        return
    if context.scene is None or not hasattr(context.scene, "blendsplit"):
        return

    settings = runtime.settings_for_context(context)
    if not settings.show_overlay:
        return

    ui_scale = context.preferences.system.ui_scale or 1.0
    scale = settings.overlay_scale * max(0.5, ui_scale)
    width = settings.overlay_width * scale
    title_height = 58 * scale
    row_height = 29 * scale
    footer_height = (64 if settings.show_pb else 54) * scale
    row_indices = _visible_range(len(settings.splits), runtime.engine.current_index, settings.visible_splits)
    height = title_height + len(row_indices) * row_height + footer_height
    margin_x = settings.overlay_offset_x * scale
    margin_y = settings.overlay_offset_y * scale
    toolbar_width = _visible_toolbar_width(context.area)
    left_inset = toolbar_width + 8 * scale if toolbar_width else 0.0

    x, y = _overlay_position(
        context.region.width,
        context.region.height,
        settings.overlay_anchor,
        margin_x,
        margin_y,
        width,
        height,
        left_inset,
    )

    opacity = settings.background_opacity
    gpu.state.blend_set("ALPHA")
    try:
        _rect(x, y, width, height, (*BG[:3], opacity))
        _rect(x, y + height - title_height, width, title_height, (*HEADER_BG[:3], min(1.0, opacity + 0.04)))

        pad = 13 * scale
        title_size = max(10, round(18 * scale))
        small_size = max(9, round(11 * scale))
        row_size = max(9, round(13 * scale))
        time_size = max(15, round(32 * scale))

        title_y = y + height - 28 * scale
        title = _fit_text(settings.run_title or "Untitled Run", width - 2 * pad, title_size)
        _text(title, x + pad, title_y, title_size)
        subtitle = settings.category or "Any%"
        if settings.show_attempts:
            subtitle += f"  •  Attempt {settings.attempts}"
        _text(_fit_text(subtitle, width - 2 * pad, small_size), x + pad, title_y - 20 * scale, small_size, MUTED)

        top = y + height - title_height
        decimals = int(settings.decimals)
        for display_row, split_index in enumerate(row_indices):
            item = settings.splits[split_index]
            row_y = top - (display_row + 1) * row_height
            is_current = runtime.engine.is_active and split_index == runtime.engine.current_index
            if is_current:
                _rect(x, row_y, width, row_height, ROW_CURRENT)
            _rect(x, row_y, width, max(1.0, scale), DIVIDER)

            result = runtime.engine.results[split_index] if split_index < len(runtime.engine.results) else None
            label_color = GOLD if split_index == runtime.last_gold_index else TEXT
            
            value = ""
            value_color = MUTED

            relative_time_value = ""
            relative_time_value_color = MUTED
            
            if result is not None:
                if result.skipped:
                    value = "—"
                    relative_time_value = "—"
                else:
                    value = format_time(result.cumulative_ns, decimals)
                    value_color = TEXT

                    if settings.show_relative_time:
                        current_segment = result.segment_ns
                        pb_segment = runtime.comparison_segment_pb_time(split_index)
                        if current_segment is not None and pb_segment >= 0:
                            relative_time_delta = (
                                current_segment 
                                - runtime.seconds_to_ns(pb_segment)
                            )
                            relative_time_value = format_delta(
                                relative_time_delta, 
                                decimals,
                            )
                            relative_time_value_color = (
                                GREEN if relative_time_delta <= 0 else RED
                            )
            elif is_current:
                value = format_time(
                    runtime.engine.elapsed_ns(),
                    decimals,
                )

                if settings.show_relative_time:
                    pb_segment = runtime.comparison_segment_pb_time(split_index)
    
                    if pb_segment >= 0:
                        current_segment = runtime.current_segment_elapsed_ns()
                        relative_time_delta = (
                            current_segment
                            - runtime.seconds_to_ns(pb_segment)
                        )
                        relative_time_value = format_delta(
                            relative_time_delta, 
                            decimals
                        )
                        relative_time_value_color = (
                            GREEN if relative_time_delta <= 0 else RED
                        )


            elif settings.show_pb and item.pb_time >= 0:
                value = format_time(runtime.seconds_to_ns(item.pb_time), decimals)

            label_x = x + pad
            icon_size = 17 * scale
            icon_y = row_y + (row_height - icon_size) * 0.5
            icon_space = 0.0
            if icon_atlas.draw_icon(item.blender_icon, label_x, icon_y, icon_size):
                icon_space = icon_size + 6 * scale
                label_x += icon_space
            blf.size(0, row_size)
            value_width = blf.dimensions(0, value)[0] if value else 0.0
            relative_width = blf.dimensions(0, relative_time_value)[0] if relative_time_value else 0.0
            
            value_right = x + width - pad
            relative_right = value_right - value_width - 10 * scale
            
            label_width = _row_label_width(width, pad, icon_space, value_width, relative_width, scale)
            label = _fit_text(item.name, label_width, row_size)
            _text(label, label_x, row_y + 8 * scale, row_size, label_color)
            _text(relative_time_value, relative_right, row_y + 8 * scale, row_size, relative_time_value_color, right=relative_right )
            _text(value, value_right, row_y + 8 * scale, row_size, value_color, right=value_right)

        footer_top = y + footer_height
        _rect(x, footer_top, width, max(1.0, scale), DIVIDER)

        overall_pb = settings.splits[-1].pb_time if settings.splits else settings.timer_only_pb
        pb_ns = runtime.seconds_to_ns(overall_pb) if overall_pb >= 0 else None
        if settings.show_pb:
            pb_label = f"PB  {format_time(pb_ns, decimals)}" if pb_ns is not None else "PB  —"
            _text(pb_label, x + pad, y + 13 * scale, small_size, MUTED)

        elapsed = runtime.engine.elapsed_ns()
        timer_color = TEXT
        current = runtime.engine.current_index
        if settings.show_pb and runtime.engine.is_active and current < runtime.engine.segment_count:
            target = runtime.comparison_pb_time(current)
            if target >= 0:
                timer_color = GREEN if elapsed <= runtime.seconds_to_ns(target) else RED
        timer_text = format_time(elapsed, decimals)
        timer_y = y + (25 if settings.show_pb else 12) * scale
        _text(timer_text, x + width - pad, timer_y, time_size, timer_color, right=x + width - pad)
    finally:
        gpu.state.blend_set("NONE")


def register() -> None:
    global _draw_handle
    if _draw_handle is None:
        _draw_handle = bpy.types.SpaceView3D.draw_handler_add(_draw_overlay, (), "WINDOW", "POST_PIXEL")


def unregister() -> None:
    global _draw_handle, _shader
    if _draw_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, "WINDOW")
        _draw_handle = None
    _shader = None
    icon_atlas.unload()
