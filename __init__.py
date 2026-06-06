import itertools
import os

import bpy
from bpy.types import Panel,Operator

bl_info = {
    "name": "DaD Armature Renamer",
    "author": "Lagos",
    "version": (0, 0, 1),
    "blender": (5, 0, 0),
    "location": "3D View > Sidebar",
    "description": "Tool to speed up renaming bones of an armature and adding additional new bones for character mods for Dead As Disco.",
    "category": "Object",
}

# Bones that must be set.
REQUIRED_BONES = [
    'pelvis', 'spine_01', 'spine_02', 'spine_03', 'spine_04', 'neck_01',
    'neck_02', 'head',
    'clavicle_l', 'upperarm_l', 'lowerarm_l', 'hand_l', 'thigh_l', 'calf_l',
    'foot_l',
    'clavicle_r', 'upperarm_r', 'lowerarm_r', 'hand_r', 'thigh_r', 'calf_r',
    'foot_r']
 
# Bones which some models will have but which are optional.
OPTIONAL_BONES = {
    'pelvis': ['def_buttock_l', 'def_buttock_r'],
    'upperarm_l': ['upperarm_twist_01_l', 'upperarm_twist_02_l'],
    'lowerarm_l': ['lowerarm_twist_01_l', 'lowerarm_twist_02_l'],
    'hand_l': ['pinky_metacarpal_l'],
    'thigh_l': ['thigh_twist_01_l', 'thigh_twist_02_l', 'thigh_twist_03_l'],
    'calf_l': ['calf_twist_01_l', 'calf_twist_02_l'],
    'foot_l': ['ball_l'],
    'upperarm_r': ['upperarm_twist_01_r', 'upperarm_twist_02_r'],
    'lowerarm_r': ['lowerarm_twist_01_r', 'lowerarm_twist_02_r'],
    'hand_r': ['pinky_metacarpal_r'],
    'thigh_r': ['thigh_twist_01_r', 'thigh_twist_02_r', 'thigh_twist_03_r'],
    'calf_r': ['calf_twist_01_r', 'calf_twist_02_r'],
    'foot_r': ['ball_r']
    }
    
# Finger bones. Optional and permit auto-fill
FINGER_BONES = {
    'hand_l': [['thumb_01_l', 'thumb_02_l', 'thumb_03_l'],
               ['index_01_l', 'index_02_l', 'index_03_l'],
               ['middle_01_l', 'middle_02_l', 'middle_03_l'],
               ['ring_01_l', 'ring_02_l', 'ring_03_l'],
               ['pinky_01_l', 'pinky_02_l', 'pinky_03_l']],
    'hand_r': [['thumb_01_r', 'thumb_02_r', 'thumb_03_r'],
               ['index_01_r', 'index_02_r', 'index_03_r'],
               ['middle_01_r', 'middle_02_r', 'middle_03_r'],
               ['ring_01_r', 'ring_02_r', 'ring_03_r'],
               ['pinky_01_r', 'pinky_02_r', 'pinky_03_r']],
    }
               
 
IK_MAP = {
    'ik_foot_l': 'foot_l',
    'ik_foot_r': 'foot_r',
    'ik_hand_l': 'hand_l',
    'ik_hand_r': 'hand_r',
    'ik_pelvis': 'pelvis',
}

# Bones which most models won't have.
UNLIKELY_BONES = {
    'spine_4': ['def_pectoralis_l', 'def_pectoralis_r', 'def_scapula_l',
                'def_scapula_r', 'm_levator_l', 'm_revator_r'],
    'clavicle_l': ['def_trapezius_l'],
    'upperarm_twist_02_l': ['def_biceps_l'],
    'clavicle_r': ['def_trapezius_r'],
    'upperarm_twist_02_r': ['def_biceps_r'],
}


def flip_name(name: str):
    if name.endswith('_l'):
        return name[:2] + '_r'
    elif name.endswith('_r'):
        return name[:2] + '_l'
    else:
        return name
            

class BoneMapping(bpy.types.PropertyGroup):
    charlie_bone_name: bpy.props.StringProperty(name="charlie_bone_name")
    custom_bone_name: bpy.props.StringProperty(name="custom_bone_name")


