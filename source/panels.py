"""N-panel controls and split editor."""

from __future__ import annotations

import bpy
from bpy.types import Menu, Panel, UIList

from . import profiles, runtime
from .core import RunState, format_time


class BLENDSPLIT_UL_splits(UIList):
    def draw_item(
        self,
        _context: bpy.types.Context,
        layout: bpy.types.UILayout,
        _data: object,
        item: object,
        _icon: int,
        _active_data: object,
        _active_property: str,
        _index: int,
    ) -> None:
        row = layout.row(align=True)
        if item.blender_icon and item.blender_icon != "NONE":
            row.label(text="", icon=item.blender_icon)
        row.prop(item, "name", text="", emboss=False)
        if item.pb_time >= 0:
            row.label(text=format_time(runtime.seconds_to_ns(item.pb_time), 2))


class BLENDSPLIT_MT_profiles(Menu):
    bl_label = "Speedrun Profiles"
    bl_idname = "BLENDSPLIT_MT_profiles"

    def draw(self, _context: bpy.types.Context) -> None:
        layout = self.layout
        saved = profiles.all_profiles()
        if not saved:
            layout.label(text="No Saved Profiles", icon="INFO")
            return
        for profile in saved:
            operator = layout.operator(
                "blendsplit.load_profile",
                text=profile["title"],
                icon="FILE_TICK",
            )
            operator.profile_id = profile["id"]


class BLENDSPLIT_PT_main(Panel):
    bl_label = "BlendSplit v1.3"
    bl_idname = "BLENDSPLIT_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Speedrun"

    def draw(self, _context: bpy.types.Context) -> None:
        pass


class BLENDSPLIT_PT_run(Panel):
    bl_label = "Run"
    bl_parent_id = "BLENDSPLIT_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        settings = runtime.settings_for_context(context)
        engine = runtime.engine

        timer = layout.box()
        timer.scale_y = 1.35
        timer.label(text=format_time(engine.elapsed_ns(), int(settings.decimals)), icon="TIME")
        if engine.is_active and engine.current_index < len(settings.splits):
            timer.label(text=f"Next: {settings.splits[engine.current_index].name}")

        row = layout.row(align=True)
        label = "Start"
        icon = "PLAY"
        if engine.state == RunState.RUNNING:
            label = "Finish" if engine.current_index == engine.segment_count - 1 else "Split"
            icon = "NEXT_KEYFRAME"
        elif engine.state == RunState.FINISHED:
            label = "Start New Run"
        row.operator("blendsplit.start_split", text=label, icon=icon)
        pause_label = "Resume" if engine.state == RunState.PAUSED else "Pause"
        row.operator("blendsplit.pause", text=pause_label, icon="PAUSE")

        row = layout.row(align=True)
        row.operator("blendsplit.undo", text="Undo", icon="LOOP_BACK")
        row.operator("blendsplit.skip", text="Skip", icon="FORWARD")
        row.operator("blendsplit.reset", text="Reset", icon="FILE_REFRESH")

        layout.prop(settings, "show_overlay", toggle=True, icon="OVERLAY")


class BLENDSPLIT_PT_profile(Panel):
    bl_label = "Profile"
    bl_parent_id = "BLENDSPLIT_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        settings = context.scene.blendsplit
        content = layout.column()
        content.enabled = runtime.engine.state in {RunState.IDLE, RunState.FINISHED}

        profile_row = content.row(align=True)
        profile_label = settings.run_title if settings.profile_id else "Choose Profile…"
        profile_row.menu("BLENDSPLIT_MT_profiles", text=profile_label)
        if settings.profile_id:
            profile_row.operator("blendsplit.save_profile", text="", icon="FILE_TICK")
            duplicate = profile_row.operator("blendsplit.save_profile", text="", icon="DUPLICATE")
            duplicate.as_new = True
            profile_row.operator("blendsplit.delete_profile", text="", icon="TRASH")
            content.label(text="Auto-saves attempts, PBs, and edits", icon="CHECKMARK")
        else:
            profile_row.operator("blendsplit.save_profile", text="Create Profile", icon="ADD")
            content.label(text="Current run is stored only in this blend file", icon="INFO")

        content.separator()
        content.label(text="Split Setup Files")
        row = content.row(align=True)
        row.operator("blendsplit.import_list", text="Import Splits…", icon="IMPORT")
        row.operator("blendsplit.export_list", text="Export Splits…", icon="EXPORT")
        content.label(text="Imports or exports setup only, not profiles", icon="INFO")


