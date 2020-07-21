# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8-80 compliant>
import bpy
from bpy.types import Operator
import logging

from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
)
from bpy.app.translations import pgettext_data as data_

from bpy_extras import object_utils

def add_torus(major_rad, minor_rad, major_seg, minor_seg, section_angle, section_twist):
    from math import cos, sin, pi
    from mathutils import Vector, Matrix

    pi_2 = pi * 2.0

    twist_step_angle = ((pi_2 / minor_seg) / major_seg) * section_twist
    
    verts = []
    faces = []
    i1 = 0
    tot_verts = major_seg * minor_seg
    for major_index in range(major_seg):
        matrix = Matrix.Rotation((major_index / major_seg) * pi_2, 3, 'Z')
        major_twist_angle = major_index * twist_step_angle
        
        for minor_index in range(minor_seg):
            angle = pi_2 * minor_index / minor_seg + section_angle + major_twist_angle

            vec = matrix @ Vector((
                major_rad + (cos(angle) * minor_rad),
                0.0,
                sin(angle) * minor_rad,
            ))

            verts.extend(vec[:])

            if minor_seg > 2 and minor_index + 1 == minor_seg:
                i2 = (major_index) * minor_seg
                i3 = i1 + minor_seg
                i4 = i2 + minor_seg
            else:
                i2 = i1 + 1
                i3 = i1 + minor_seg
                i4 = i3 + 1

            if i2 >= tot_verts:
                i2 = (i2 - tot_verts + section_twist) % minor_seg
            if i3 >= tot_verts:
                i3 = (i3 - tot_verts + section_twist) % minor_seg
            if i4 >= tot_verts:
                i4 = (i4 - tot_verts + section_twist) % minor_seg
            
            faces.extend([i1, i3, i4, i2])

            i1 += 1

    return verts, faces


def add_uvs(mesh, minor_seg, major_seg):
    from math import fmod

    mesh.uv_layers.new()
    uv_data = mesh.uv_layers.active.data
    polygons = mesh.polygons
    u_step = 1.0 / major_seg
    v_step = 1.0 / minor_seg

    # Round UV's, needed when segments aren't divisible by 4.
    u_init = 0.5 + fmod(0.5, u_step)
    v_init = 0.5 + fmod(0.5, v_step)

    # Calculate wrapping value under 1.0 to prevent
    # float precision errors wrapping at the wrong step.
    u_wrap = 1.0 - (u_step / 2.0)
    v_wrap = 1.0 - (v_step / 2.0)

    vertex_index = 0
    u_prev = u_init
    u_next = u_prev + u_step
    for _major_index in range(major_seg):
        v_prev = v_init
        v_next = v_prev + v_step
        for _minor_index in range(minor_seg):
            loops = polygons[vertex_index].loop_indices
            uv_data[loops[0]].uv = u_prev, v_prev
            uv_data[loops[1]].uv = u_next, v_prev
            uv_data[loops[3]].uv = u_prev, v_next
            uv_data[loops[2]].uv = u_next, v_next
            if v_next > v_wrap:
                v_prev = v_next - 1.0
            else:
                v_prev = v_next
            v_next = v_prev + v_step
            vertex_index += 1
        if u_next > u_wrap:
            u_prev = u_next - 1.0
        else:
            u_prev = u_next
        u_next = u_prev + u_step

def add_uvs_one_ribbon(mesh, minor_seg, major_seg, section_twist):
    from math import fmod
    mesh.uv_layers.new()
    uv_data = mesh.uv_layers.active.data
    polygons = mesh.polygons
    count = major_seg * minor_seg
    u_step = 1.0 / count
    u_next = 0.0
    u_prev = 0.0
    for offset in range(minor_seg):
        off = (offset * section_twist) % minor_seg
        for idx in range(major_seg):
            u_prev = u_next
            u_next = u_prev + u_step 
            loops = polygons[idx * minor_seg + off].loop_indices
            uv_data[loops[0]].uv = u_prev, 0.0
            uv_data[loops[1]].uv = u_next, 0.0
            uv_data[loops[3]].uv = u_prev, 1.0
            uv_data[loops[2]].uv = u_next, 1.0

