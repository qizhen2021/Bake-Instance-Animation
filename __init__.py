bl_info = {
    "name": "Bake Instance Animation (烘焙几何节点实例动画)",
    "author": "ChyiZ_",
    "version": (1, 0, 3),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > BIA",
    "description": "Bake geometry nodes instance animation to keyframe animation(烘焙几何节点实例动画为关键帧动画)",
    "warning": "",
    "doc_url": "",
    "category": "Animation",
}

import bpy
from bpy.props import StringProperty, IntProperty
from bpy.types import Panel, Operator

class BAKE_OT_instance_animation(Operator):
    """Bake geometry nodes instance animation to keyframe animation"""
    bl_idname = "bake.instance_animation"
    bl_label = "Bake Instance Animation"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        # Get addon settings
        settings = context.scene.bake_instance_settings
        
        # Get collection name
        collection_name = settings.collection_name if settings.collection_name else "bake_animation"
        
        # Get frame range
        frame_start = settings.frame_start
        frame_end = settings.frame_end
        
        try:
            # Execute baking
            self.bake_instance_animation(context, collection_name, frame_start, frame_end)
            self.report({'INFO'}, f"Instance animation baking completed! {frame_end - frame_start + 1} frames processed.")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Baking failed: {str(e)}")
            return {'CANCELLED'}
    
    def bake_instance_animation(self, context, collection_name, frame_start, frame_end):
        """Perform instance animation baking"""
        # Get selected objects
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        
        if not selected_objects:
            raise Exception("Please select objects containing geometry nodes instances.")
        
        # Create or get collection
        if collection_name in bpy.data.collections:
            bake_collection = bpy.data.collections[collection_name]
        else:
            bake_collection = bpy.data.collections.new(collection_name)
            context.scene.collection.children.link(bake_collection)
        
        for obj in selected_objects:
            # Find geometry nodes modifier
            geometry_nodes_modifier = None
            for modifier in obj.modifiers:
                if modifier.type == 'NODES' and modifier.node_group:
                    geometry_nodes_modifier = modifier
                    break
            
            if not geometry_nodes_modifier:
                continue
            
            # Use depsgraph to get actual instance data
            depsgraph = context.evaluated_depsgraph_get()
            
            # Iterate all object instances in depsgraph
            instance_count = 0
            copied_objects = []
            instance_data = []
            
            # First process instances
            for object_instance in depsgraph.object_instances:
                # Check if this instance comes from our selected object
                if object_instance.parent and object_instance.parent.original == obj:
                    instance_count += 1
                    
                    # Get the actual geometry data of the instance
                    try:
                        # Use new_from_object to get mesh data
                        mesh_data = bpy.data.meshes.new_from_object(object_instance.object)
                        
                        if mesh_data and len(mesh_data.vertices) > 0:
                            # Create new object
                            new_obj = bpy.data.objects.new(name=f"Instance_{instance_count:03d}", object_data=mesh_data)
                            
                            # Set initial location, rotation, scale
                            new_obj.matrix_world = object_instance.matrix_world
                            
                            # Add to bake collection
                            bake_collection.objects.link(new_obj)
                            copied_objects.append(new_obj)
                            
                            # Store instance data for animation
                            instance_data.append({
                                'object': new_obj,
                                'random_id': object_instance.random_id if hasattr(object_instance, 'random_id') else None,
                                'initial_matrix': object_instance.matrix_world.copy(),
                                'is_instance': True
                            })
                        
                    except Exception as e:
                        print(f"Error copying instance: {e}")
            
            # Then process non-instance geometry
            # Get evaluated object (with all modifiers applied)
            obj_eval = obj.evaluated_get(depsgraph)
            
            try:
                # Use new_from_object to get full mesh data
                mesh_data = bpy.data.meshes.new_from_object(obj_eval)
                
                if mesh_data and len(mesh_data.vertices) > 0:
                    # Create new object
                    new_obj = bpy.data.objects.new(name=f"{obj.name}_Geometry", object_data=mesh_data)
                    
                    # Set location, rotation, scale (use original object's world matrix)
                    new_obj.matrix_world = obj.matrix_world
                    
                    # Add to bake collection
                    bake_collection.objects.link(new_obj)
                    copied_objects.append(new_obj)
                    
                    # Store geometry data for animation
                    instance_data.append({
                        'object': new_obj,
                        'random_id': None,  # Geometry has no random ID
                        'initial_matrix': obj.matrix_world.copy(),
                        'is_instance': False
                    })
                    
            except Exception as e:
                print(f"Error copying geometry: {e}")
            
            if len(copied_objects) == 0:
                continue
            
            # Now create keyframe animation for each copied object
            for frame in range(frame_start, frame_end + 1):
                # Set current frame
                context.scene.frame_set(frame)
                
                # Re-get depsgraph for current frame's instance data
                depsgraph = context.evaluated_depsgraph_get()
                
                # Set keyframes for each copied object
                for instance_info in instance_data:
                    copied_obj = instance_info['object']
                    random_id = instance_info['random_id']
                    is_instance = instance_info['is_instance']
                    
                    if is_instance:
                        # Handle instance object
                        # Find corresponding instance in current frame's depsgraph
                        for object_instance in depsgraph.object_instances:
                            if (object_instance.parent and 
                                object_instance.parent.original == obj and
                                hasattr(object_instance, 'random_id') and
                                object_instance.random_id == random_id):
                                
                                # Set object's location, rotation, scale
                                copied_obj.matrix_world = object_instance.matrix_world
                                
                                # Insert keyframes
                                copied_obj.keyframe_insert(data_path="location", frame=frame)
                                copied_obj.keyframe_insert(data_path="rotation_euler", frame=frame)
                                copied_obj.keyframe_insert(data_path="scale", frame=frame)
                                break
                    else:
                        # Handle geometry object
                        # Get evaluated object for current frame
                        obj_eval = obj.evaluated_get(depsgraph)
                        
                        # Set object's location, rotation, scale
                        copied_obj.matrix_world = obj_eval.matrix_world
                        
                        # Insert keyframes
                        copied_obj.keyframe_insert(data_path="location", frame=frame)
                        copied_obj.keyframe_insert(data_path="rotation_euler", frame=frame)
                        copied_obj.keyframe_insert(data_path="scale", frame=frame)