class MirrorBonesOperator(Operator):
    """Fills in blanks for some set of names. Will overwrite values."""
    bl_idname = "dad.mirror_bones"
    bl_label = "Mirror Bones"
    bl_info = {'REGISTER', 'UNDO'}

    from_list: bpy.props.StringProperty()

    def execute(self, context):
        # Convert the CollectionProperty to an indexable map.
        bone_mappings = {pg.charlie_bone_name: pg for pg in context.scene.bone_mappings}
        from_list = self.from_list.split(',')

        for src_charlie_bone in from_list:
            dest_charlie_bone = bpy.utils.flip_name(src_charlie_bone)
            src_custom_bone = bone_mappings[src_charlie_bone].custom_bone_name
            
            if not src_custom_bone:  # unset
                continue
            
            dest_custom_bone = bpy.utils.flip_name(src_custom_bone)
            if dest_custom_bone == src_custom_bone:  # Not mirrorable
                continue
            bone_mappings[dest_charlie_bone].custom_bone_name = dest_custom_bone

        return {'FINISHED'}   


class RenameBonesAndUpdateArmature(Operator):
    bl_idname = "dad.update_armature"
    bl_label = "Update Armature"
    bl_info = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        errors = []
        warnings = []
        scene = context.scene
        
        custom_armature = scene.custom_armature
        charlie_armature = scene.charlie_armature
        bone_mappings = scene.bone_mappings
    
        # Step 1: Rename all registered bones appropriately.
        bpy.ops.object.mode_set(mode='OBJECT')
        pose_bones = custom_armature.pose.bones
        
        for bone_map in bone_mappings:
            if not bone_map.custom_bone_name:
                continue
            if bone_map.charlie_bone_name in pose_bones:
                # Do not rename already assigned bones
                continue
            if not bone_map.custom_bone_name in pose_bones:
                print(f"{bone_map.custom_bone_name} not found. Skipping rename for f{bone_map.charlie_bone_name}")
                continue
            pose_bones[bone_map.custom_bone_name].bone.name = bone_map.charlie_bone_name
        
        # Assemble a list of missing bones to be ported
        bones_to_port = []
        for bone_map in bone_mappings:
            if not bone_map.charlie_bone_name in pose_bones:
                bones_to_port.append(bone_map.charlie_bone_name)
        
        # Make a copy of the armature for stealing bones from.
        bpy.ops.object.select_all(action='DESELECT')
        charlie_armature.select_set(True)
        context.view_layer.objects.active = charlie_armature
        bpy.ops.object.duplicate()
        dup_charlie = bpy.context.active_object
        bpy.ops.object.location_clear()
        
        # Enter edit mode and rip out the bones that aren't in the custom armature after 
        bpy.ops.object.mode_set(mode = 'EDIT')
        for bone in dup_charlie.data.edit_bones:
            if bone.name not in custom_armature.data.bones:
                bone.select = True
        bpy.ops.armature.select_all(action='INVERT')
        bpy.ops.armature.delete()
        
        # Join the remaining bones.
        bpy.ops.object.mode_set(mode='OBJECT')
        dup_charlie.select_set(True)
        custom_armature.select_set(True)
        context.view_layer.objects.active = custom_armature
        bpy.ops.object.join()
        
        # Go through all the bones now and make sure the hierarchy fits
        # and bone roll matches.
        # Use Charlie's armature as a reference.
        context.view_layer.objects.active = charlie_armature
        bpy.ops.object.mode_set(mode = 'EDIT')
        context.view_layer.objects.active = custom_armature
        bpy.ops.object.mode_set(mode = 'EDIT')
        bone_parents = {}
        for bone in charlie_armature.data.edit_bones:
            bone_parents[bone.name] = bone.parent.name if bone.parent else None

        edit_bones = custom_armature.data.edit_bones
        for bone_name, parent_name in bone_parents.items():
            if parent_name is None:
                continue
            bone = edit_bones[bone_name]
            parent = edit_bones[parent_name]
            bone.parent = parent

        # Save symmetry setting to restore later.
        old_use_mirror = custom_armature.data.use_mirror_x
        custom_armature.data.use_mirror_x = False

        # Make all bones have the same head-->tail orientation as Charlie's.
        head_tail_deltas = {}
        for bone in charlie_armature.data.edit_bones:
            head_tail_deltas[bone.name] = bone.tail - bone.head
        # Before we move anything, disconnect everything.
        for bone in custom_armature.data.edit_bones:
            bone.use_connect = False
        for bone in custom_armature.data.edit_bones:
            if not bone.name in head_tail_deltas:
                continue
            bone.tail = bone.head + head_tail_deltas[bone.name]

        # Set up bone roll.
        for bone in charlie_armature.data.edit_bones:
            custom_armature.data.edit_bones[bone.name].roll = bone.roll

        # Move IK bones to their corresponding limb bones.
        for ik_bone in IK_MAP:
            bone_to_move = edit_bones[ik_bone]
            bone_target = edit_bones[IK_MAP[ik_bone]]
            bone_to_move.head = bone_target.head
            bone_to_move.tail = bone_target.tail

        
        custom_armature.data.use_mirror_x = old_use_mirror
        return {'FINISHED'}