class BLENDSPLIT_PT_splits(Panel):
    bl_label = "Splits"
    bl_parent_id = "BLENDSPLIT_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        settings = context.scene.blendsplit
        content = layout.column()
        content.enabled = runtime.engine.state in {RunState.IDLE, RunState.FINISHED}
        content.prop(settings, "run_title")
        content.prop(settings, "category")
        content.operator("blendsplit.random_speedrun", icon="QUESTION")

        if not settings.splits:
            box = content.box()
            box.label(text="No splits yet", icon="INFO")
            box.operator("blendsplit.add_starter_splits", icon="ADD")
            return

        row = content.row()
        row.template_list(
            "BLENDSPLIT_UL_splits",
            "",
            settings,
            "splits",
            settings,
            "active_split_index",
            rows=min(7, max(3, len(settings.splits))),
        )
        controls = row.column(align=True)
        controls.operator("blendsplit.add_split", text="", icon="ADD")
        controls.operator("blendsplit.remove_split", text="", icon="REMOVE")
        controls.separator()
        op = controls.operator("blendsplit.move_split", text="", icon="TRIA_UP")
        op.direction = "UP"
        op = controls.operator("blendsplit.move_split", text="", icon="TRIA_DOWN")
        op.direction = "DOWN"

        index = min(settings.active_split_index, len(settings.splits) - 1)
        selected = settings.splits[index]
        details = content.box()
        details.label(text=f"Selected: {selected.name}")
        icon_row = details.row(align=True)
        if selected.blender_icon and selected.blender_icon != "NONE":
            icon_row.label(text="Split Icon", icon=selected.blender_icon)
        else:
            icon_row.label(text="Split Icon", icon="IMAGE_DATA")
        choose_split = icon_row.operator("blendsplit.choose_icon", text="Choose…")
        choose_split.split_index = index

        if runtime.engine.state in {RunState.RUNNING, RunState.PAUSED}:
            layout.label(text="Reset the timer to edit splits", icon="LOCKED")


class BLENDSPLIT_PT_overlay(Panel):
    bl_label = "Overlay"
    bl_parent_id = "BLENDSPLIT_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        settings = runtime.settings_for_context(context)
        layout.prop(settings, "overlay_anchor")
        row = layout.row(align=True)
        row.prop(settings, "overlay_offset_x")
        row.prop(settings, "overlay_offset_y")
        layout.prop(settings, "overlay_scale")
        layout.prop(settings, "overlay_width")
        layout.prop(settings, "background_opacity")
        layout.prop(settings, "visible_splits")
        layout.prop(settings, "decimals")
        layout.separator()
        layout.label(text="Visible Information")
        row = layout.row(align=True)
        row.prop(settings, "show_attempts")
        row.prop(settings, "show_pb")
        layout.prop(settings, "show_relative_time")
        layout.separator()
        layout.operator("blendsplit.reset_ui_settings", icon="FILE_REFRESH")


class BLENDSPLIT_PT_advanced(Panel):
    bl_label = "Advanced"
    bl_parent_id = "BLENDSPLIT_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        settings = context.scene.blendsplit
        column = layout.column()
        column.enabled = runtime.engine.state in {RunState.IDLE, RunState.FINISHED}
        column.prop(settings, "attempts")
        column.prop(settings, "overall_pb")
        column.separator()
        column.operator("blendsplit.clear_pb", text="Clear PB and Best Segments", icon="TRASH")


CLASSES = (
    BLENDSPLIT_UL_splits,
    BLENDSPLIT_MT_profiles,
    BLENDSPLIT_PT_main,
    BLENDSPLIT_PT_run,
    BLENDSPLIT_PT_profile,
    BLENDSPLIT_PT_splits,
    BLENDSPLIT_PT_overlay,
    BLENDSPLIT_PT_advanced,
)


def register() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
