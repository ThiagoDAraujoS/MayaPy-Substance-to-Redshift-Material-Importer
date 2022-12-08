""" This Maya script tool imports Substance Painter textures into maya as redshift materials
    The textures have to follow this schema to be imported correctly "Mesh_{material name}_mat_{texture type}"
    How to use:
        Click the button "Open Folder" and select a folder containing Substance Painter materials.
        Then you may select what material and textures to import.
        When you're done click on Import button.
    Author: Thiago de Araujo Silva
    Date: 2022-12-07
"""

import json
from enum import Enum
from maya import cmds
from os import path, listdir
from functools import partial


class TexType(Enum):
    BaseColor = "diffuse_color"
    Metallic  = "refl_metalness"
    Normal    = "bump_input"
    Roughness = "refl_roughness"
    Emissive  = "emissive_not_implemented"
    Height    = "height_not_implemented"


class MatImporter:
    # Define the file name prefix, suffix, and extensions static constants
    _PREFIX: str = "Mesh_"
    _SUFFIX: str = "_mat"
    _EXTENSIONS: list[str] = ".png", ".bmp", ".jpeg", ".jpg"

    # Define the node connections blueprints' static constants
    _FILE_NODE_SIMPLE_BINDS: list[str] = "coverage", "wrapU", "mirrorU", "mirrorV", "vertexUvOne", "vertexCameraOne", "rotateFrame", "offset", \
                                         "repeatUV", "wrapV", "noiseUV", "stagger", "vertexUvTwo", "translateFrame", "vertexUvThree", "rotateUV"
    _FILE_NODE_UNIQUE_BINDS: list[tuple[str, str]] = ("outUV", "uv"), ("outUvFilterSize", "uvFilterSize")

    def __init__(self) -> None:
        self.loaded_mats = {}
        """ Structure containing all loaded materials """
        self.texture_type_filter = set(TexType)
        """ Filter containing all texture types that will be imported"""

        self.texture_type_filter.remove(TexType.Emissive)  # emissive and height textures aren't implemented in this tool
        self.texture_type_filter.remove(TexType.Height)

    def __str__(self) -> str: return json.dumps(self.loaded_mats, sort_keys=True, indent=4)  # Convert the Loaded data into a json string

    def delete_materials_data(self) -> None: self.loaded_mats = {}  # Delete data saved on _loaded_mats

    def load_materials_data(self, folder_path) -> None:
        """ Load all file names contained in the selected folder, then populate loaded_mats structure with the data found """
        for file in listdir(folder_path):                                                                                                      # For each file in folder
            if file.endswith(MatImporter._EXTENSIONS):                                                                                         # If it has the extensions
                mat_name, tex_name = path.splitext(file)[0].removeprefix(MatImporter._PREFIX).replace(MatImporter._SUFFIX, "").rsplit("_", 1)  # Find the material and texture names from file name
                self.loaded_mats.setdefault(
                    mat_name.capitalize(), [{}, True])[0].setdefault(
                        tex_name, [path.normcase(path.join(folder_path, file)), True])   # Structure files in this schema "mat_dict{mat_name: ({tex_name:(path, tex_import_bool)}, mat_import_bool)}"

    @staticmethod
    def _create_texture_node(name: str, file_name: str, isRaw: bool = False) -> tuple[str, str]:
        """ Create a texture and file nodes, then bind them together """
        node_file = cmds.shadingNode("file", name=f"{name}_file", asTexture=True, isColorManaged=True)    # Create file node
        node_tex = cmds.shadingNode("place2dTexture", name=f"{name}_texture", asUtility=True)             # Create texture node

        for connection in MatImporter._FILE_NODE_SIMPLE_BINDS:                                            # Foreach symmetric connection
            cmds.connectAttr(f"{node_tex}.{connection}", f"{node_file}.{connection}", force=True)           # Connect both nodes
        for connection_a, connection_b in MatImporter._FILE_NODE_UNIQUE_BINDS:                            # Foreach non-symmetric connection
            cmds.connectAttr(f"{node_tex}.{connection_a}", f"{node_file}.{connection_b}")                   # Connect both nodes

        cmds.setAttr(f"{node_file}.fileTextureName", file_name, type="string")                            # Set texture file name
        if isRaw: cmds.setAttr(f"{node_file}.colorSpace", "Raw", type="string")                           # If texture is raw, set its type as raw
        return node_file, node_tex                                                                        # Return nodes names

    def import_loaded_material(self, material_name: str) -> None:
        """ Create Material and bind all its textures to it """
        material_node = cmds.shadingNode("RedshiftMaterial", asShader=True, name=material_name)           # Create the shader node
        cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=f"rsMaterial_{material_node}")  # Bind the shader engine node to it
        cmds.connectAttr(f"{material_node}.outColor", f"rsMaterial_{material_node}.surfaceShader")

        for tex_name, (file, is_import) in self.loaded_mats[material_name][0].items():                    # For each file in material texture dictionary
            if not is_import:                                                                             # Skip if this texture was tagged as no import
                continue

            try: tex_type: TexType = TexType[tex_name]
            except KeyError:                                                                              # Skip this texture if its type is not acknowledged by the tool
                print(f"{tex_name} texture type is not supported\n{material_node}_{tex_name} was not imported\nFile: {file}\n")
                continue

            if tex_type not in self.texture_type_filter:                                                  # Skip if this texture, if it's type was tagged as no import
                continue

            node_file, node_tex = MatImporter._create_texture_node(f"{material_name}_{tex_type.name}", file_name=file, isRaw=tex_type != TexType.BaseColor)  # Create a texture node
            cmds.defaultNavigation(connectToExisting=True, source=node_file, destination=f"{material_node}.{tex_type.value}")  # Connect this node to the material node

            if tex_type == TexType.Normal:                               # If it's a Normal texture
                bump_node = cmds.ls(sl=True)[0]                          # Select the extra bump map node
                cmds.setAttr(f"{bump_node}.inputType", 1)                # Set its input type node

            elif tex_type == TexType.Metallic:                           # If it's a Metallic node
                cmds.setAttr(f"{material_node}.refl_fresnel_mode", 2)    # Set the main mat node fresnel mode to 2

    def import_all_loaded_materials(self) -> None:
        for material_name, (_, is_import) in self.loaded_mats.items():  # For each loaded material
            if not is_import:
                continue
            self.import_loaded_material(material_name)                   # Import that material