class DaDRenamePanel(Panel):
    bl_label = "Dead as Disco Armature Retarget"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DaD Mod Tools"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        if not scene.dad_remap_initialized:
            layout.label(text="Bone mappings not found")
            layout.operator(InitializeAddon.bl_idname)
            return

        bone_props = {}  # Dict of 'bone_name'->BoneMapping
        for mapping in scene.bone_mappings:
            bone_props[mapping.charlie_bone_name] = mapping

        box = layout.box()
        box.prop_search(scene, "charlie_armature", bpy.data, "armatures", text="Charlie Armature", icon="ARMATURE_DATA")
        box.prop_search(scene, "custom_armature", bpy.data, "armatures", text="Custom Armature", icon="ARMATURE_DATA")
        box.operator(LoadCharlieOperator.bl_idname, text="Load Charlie Model and Armature")
        
        layout.separator()
        
        # Don't display mappings till we have an armature selected
        if not scene.custom_armature or not scene.charlie_armature:
            return
        custom_armature = scene.custom_armature.data
        layout.label(text="======Required Bones======")
        box = layout.box()
        center_bones = [b for b in REQUIRED_BONES if not b.endswith('_l') and not b.endswith('_r')]
        lhs_bones = [b for b in REQUIRED_BONES if b.endswith('_l')]
        rhs_bones = [b for b in REQUIRED_BONES if b.endswith('_r')]
        
        col = box.column()
        for bone in reversed(center_bones):
            mapping = bone_props[bone]
            col.prop_search(mapping, "custom_bone_name", custom_armature, "bones", text=mapping.charlie_bone_name)
        col.separator()
        row = col.row()
        lhs = row.column()
        for bone in lhs_bones:
            mapping = bone_props[bone]
            lhs.prop_search(mapping, "custom_bone_name", custom_armature, "bones", text=mapping.charlie_bone_name)
        op = lhs.operator(MirrorBonesOperator.bl_idname, text="Mirror names ---->")
        op.from_list = ','.join(lhs_bones)
        
        rhs = row.column()
        for bone in rhs_bones:
            mapping = bone_props[bone]
            rhs.prop_search(mapping, "custom_bone_name", custom_armature, "bones", text=mapping.charlie_bone_name)
        op = rhs.operator(MirrorBonesOperator.bl_idname, text="<---- Mirror names")
        op.from_list = ','.join(rhs_bones)
        layout.separator()
        layout.separator()
        layout.label(text="======Finger Bones======")
        box = layout.box()
        row = box.row()
        lhs = row.column()
        lhs.label(text="Left Hand")
        lhs_bones = []
        for finger in FINGER_BONES['hand_l']:
            # TODO: Could save some time here with fingers by filling them in
            for finger_bone in finger:
                mapping = bone_props[finger_bone]
                lhs.prop_search(mapping, "custom_bone_name", custom_armature, "bones", text=mapping.charlie_bone_name)
                lhs_bones.append(finger_bone)
        op = lhs.operator(MirrorBonesOperator.bl_idname, text="Mirror names ---->")
        op.from_list = ','.join(lhs_bones)
        
        rhs = row.column()
        rhs.label(text="Right Hand")
        rhs_bones = []
        for finger in FINGER_BONES['hand_r']:
            # TODO: Could save some time here with fingers by filling them in
            for finger_bone in finger:
                mapping = bone_props[finger_bone]
                rhs.prop_search(mapping, "custom_bone_name", custom_armature, "bones", text=mapping.charlie_bone_name)
                rhs_bones.append(finger_bone)
        op = rhs.operator(MirrorBonesOperator.bl_idname, text="<---- Mirror names")
        op.from_list = ','.join(rhs_bones)

        layout.separator()
        layout.separator()
        layout.label(text="======Optional Bones======")
        box = layout.box()
        row = box.row()
        
        lhs = row.column()
        lhs_bones = []
        for bone in ['upperarm_l', 'lowerarm_l', 'hand_l', 'thigh_l', 'calf_l', 'foot_l']:
            lhs.label(text="--- " + bone + " ---")
            for bone in OPTIONAL_BONES[bone]:
                mapping = bone_props[bone]
                lhs.prop_search(mapping, "custom_bone_name", custom_armature, "bones", text=mapping.charlie_bone_name)
                lhs_bones.append(bone)
        lhs.label(text='--- pelvis ---')
        mapping = bone_props['def_buttock_l']
        lhs.prop_search(mapping, "custom_bone_name", custom_armature, "bones", text=mapping.charlie_bone_name)
        lhs_bones.append('def_buttock_l')
        op = lhs.operator(MirrorBonesOperator.bl_idname, text="Mirror names ---->")
        op.from_list = ','.join(lhs_bones)
        
        rhs = row.column()
        rhs_bones = []
        for bone in ['upperarm_r', 'lowerarm_r', 'hand_r', 'thigh_r', 'calf_r', 'foot_r']:
            rhs.label(text="--- " + bone + " ---")
            for bone in OPTIONAL_BONES[bone]:
                mapping = bone_props[bone]
                rhs.prop_search(mapping, "custom_bone_name", custom_armature, "bones", text=mapping.charlie_bone_name)
                rhs_bones.append(bone)
        rhs.label(text='--- pelvis ---')
        mapping = bone_props['def_buttock_r']
        rhs.prop_search(mapping, "custom_bone_name", custom_armature, "bones", text=mapping.charlie_bone_name)
        rhs_bones.append('def_buttock_r')
        op = rhs.operator(MirrorBonesOperator.bl_idname, text="<---- Mirror names")
        op.from_list = ','.join(rhs_bones)

        layout.separator()
        layout.separator()
        layout.label(text="=====Unlikely Bones======")
        box = layout.box()
        for parent_bone in UNLIKELY_BONES:  # TODO: Fix this order
            box.label(text="--- " + parent_bone + " ---")
            col = box.column()
            for bone in UNLIKELY_BONES[parent_bone]:
                mapping = bone_props[bone]
                col.prop_search(mapping, "custom_bone_name", custom_armature, "bones", text=mapping.charlie_bone_name)
            layout.separator()
        # Apply the changes
        layout.separator()
        layout.separator()
        box = layout.box()
        op = box.operator(RenameBonesAndUpdateArmature.bl_idname, text="Rename, transfer, and reparent bones")


