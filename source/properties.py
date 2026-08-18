"""Blender RNA properties used by BlendSplit."""

from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import AddonPreferences, PropertyGroup


def _redraw(_self: object, _context: bpy.types.Context) -> None:
    from . import runtime

    runtime.tag_view3d_redraw()


def _profile_changed(self: object, context: bpy.types.Context) -> None:
    _redraw(self, context)
    owner = getattr(self, "id_data", None)
    settings = owner.blendsplit if owner is not None and hasattr(owner, "blendsplit") else None
    if settings is None and context is not None and context.scene is not None:
        settings = getattr(context.scene, "blendsplit", None)
    if settings is None:
        return
    from . import profiles

    profiles.schedule_autosave(settings)


def _ui_changed(self: object, context: bpy.types.Context) -> None:
    _redraw(self, context)
    owner = getattr(self, "id_data", None)
    settings = owner.blendsplit if owner is not None and hasattr(owner, "blendsplit") else None
    if settings is None and context is not None and context.scene is not None:
        settings = getattr(context.scene, "blendsplit", None)
    if settings is None:
        return
    from . import profiles

    profiles.schedule_ui_autosave(settings)


class BlendSplitSegment(PropertyGroup):
    name: StringProperty(
        name="Name",
        description="Name of this speedrun split",
        default="New Split",
        update=_profile_changed,
    )
    blender_icon: StringProperty(
        name="Split Icon",
        description="Optional Blender icon shown beside this split in the N-panel and viewport overlay",
        default="NONE",
        update=_profile_changed,
    )
    pb_time: FloatProperty(
        name="PB Split Time",
        description="Cumulative personal-best time in seconds; -1 means unset",
        default=-1.0,
        min=-1.0,
        precision=3,
        options={"HIDDEN"},
    )
    best_segment: FloatProperty(
        name="Best Segment",
        description="Best individual segment in seconds; -1 means unset",
        default=-1.0,
        min=-1.0,
        precision=3,
        options={"HIDDEN"},
    )


def _get_overall_pb(self: "BlendSplitSettings") -> float:
    if not self.splits:
        return max(0.0, self.timer_only_pb)
    return max(0.0, self.splits[-1].pb_time)


def _set_overall_pb(self: "BlendSplitSettings", value: float) -> None:
    if self.splits:
        self.splits[-1].pb_time = value if value > 0 else -1.0
    else:
        self.timer_only_pb = value if value > 0 else -1.0
    from . import profiles, runtime

    runtime.tag_view3d_redraw()
    profiles.schedule_autosave(self)