# Plugin description in English
PLUGIN_DESCRIPTION = (
    "Bake Instance Animation Addon\n"
    "\nThis is a Blender addon for baking instance animation from geometry nodes to traditional keyframe animation.\n"
    "\nMain features:\n"
    "- Instance baking: Convert geometry nodes instances to independent mesh objects\n"
    "- Animation preservation: Keep complete animation information of instances\n"
    "- Collection management: Automatically create a dedicated collection for baked objects\n"
    "- Parameter configuration: Customizable collection name and frame range\n"
    "- User friendly: Simple interface and detailed operation feedback\n"
    "\nFor detailed instructions, please refer to README.md in the addon folder."
)

class BAKE_OT_show_readme(bpy.types.Operator):
    bl_idname = "bake.show_readme"
    bl_label = "Addon Description"
    bl_description = "Show detailed addon description"

    def invoke(self, context, event):
        self.readme_text = PLUGIN_DESCRIPTION
        return context.window_manager.invoke_popup(self, width=800)

    def draw(self, context):
        layout = self.layout
        for line in self.readme_text.splitlines():
            layout.label(text=line)

    def execute(self, context):
        return {'FINISHED'}

class BakeInstanceAnimationPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    def draw(self, context):
        layout = self.layout
        layout.separator()
        row = layout.row(align=True)
        row.operator("wm.url_open", text="Author Homepage", icon='URL').url = "https://space.bilibili.com/309426047?spm_id_from=333.40164.0.0"
        row.operator("bake.show_readme", text="Addon Description", icon='INFO')
        layout.separator()
        layout.label(text="For detailed instructions, please click the button above.", icon='INFO')

class BAKE_PT_node_instance_animation(Panel):
    """Bake Instance Animation Panel"""
    bl_label = "Bake Instance Animation"
    bl_idname = "BAKE_PT_node_instance_animation"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BIA'
    
    def draw(self, context):
        layout = self.layout
        settings = context.scene.bake_instance_settings
        
        # Collection name setting
        box = layout.box()
        box.label(text="Collection Settings", icon='OUTLINER_COLLECTION')
        box.prop(settings, "collection_name", text="Collection Name")
        if not settings.collection_name:
            box.label(text="Default name: bake_animation", icon='INFO')
        
        # Frame range setting
        box = layout.box()
        box.label(text="Frame Range Settings", icon='TIME')
        row = box.row()
        row.prop(settings, "frame_start", text="Start Frame")
        row.prop(settings, "frame_end", text="End Frame")
        
        # Bake button
        layout.separator()
        layout.operator("bake.instance_animation", text="Start Baking", icon='PLAY')

# Addon settings class
class BakeInstanceSettings(bpy.types.PropertyGroup):
    collection_name: StringProperty(
        name="Collection Name",
        description="Collection name for baked objects, leave blank to use default name",
        default=""
    )
    
    frame_start: IntProperty(
        name="Start Frame",
        description="Start frame for baking animation",
        default=1,
        min=-1000000,
        max=1000000,
    )
    
    frame_end: IntProperty(
        name="End Frame",
        description="End frame for baking animation",
        default=250,
        min=-1000000,
        max=1000000,
    )

# Register and unregister functions
classes = [
    BakeInstanceSettings,
    BAKE_OT_instance_animation,
    BAKE_PT_node_instance_animation,
    BAKE_OT_show_readme,
    BakeInstanceAnimationPreferences
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.bake_instance_settings = bpy.props.PointerProperty(type=BakeInstanceSettings)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.bake_instance_settings

if __name__ == "__main__":
    register() 