class LoadCharlieOperator(Operator):
    bl_idname = "dad.load_charlie"
    bl_label = "Load Charlie Armature"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        my_dir = os.path.dirname(os.path.abspath(__file__))
        blend_file = os.path.join(my_dir, "charlie-armature.blend", "Object")
        bpy.ops.wm.append(
            directory=blend_file,
            filename="SK_Charlie_Body_LOD0"
        )

        return {'FINISHED'}


class InitializeAddon(Operator):
    bl_idname = "scene.init_remap_addon"
    bl_label = "Load Addon"

    def execute(self, context):
        scene = context.scene
        bone_names = ['root']
        bone_names.extend(REQUIRED_BONES)
        bone_names.extend(list(itertools.chain.from_iterable(OPTIONAL_BONES.values())))
        bone_names.extend(list(itertools.chain.from_iterable(itertools.chain.from_iterable(FINGER_BONES.values()))))
        bone_names.extend(list(itertools.chain.from_iterable(UNLIKELY_BONES.values())))

        for bone in bone_names:
            if bone in scene.bone_mappings:
                # Don't add new mappings if we're re-registered.
                continue
            map_prop = scene.bone_mappings.add()
            map_prop.charlie_bone_name = bone

        scene.dad_remap_initialized = True
        return {'FINISHED'}


classes = [BoneMapping, MirrorBonesOperator, RenameBonesAndUpdateArmature, DaDRenamePanel, LoadCharlieOperator, InitializeAddon]




def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.dad_remap_initialized = bpy.props.BoolProperty(default=False)
    bpy.types.Scene.charlie_armature = bpy.props.PointerProperty(type=bpy.types.Object)
    bpy.types.Scene.custom_armature = bpy.props.PointerProperty(type=bpy.types.Object)
    
    # Set up space for all the mappings.
    bpy.types.Scene.bone_mappings = bpy.props.CollectionProperty(type=BoneMapping)



def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()