class ControlWindow:
    """ This class defines a control window for this tool """

    _NAME: str = "Redshift_Material_Importer"
    _DARK_BGC, _GREEN_BGC, _RED_BGC = (0.2, 0.2, 0.2), (0.2, 0.7, 0.2), (0.215, 0.19, 0.21)
    _singleton_instance = None

    def __init__(self, inspected_tool):
        self._materials_shelf_layout = ""
        """ Material shelf's element path """

        self._texture_shelf_layout = ""
        """ Texture shelf's element path """

        self._main_column_split_layout = ""
        """ Material/Texture split layout element path"""

        self._inspected_folder = ""
        """ Inspected folder's path """

        self.tool = inspected_tool
        """ Inspected tool's reference"""

        self.tool.delete_materials_data()  # refresh importer's data

    def open_window(self) -> None:
        """ Open the window """
        if cmds.window(ControlWindow._NAME, query=True, exists=True):
            cmds.deleteUI(ControlWindow._NAME, window=True)
        self._assemble_window()

    def _open_folder(self, *_) -> None:
        """ Search for a folder path then request the tool to inspect its content """
        folder = cmds.fileDialog2(dialogStyle=2, fm=3)
        if folder:
            self._inspected_folder = folder[0]
            self.tool.load_materials_data(self._inspected_folder)

        self._draw_materials_shelf_layout()

    def _import_selected(self, *_) -> None:
        """ Request the tool to proceed with the import process """
        if self.tool.loaded_mats:
            result = cmds.confirmDialog(title='Import Tool Msg', message='Import selected materials:',
                button=['Yes', 'No'], defaultButton='Yes', cancelButton='No', dismissString='No')

            if result == 'Yes':
                self.tool.import_all_loaded_materials()

    def _assemble_window(self) -> str:
        """ Assemble the window, then show it """

        window_element = cmds.window(ControlWindow._NAME, sizeable=False)
        main_column = cmds.columnLayout(columnAttach=('both', 2), columnWidth=450)

        cmds.button(label="Open File", c=self._open_folder)
        self._draw_texture_import_options_box()
        self._main_column_split_layout = cmds.rowLayout(numberOfColumns=2, columnAttach=[(1, 'left', -2), (2, 'left', -2)])

        cmds.setParent(main_column)
        cmds.button(label="Import", c=self._import_selected)

        cmds.showWindow(window_element)

        return window_element

    def _draw_texture_import_options_box(self) -> str:
        """ Draw the texture type import options box then bind it to the tool """
        def toggle(category, value):            # Toggle texture filter's elements
            if value: self.tool.texture_type_filter.add(category)
            else: self.tool.texture_type_filter.remove(category)

        width_list = [74, 72, 66, 84, 70, 68]   # List of texture type button widths

        cmds.separator(h=6)
        root = cmds.rowLayout(nc=6, columnAttach=[(1, 'left', 0)])
        button_elements = {v: cmds.iconTextCheckBox(st='textOnly', w=w, h=30, l=v.name, bgc=ControlWindow._DARK_BGC, cc=partial(toggle, v), v=True) for w, v in zip(width_list, list(TexType))}

        cmds.iconTextCheckBox(button_elements[TexType.Emissive], e=True, enable=False)  # Disable the non implemented texture types
        cmds.iconTextCheckBox(button_elements[TexType.Height],   e=True, enable=False)

        cmds.setParent("..")    # return to parent element
        cmds.separator(h=2)
        return root             # return root element

    def _draw_materials_shelf_layout(self) -> str:
        """ Draw the material shelf containing all the materials found inside the inspected folder """
        def on_material_toggle_switched(data_reference, state): data_reference[1] = state   # Toggle the material import tag on toggle element pressed
        def on_material_button_pressed(data_reference, selected_button_element, *_):        # Load a new texture set panel for the selected material
            for button_element in button_elements:
                cmds.iconTextCheckBox(button_element, e=True, value=button_element == selected_button_element)
            self._draw_texture_shelf_layout(data_reference[0])

        button_elements = []    # list with loaded material button elements

        self._destroy_materials_shelf_layout()  # Reset the material shelf layout before building a new one

        cmds.setParent(self._main_column_split_layout)
        self._materials_shelf_layout = cmds.scrollLayout(hst=0, vst=8, vsb=True, h=500, w=248, childResizable=True)

        for name, data in self.tool.loaded_mats.items():    # For each material create a [Toggle|Button] element then bind this structure to the tool
            cmds.rowLayout(numberOfColumns=2, columnAttach=[(1, 'left', 1), (2, 'left', 1)])
            cmds.iconTextCheckBox(st='textOnly', w=30, h=30, label=" ", hlc=ControlWindow._GREEN_BGC, bgc=ControlWindow._RED_BGC, cc=partial(on_material_toggle_switched, data), value=data[1])
            button = cmds.iconTextCheckBox(st='textOnly', w=195, h=30, label=name, bgc=ControlWindow._DARK_BGC)
            cmds.iconTextCheckBox(button, e=True, cc=partial(on_material_button_pressed, data, button))
            button_elements.append(button)
            cmds.setParent(self._materials_shelf_layout)

        return self._materials_shelf_layout  # return root

    def _draw_texture_shelf_layout(self, data) -> str:
        def on_texture_selected(data_reference, state): data_reference[1] = state  # Toggle the texture import tag on toggle element pressed

        self._destroy_textures_shelf_layout()

        cmds.setParent(self._main_column_split_layout)
        self._texture_shelf_layout = cmds.scrollLayout(hst=0, vst=8, vsb=True, h=500, w=200, childResizable=True)
        for name, data in data.items():
            cmds.iconTextCheckBox(st='iconAndTextVertical', i1=data[0], l=name, w=80, h=82, cc=partial(on_texture_selected, data), value=data[1])
            cmds.separator(h=2)

        return self._texture_shelf_layout

    def _destroy_materials_shelf_layout(self):
        """ Destroy the material and texture shelf layout element and its children """
        if self._materials_shelf_layout:
            self._destroy_textures_shelf_layout()
            cmds.deleteUI(self._materials_shelf_layout)
            self._materials_shelf_layout = ""

    def _destroy_textures_shelf_layout(self):
        """ Destroy the texture shelf layout element and its children """
        if self._texture_shelf_layout:
            cmds.deleteUI(self._texture_shelf_layout)
            self._texture_shelf_layout = ""


tool = MatImporter()
window = ControlWindow(tool)
window.open_window()