class BlendSplitSettings(PropertyGroup):
    profile_id: StringProperty(
        name="Profile ID",
        description="Stable identifier of the persistent profile linked to this scene",
        default="",
        options={"HIDDEN"},
    )
    profile_revision: IntProperty(
        name="Profile Revision",
        description="Revision of the persistent profile last loaded into this scene",
        default=0,
        min=0,
        options={"HIDDEN"},
    )
    run_title: StringProperty(
        name="Run Title",
        description="Name of the complete speedrun",
        default="Untitled Blender Run",
        update=_profile_changed,
    )
    category: StringProperty(
        name="Category",
        description="Speedrun category, such as Any% or No Add-ons",
        default="Any%",
        update=_profile_changed,
    )
    splits: CollectionProperty(type=BlendSplitSegment)
    active_split_index: IntProperty(default=0, min=0)

    attempts: IntProperty(
        name="Attempts",
        description="Number of runs started; edit this when continuing on another computer",
        default=0,
        min=0,
        update=_profile_changed,
    )
    timer_only_pb: FloatProperty(
        name="Timer-only PB",
        description="Personal-best time for runs without configured splits; -1 means unset",
        default=-1.0,
        min=-1.0,
        precision=3,
        options={"HIDDEN"},
    )
    overall_pb: FloatProperty(
        name="Overall PB",
        description="Overall personal-best time; set to zero to clear",
        subtype="TIME",
        unit="TIME",
        min=0.0,
        get=_get_overall_pb,
        set=_set_overall_pb,
    )

    show_overlay: BoolProperty(
        name="Show Viewport Overlay",
        description="Show the live timer and split list over the 3D Viewport",
        default=True,
        update=_ui_changed,
    )
    show_attempts: BoolProperty(
        name="Show Attempts",
        description="Show the attempt counter in the viewport overlay",
        default=True,
        update=_ui_changed,
    )
    show_pb: BoolProperty(
        name="Show PB Times",
        description="Show personal-best times in the viewport overlay",
        default=True,
        update=_ui_changed,
    )
    show_relative_time: BoolProperty(
        name="Show Relative Time",
        description="Show the difference between the current segment and personal-best in the viewport overlay",
        default=True,
        update=_ui_changed,
    )
    overlay_anchor: EnumProperty(
        name="Anchor",
        description="Viewport corner used to position the overlay",
        items=(
            ("TOP_LEFT", "Top Left", "Anchor overlay to the top left"),
            ("TOP_RIGHT", "Top Right", "Anchor overlay to the top right"),
            ("BOTTOM_LEFT", "Bottom Left", "Anchor overlay to the bottom left"),
            ("BOTTOM_RIGHT", "Bottom Right", "Anchor overlay to the bottom right"),
        ),
        default="TOP_LEFT",
        update=_ui_changed,
    )
    overlay_offset_x: IntProperty(
        name="Horizontal Offset",
        description="Distance from the selected horizontal viewport edge",
        default=18,
        min=0,
        max=2000,
        update=_ui_changed,
    )
    overlay_offset_y: IntProperty(
        name="Vertical Offset",
        description="Distance from the selected vertical viewport edge",
        default=100,
        min=0,
        max=2000,
        update=_ui_changed,
    )
    overlay_scale: FloatProperty(
        name="Scale",
        description="Scale the entire viewport overlay",
        default=1.0,
        min=0.6,
        max=2.5,
        step=5,
        update=_ui_changed,
    )
    overlay_width: IntProperty(
        name="Width",
        description="Overlay width before UI scaling",
        default=285,
        min=220,
        max=420,
        subtype="PIXEL",
        update=_ui_changed,
    )
    background_opacity: FloatProperty(
        name="Background Opacity",
        description="Opacity of the dark viewport overlay background",
        default=0.92,
        min=0.15,
        max=1.0,
        subtype="FACTOR",
        update=_ui_changed,
    )
    visible_splits: IntProperty(
        name="Visible Splits",
        description="Maximum number of split rows visible in the overlay",
        default=8,
        min=3,
        max=20,
        update=_ui_changed,
    )
    decimals: EnumProperty(
        name="Precision",
        description="Number of decimal places shown for times",
        items=(("1", "Tenths", "Show one decimal"), ("2", "Hundredths", "Show two decimals"), ("3", "Milliseconds", "Show three decimals")),
        default="2",
        update=_ui_changed,
    )


class BlendSplitPreferences(AddonPreferences):
    bl_idname = __package__

    confirm_reset: BoolProperty(
        name="Confirm Reset During a Run",
        default=True,
        description="Ask for confirmation before discarding an active attempt",
    )
    auto_load_last_profile: BoolProperty(
        name="Auto-load Last Profile in New Files",
        default=True,
        description="Restore the last active speedrun profile after creating a new Blender file",
    )

    def draw(self, _context: bpy.types.Context) -> None:
        layout = self.layout
        layout.prop(self, "confirm_reset")
        layout.prop(self, "auto_load_last_profile")
        box = layout.box()
        box.label(text="Default Hotkeys")
        box.label(text="Start / Split: Ctrl Shift Alt 1")
        box.label(text="Pause / Resume: Ctrl Shift Alt 2")
        box.label(text="Undo Split: Ctrl Shift Alt 3")
        box.label(text="Skip Split: Ctrl Shift Alt 4")
        box.label(text="Reset: Ctrl Shift Alt 5")
        box.label(text="Toggle Overlay: Ctrl Shift Alt 6")


CLASSES = (
    BlendSplitSegment,
    BlendSplitSettings,
    BlendSplitPreferences,
)


def register() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.blendsplit = PointerProperty(type=BlendSplitSettings)


def unregister() -> None:
    if hasattr(bpy.types.Scene, "blendsplit"):
        del bpy.types.Scene.blendsplit
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