class AddTorus(Operator, object_utils.AddObjectHelper):
    """Construct a torus mesh"""
    bl_idname = "mesh.primitive_torus_add"
    bl_label = "Add Torus"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}

    def mode_update_callback(self, _context):
        if self.mode == 'EXT_INT':
            self.abso_major_rad = self.major_radius + self.minor_radius
            self.abso_minor_rad = self.major_radius - self.minor_radius

    major_segments: IntProperty(
        name="Major Segments",
        description="Number of segments for the main ring of the torus",
        min=3, max=256,
        default=48,
    )
    minor_segments: IntProperty(
        name="Minor Segments",
        description="Number of segments for the minor ring of the torus",
        min=2, max=256,
        default=12,
    )
    section_angle: FloatProperty(
        name="Section Angle",
        description=("Section Angle"),
        soft_min=0.0, soft_max=360.0,
        min=0.0, max=360.0,
        default=0.0,
        subtype='ANGLE',
        unit='ROTATION',
    )
    section_twist: IntProperty(
        name="Section Twist",
        description="Section Twist",
        min=0, max=256,
        default=0,
    )
    mode: EnumProperty(
        name="Torus Dimensions",
        items=(
            ('MAJOR_MINOR', "Major/Minor",
             "Use the major/minor radii for torus dimensions"),
            ('EXT_INT', "Exterior/Interior",
             "Use the exterior/interior radii for torus dimensions"),
        ),
        update=mode_update_callback,
    )
    major_radius: FloatProperty(
        name="Major Radius",
        description=("Radius from the origin to the "
                     "center of the cross sections"),
        soft_min=0.0, soft_max=100.0,
        min=0.0, max=10_000.0,
        default=1.0,
        subtype='DISTANCE',
        unit='LENGTH',
    )
    minor_radius: FloatProperty(
        name="Minor Radius",
        description="Radius of the torus' cross section",
        soft_min=0.0, soft_max=100.0,
        min=0.0, max=10_000.0,
        default=0.25,
        subtype='DISTANCE',
        unit='LENGTH',
    )
    abso_major_rad: FloatProperty(
        name="Exterior Radius",
        description="Total Exterior Radius of the torus",
        soft_min=0.0, soft_max=100.0,
        min=0.0, max=10_000.0,
        default=1.25,
        subtype='DISTANCE',
        unit='LENGTH',
    )
    abso_minor_rad: FloatProperty(
        name="Interior Radius",
        description="Total Interior Radius of the torus",
        soft_min=0.0, soft_max=100.0,
        min=0.0, max=10_000.0,
        default=0.75,
        subtype='DISTANCE',
        unit='LENGTH',
    )
    generate_uvs: BoolProperty(
        name="Generate UVs",
        description="Generate a default UV map",
        default=True,
    )

    def draw(self, _context):
        layout = self.layout

        col = layout.column(align=True)
        col.prop(self, "generate_uvs")
        col.separator()
        col.prop(self, "align")

        col = layout.column(align=True)
        col.label(text="Location")
        col.prop(self, "location", text="")

        col = layout.column(align=True)
        col.label(text="Rotation")
        col.prop(self, "rotation", text="")

        col = layout.column(align=True)
        col.label(text="Major Segments")
        col.prop(self, "major_segments", text="")

        col = layout.column(align=True)
        col.label(text="Minor Segments")
        col.prop(self, "minor_segments", text="")

        col = layout.column(align=True)
        col.label(text="Section Angle")
        col.prop(self, "section_angle", text="")
        
        col = layout.column(align=True)
        col.label(text="Section Twist")
        col.prop(self, "section_twist", text="")
        
        col = layout.column(align=True)
        col.label(text="Torus Dimensions")
        col.row().prop(self, "mode", expand=True)

        if self.mode == 'MAJOR_MINOR':
            col = layout.column(align=True)
            col.label(text="Major Radius")
            col.prop(self, "major_radius", text="")

            col = layout.column(align=True)
            col.label(text="Minor Radius")
            col.prop(self, "minor_radius", text="")
        else:
            col = layout.column(align=True)
            col.label(text="Exterior Radius")
            col.prop(self, "abso_major_rad", text="")

            col = layout.column(align=True)
            col.label(text="Interior Radius")
            col.prop(self, "abso_minor_rad", text="")

    def invoke(self, context, _event):
        object_utils.object_add_grid_scale_apply_operator(self, context)
        return self.execute(context)

    def execute(self, context):

        if self.mode == 'EXT_INT':
            extra_helper = (self.abso_major_rad - self.abso_minor_rad) * 0.5
            self.major_radius = self.abso_minor_rad + extra_helper
            self.minor_radius = extra_helper

        verts_loc, faces = add_torus(
            self.major_radius,
            self.minor_radius,
            self.major_segments,
            self.minor_segments,
            self.section_angle,
            self.section_twist,
        )

        mesh = bpy.data.meshes.new(data_("Torus"))

        mesh.vertices.add(len(verts_loc) // 3)

        nbr_loops = len(faces)
        nbr_polys = nbr_loops // 4
        mesh.loops.add(nbr_loops)
        mesh.polygons.add(nbr_polys)

        mesh.vertices.foreach_set("co", verts_loc)
        mesh.polygons.foreach_set("loop_start", range(0, nbr_loops, 4))
        mesh.polygons.foreach_set("loop_total", (4,) * nbr_polys)
        mesh.loops.foreach_set("vertex_index", faces)

        if self.generate_uvs:
            if self.section_twist % self.minor_segments == 0:
                add_uvs(mesh, self.minor_segments, self.major_segments)
            else:
                add_uvs_one_ribbon(mesh, self.minor_segments, self.major_segments, self.section_twist)
        
        mesh.update()

        object_utils.object_data_add(context, mesh, operator=self)

        return {'FINISHED'}


classes = (
    AddTorus,
)
