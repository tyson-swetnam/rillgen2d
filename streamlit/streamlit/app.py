

import folium
import rasterio
import branca
import os
import subprocess
import shutil
import sys
import PIL
import tarfile
import asyncio
import streamlit as st
from streamlit_autorefresh import st_autorefresh
import matplotlib.pyplot as plt
from rillgen2d import Rillgen2d
from rasterio.plot import show
from matplotlib.figure import Figure
from subprocess import Popen, PIPE, STDOUT
import streamlit.components.v1 as components
from osgeo import gdal, osr
from pathlib import Path
# Threading makes sense here, since C code doesn't have global interpreter lock?
from threading import Thread
from queue import Queue

#st_autorefresh(interval=2000, limit=100, key="fizzbuzzcounter")


class App:
    def __init__(self):
        if "console_log" not in st.session_state:
            st.session_state.console_log = []
        if "hillshade_generated" not in st.session_state:
            st.session_state.hillshade_generated = False
        if "console" not in st.session_state:
            st.session_state.console = Queue()
        if "rillgen2d" not in st.session_state:
            st.session_state.rillgen2d = None
        if "fig1" not in st.session_state:
            st.session_state.fig1 = Figure(figsize=(5, 5), dpi=100)
        if "folium_map" not in st.session_state:
            st.session_state.folium_map = None
        self.map = None
        if self.map:
            st.session_state.folium_map = self.map

        self.initialize_parameter_fields()

    def initialize_parameter_fields(self, force=False):
        """
        Initialize the parameter fields to the correct types
        """
        if 'flagForEquationVar' not in st.session_state or force:
            st.session_state.flagForEquationVar = True
        if 'flagforDynamicModeVar' not in st.session_state or force:
            st.session_state.flagforDynamicModeVar = False
        if 'flagForMaskVar' not in st.session_state or force:
            st.session_state.flagForMaskVar = False
            st.session_state.flagForTaucSoilAndVegVar = False
            st.session_state.flagFord50Var = False
            st.session_state.flagForRockCoverVar = False
            st.session_state.fillIncrementVar = 0.0
            st.session_state.minSlopeVar = 0.0
            st.session_state.expansionVar = 0
            st.session_state.yellowThresholdVar = 0.0
            st.session_state.lattice_size_xVar = 0
            st.session_state.lattice_size_yVar = 0
            st.session_state.deltaXVar = 0.0
            st.session_state.noDataVar = 0
            st.session_state.smoothingLengthVar = 0
            st.session_state.rainVar = 0
            st.session_state.taucSoilAndVegeVar = 0
            st.session_state.d50Var = 0.0
            st.session_state.rockCoverVar = 0
            st.session_state.tanAngleOfInternalFrictionVar = 0.0
            st.session_state.bVar = 0
            st.session_state.cVar = 0.0
            st.session_state.rillWidthVar = 0.0
            st.session_state.show_parameters = False

    def get_parameter_values(self):
        f = open('input.txt', 'r')
        st.session_state.flagForEquationVar = int(f.readline().strip())
        st.session_state.flagforDynamicModeVar = int(f.readline().strip())
        st.session_state.flagForMaskVar = int(f.readline().strip())
        st.session_state.flagForTaucSoilAndVegVar = int(f.readline().strip())
        st.session_state.flagFord50Var = int(f.readline().strip())
        st.session_state.flagForRockCoverVar = int(f.readline().strip())
        st.session_state.fillIncrementVar = float(f.readline().strip())
        st.session_state.minSlopeVar = float(f.readline().strip())
        st.session_state.expansionVar = int(f.readline().strip())
        st.session_state.yellowThresholdVar = float(f.readline().strip())
        # st.session_state.lattice_size_xVar = self.dimensions[1]
        # st.session_state.lattice_size_yVar = self.dimensions[0]
        f.readline()
        f.readline()
        st.session_state.deltaXVar = float(f.readline().strip())
        st.session_state.noDataVar = int(f.readline().strip())
        st.session_state.smoothingLengthVar = int(f.readline().strip())
        st.session_state.rainVar = int(f.readline().strip())
        st.session_state.taucSoilAndVegeVar = int(f.readline().strip())
        st.session_state.d50Var = float(f.readline().strip())
        st.session_state.rockCoverVar = int(f.readline().strip())
        st.session_state.tanAngleOfInternalFrictionVar = float(
            f.readline().strip())
        st.session_state.bVar = int(f.readline().strip())
        st.session_state.cVar = float(f.readline().strip())
        st.session_state.rillWidthVar = float(f.readline().strip())
        st.session_state.show_parameters = True
        f.close()

    def hillshade_and_color_relief(self, filename):
        """Generates the hillshade and color-relief images from the original 
        geotiff image that will be available on the map"""

        st.session_state.console.put(
            "Generating hillshade and color relief...\n")
        cmd0 = "gdaldem hillshade " + filename + " hillshade.png"
        st.session_state.console.put(cmd0)
        st.session_state.console.put(subprocess.check_output(cmd0, shell=True))

    def generate_parameters_button_callback(self):
        imagePath = Path(st.session_state.imagePath)
        self.get_parameter_values()
        self.preview_geotiff(imagePath)
        filename = self.save_image_as_txt(imagePath)
        self.hillshade_and_color_relief(filename)
        st.session_state.hillshade_generated = True

    def getMask(self, filepath):
        # TODO Figure out input for filepath
        if st.session_state.flagForMaskVar == 1:
            st.text(
                ("Choose a mask.tif file\n\n"))
            try:
                maskfile = Path(filepath)
                if maskfile.suffix == '.tar' or maskfile.suffix == '.gz':
                    maskfile = self.extract_geotiff_from_tarfile(
                        maskfile, Path.cwd())

                shutil.copyfile(maskfile, Path.cwd() / "mask.tif")
                (
                    ("maskfile: is: " + str(maskfile) + "\n\n"))
            except Exception:
                (
                    ("Invalid mask.tif file\n\n"))

    def preview_geotiff(self, imagePath):
        """Display the geotiff on the canvas of the first tab"""
        try:
            self.starterimg = rasterio.open(imagePath)
            if imagePath.suffix == '.tif':

                ax = st.session_state.fig1.add_subplot(111)
                ax.set(title="", xticks=[], yticks=[])
                ax.spines["top"].set_visible(False)
                ax.spines["right"].set_visible(False)
                ax.spines["left"].set_visible(False)
                ax.spines["bottom"].set_visible(False)
                st.session_state.fig1.subplots_adjust(
                    bottom=0, right=1, top=1, left=0, wspace=0, hspace=0)
                with self.starterimg as src_plot:
                    show(src_plot, ax=ax)
                plt.close()
                st.session_state.fig1 = st.session_state.fig1
            else:
                st.error(
                    "ERROR: Invalid File Format. Supported files must be in TIFF format")
        except Exception as e:
            st.error("Exception: " + str(e))

    def displayMap(self):
        """Uses the map.html file to generate a folium map using QtWidgets.QWebEngineView()"""
        if Path("map.html").exists():
            mapfile = Path("map.html").resolve().as_posix()
        else:
            ("No map.html file found\n\n")

    def populate_parameters_tab(self):
        """Populate the second tab in the application with tkinter widgets. This tab holds editable parameters
        that will be used to run the rillgen2dwitherode.c script. lattice_size_x and lattice_size_y are read in from the
        geometry of the geotiff file"""

        # Flag for equation variable
        with st.sidebar:
            st.checkbox(
                "Equation",
                value=st.session_state.flagForEquationVar,
                disabled=not st.session_state.show_parameters,
                help="Default: checked,\
                        implements the rock armor shear strength equation of Haws and Erickson (2020),\
                        if checked uses Pelletier et al. (2021) equation",
                key="flagForEquationVar"
            )

            # Flag for dynamic node variable
            st.checkbox(
                "Enable Dynamic Mode",
                value=st.session_state.flagforDynamicModeVar,
                disabled=not st.session_state.show_parameters,
                help='Default: unchecked, Note: when checked uses file "dynamicinput.txt".\
                        File must be provided in the same directory as the rillgen2d.py. When flag is unchecked uses "peak mode" with \
                        spatially uniform rainfall.',
                key="flagforDynamicModeVar"
            )
            # Flag for mask variable
            st.checkbox(
                "Mask",
                value=st.session_state.flagForMaskVar,
                disabled=not st.session_state.show_parameters,
                help='Default: unchecked, If a raster (mask.tif) is provided, the run restricts the model to certain portions of the input DEM\
                        (mask values = 1 means run the model, 0 means ignore these areas).',
                key="flagForMaskVar"
            )
            if st.session_state.flagForMaskVar:
                st.text_input("Path to mask file", key="maskPath")

            # flagForTaucSoilAndVeg variable
            st.checkbox(
                "Tau C soil & veg:",
                value=st.session_state.flagForTaucSoilAndVegVar,
                disabled=not st.session_state.show_parameters,
                help="Default: unchecked, If a raster (taucsoilandveg.txt) is provided the model applies the shear strength of soil and veg, unchecked means a fixed value will be used.",
                key="flagForTaucSoilAndVegVar"
            )
            # Flag for d50 variable
            st.checkbox(
                "d50:",
                value=st.session_state.flagFord50Var,
                disabled=not st.session_state.show_parameters,
                help='Default: unchecked, If a raster (d50.txt) is provided the model applies the median rock diameter, unchecked means a fixed value will be used.',
                key="flagFord50Var"
            )

            # Flag for rockcover
            st.checkbox(
                "Rock Cover:",
                value=st.session_state.flagForRockCoverVar,
                disabled=not st.session_state.show_parameters,
                help="",
                key="flagForRockCoverVar",
            )

            # fillIncrement variable
            st.number_input(
                "Fill increment:",
                value=st.session_state.fillIncrementVar,
                disabled=not st.session_state.show_parameters,
                help="Value in meters (m) used to fill in pits and flats for hydrologic correction. 0.01 m is a reasonable default value for lidar-based DEMs.",
                key="fillIncrementVar"
            )

            # minslope variable
            st.number_input(
                "Min Slope:",
                value=st.session_state.minSlopeVar,
                disabled=not st.session_state.show_parameters,
                help="Value (unitless) used to halt runoff from areas below a threshold slope steepness. Setting this value larger than 0 is useful for eliminating runoff from portions of the landscape that the user expects are too flat to produce significant runoff.",
                key="minSlopeVar"
            )
            # Expansion variable
            st.number_input(
                "Expansion:",
                value=st.session_state.expansionVar,
                disabled=not st.session_state.show_parameters,
                help="Value (pixel) used to expand the zones where rills are predicted in the output raster. This is useful for making the areas where rilling is predicted easier to see in the model output.",
                key="expansionVar"
            )
            # yellowThreshold variable
            st.number_input(
                "Yellow Threshold:",
                value=st.session_state.yellowThresholdVar,
                disabled=not st.session_state.show_parameters,
                help="Threshold value of f used to indicate an area that is close to but less than the threshold for generating rills. The model will visualize any location with a f value between this value and 1 as potentially prone to rill generation (any area with a f value larger than 1 is considered prone to rill generation and is colored red).",
                key='yellowThresholdVar'
            )

            # Lattice_size_x variable
            st.number_input(
                "Lattice Size X:",
                value=st.session_state.lattice_size_xVar,
                disabled=True,
                help="Pixels along the east-west direction in the DEM.",
                key="lattice_size_xVar"
            )
            # Lattice_size_y variable
            st.number_input(
                "Lattice Size Y:",
                value=st.session_state.lattice_size_yVar,
                disabled=True,
                key="lattice_size_yVar",
                help="Pixels along the north-south direction in the DEM.",
            )

            # Deltax variable
            st.number_input(
                "$\Delta$X",
                value=st.session_state.deltaXVar,
                disabled=not st.session_state.show_parameters,
                help="Resolution (meters)  of the DEM and additional optional raster inputs.",
                key="deltaXVar"
            )

            # Nodata variable
            st.number_input(
                "nodata",
                value=st.session_state.noDataVar,
                disabled=not st.session_state.show_parameters,
                help="Elevation less than or equal to the nodata value will be masked.",
                key="noDataVar",
            )

            # Smoothinglength variable
            st.number_input(
                "Smoothing Length",
                value=st.session_state.smoothingLengthVar,
                disabled=not st.session_state.show_parameters,
                help="Length scale (pixels) for smoothing of the slope map. A length of 1 has no smoothing",
                key="smoothingLengthVar"
            )
            # Rain fixed variable
            st.number_input(
                "Rain Fixed",
                value=st.session_state.rainVar,
                disabled=not st.session_state.show_parameters,
                help="Peak rainfall intensity (mm/hr). This value is ignored if flag is checked.",
                key="rainVar"
            )

            # tauc soil and vege fixed variable
            st.number_input(
                "tauc soil and vege fixed",
                value=st.session_state.taucSoilAndVegeVar,
                disabled=not st.session_state.show_parameters,
                help="Threshold shear stress for soil and vegetation.",
                key="taucSoilAndVegeVar"
            )

            # d50 fixed
            st.number_input(
                "d50 Fixed",
                value=st.session_state.d50Var,
                disabled=not st.session_state.show_parameters,
                help="Median rock armor diameter (in mm). This value is ignored if flag for d50 is checked.",
                key="d50Var"
            )

            # Rockcover fixed variable
            st.number_input(
                "Rock Cover",
                value=st.session_state.rockCoverVar,
                disabled=not st.session_state.show_parameters,
                help="This value indicates the fraction of area covered by rock armor. Will be 1 for continuous rock armors, less than one for partial rock cover. This value is ignored if flag for rock cover is checked",
                key="rockCoverVar"
            )
            # tanAngleOfInternalFriction fixed variable
            st.number_input(
                "tanAngleOfInternalFriction",
                value=st.session_state.tanAngleOfInternalFrictionVar,
                disabled=not st.session_state.show_parameters,
                help="Tangent of the angle of internal friction. Values will typically be in the range of 0.5-0.8.",
                key="tanAngleOfInternalFrictionVar"
            )

            # b variable
            st.number_input(
                "b",
                value=st.session_state.bVar,
                disabled=not st.session_state.show_parameters,
                help="This value is the coefficient in the model component that predicts the relationship between runoff and contributing area.",
                key="bVar"
            )
            # c variable
            st.number_input(
                "c",
                value=st.session_state.cVar,
                disabled=not st.session_state.show_parameters,
                help="This value is the exponent in the model component that predicts the relationship between runoff and contributing area.",
                key="cVar"
            )

            # rillWidth variable
            st.number_input(
                "rillWidth",
                value=st.session_state.rillWidthVar,
                disabled=not st.session_state.show_parameters,
                help="The width of rills (in m) as they begin to form. This value is used to localize water flow to a width less than the width of a pixel. For example, if deltax = 1 m and rillwidth = 20 cm then the flow entering each pixel is assumed, for the purposes of rill development, to be localized in a width equal to one fifth of the pixel width.",
                key="rillWidthVar"
            )

            self.parameterButton = st.button(
                'Generate Parameters',
                on_click=self.generate_parameters,
                disabled=not st.session_state.show_parameters,
                key="parameterButton"
            )
            self.goButton = st.button(
                'Run Model',
                disabled=not st.session_state.show_parameters,
                on_click=self.run_callback,
                args=(
                    st.session_state.imagePath,
                    st.session_state.console,
                    st.session_state.flagforDynamicModeVar,
                ),
                key="goButton"
            )

            st.text('NOTE: The hydrologic correction step can take a long time if there are lots of depressions in the input DEM and/or if the'
                    + ' landscape is very steep. RILLGEN2D can be sped up by increasing the value of "fillIncrement" or by performing the hydrologic correction step in a'
                    + ' different program (e.g., ArcGIS or TauDEM) prior to input into RILLGEN2D.')
        # The width of rills (in m) as they begin to form. This value is used to localize water flow to a width less than the width of a pixel.
        # For example, if deltax = 1 m and rillwidth = 20 cm then the flow entering each pixel is assumed, for the purposes of rill development, to be localized in a width equal to one fifth of the pixel width.
        ########################### ^MAIN TAB^ ###########################

    async def check_map_file(self):
        while True:
            if Path("./map.html").exists() or st.session_state.console.empty():
                st.experimental_rerun()
            r = await asyncio.sleep(3)

    def delete_temp_dir(self):
        path = Path.cwd() / "tmp"
        if path.exists():
            shutil.rmtree(path.as_posix())

    def input_change_callback(self):
        self.initialize_parameter_fields(force=True)
        t = Thread(target=self.delete_temp_dir)
        t.start()
        for key in st.session_state:
            if key == "imagePath":
                continue
            del st.session_state[key]
        t.join()
        st.session_state.console_log = []
        st.session_state.console = Queue()
        st.session_state.rillgen2d = None
        st.session_state.fig1 = Figure(figsize=(5, 5), dpi=100)
        st.session_state.folium_map = None

    def save_image_as_txt(self, imagePath):
        """Prepares the geotiff file for the rillgen2D code by getting its dimensions (for the input.txt file) and converting it to
        .txt format"""
        if imagePath == None or imagePath == "":
            st.session_state.console.put(
                "NO FILENAME CHOSEN Please choose a valid file")
        else:
            if Path.cwd().name == "tmp":
                os.chdir("..")

            path = Path.cwd() / "tmp"
            if path.exists():
                shutil.rmtree(path.as_posix())
            Path.mkdir(path)
            filename = str(path / Path(imagePath).name)
            shutil.copyfile(str(imagePath), filename)
            if Path(str(imagePath) + ".aux.xml").exists():
                shutil.copyfile(str(imagePath) + ".aux.xml",
                                str(path / imagePath.stem) + ".aux.xml")
            shutil.copyfile("input.txt", path / "input.txt")
            """This portion compiles the rillgen2d.c file in order to import it as a module"""

            # compile the c file so that it will be useable later
            cmd = "gcc -Wall -shared -fPIC ../rillgen2d.c -o rillgen.so"
            st.session_state.console.put(
                str(subprocess.check_output(cmd, shell=True)))
            for fname in Path.cwd().iterdir():
                if fname.suffix == ".tif":
                    Path(fname).unlink()
            os.chdir(str(path))

            # Open existing dataset
            st.session_state.console.put(("GDAL converting .tif to .txt...\n\n") +
                                         '\n'+"Filename is: " +
                                         (Path(filename).name + "\n\n"))
            self.src_ds = gdal.Open(filename)
            band = self.src_ds.GetRasterBand(1)
            arr = band.ReadAsArray()
            dimensions = [arr.shape[0], arr.shape[1]]
            st.session_state.lattice_size_yVar = dimensions[0]
            st.session_state.lattice_size_xVar = dimensions[1]

            st.session_state.console.put("GEO Tiff successfully converted" +
                                         "\n" + "Parameters Tab now available" +
                                         '\n' + "Click Parameters Tab for next selections\n"
                                         )
            return filename

    def generate_parameters(self):
        """Generate the parameters.txt file using the flags from the second tab"""
        path = Path.cwd() / 'parameters.txt'
        if path.exists():
            Path.unlink(path)
        f = open('parameters.txt', 'w+')
        f.write(str(int(st.session_state.flagForEquationVar)) +
                '\t /* Flag for equation out */ \n')
        f.write(str(int((st.session_state.flagforDynamicModeVar))) +
                '\t /* Flag for dynamicmode out */ \n')
        f.write(str(int(st.session_state.flagForMaskVar)) +
                '\t /* Flag for mask out */ \n')
        f.write(str(int(st.session_state.flagForTaucSoilAndVegVar)) +
                '\t /* Flag for taucsoilandveg out */ \n')
        f.write(str(int(st.session_state.flagFord50Var)) +
                '\t /* Flag for d50 out */ \n')
        f.write(str(int(st.session_state.flagForRockCoverVar)) +
                '\t /* Flag for rockcover out */ \n')
        f.write(str(st.session_state.fillIncrementVar).replace(
            "\n", "") + '\t /* fillIncrement out */ \n')
        f.write(str(st.session_state.minSlopeVar).replace(
            "\n", "") + '\t /* minslope out */ \n')
        f.write(str(st.session_state.expansionVar).replace(
            "\n", "") + '\t /* Expansion out */ \n')
        f.write(str(st.session_state.yellowThresholdVar).replace(
            "\n", "") + '\t /* Yellow threshold out */ \n')
        f.write(str(st.session_state.lattice_size_xVar).replace(
            "\n", "") + '\t /* Lattice Size X out */ \n')
        f.write(str(st.session_state.lattice_size_yVar).replace(
            "\n", "") + '\t /* Lattice Size Y out */ \n')
        f.write(str(st.session_state.deltaXVar).replace(
            "\n", "") + '\t /* Delta X out */ \n')
        f.write(str(st.session_state.noDataVar).replace(
            "\n", "") + '\t /* nodata out */ \n')
        f.write(str(st.session_state.smoothingLengthVar).replace(
            "\n", "") + '\t /* smoothing length out */ \n')
        f.write(str(st.session_state.rainVar).replace(
            "\n", "") + '\t /* Rain out */ \n')
        f.write(str(st.session_state.taucSoilAndVegeVar).replace(
            "\n", "") + '\t /* tauc soil and vege out */ \n')
        f.write(str(st.session_state.d50Var).replace(
            "\n", "") + '\t /* d50 out */ \n')
        f.write(str(st.session_state.rockCoverVar).replace(
            "\n", "") + '\t /* rock cover out */ \n')
        f.write(str(st.session_state.tanAngleOfInternalFrictionVar).replace(
            "\n", "") + '\t /* tangent of the angle of internal friction out*/ \n')
        f.write(str(st.session_state.bVar).replace(
            "\n", "") + '\t /* b out */ \n')
        f.write(str(st.session_state.cVar).replace(
            "\n", "") + '\t /* c out */ \n')
        f.write(str(st.session_state.rillWidthVar).replace(
            "\n", "") + '\t /* rill width out */ \n')
        st.success("Generated parameters.txt\n\n"+'\n'+"Click on Run Model\n")
        f.close()

    def generate_input_txt_file(self):
        """Generate the input.txt file using the flags from the second tab.

        There are then helper functions, the first of which runs the rillgen.c script
        in order to create xy_f.txt and xy_tau.txt (and xy_inciseddepth.txt if st.session_state.flagforDynamicModeVar==1)

        The second helper function then sets the georeferencing information from the original
        geotiff file to xy_f.txt and xy_tau.txt (and xy_inciseddepth.txt if st.session_state.flagforDynamicModeVar==1) in order to generate f.tif and tau.tif"""
        path = Path.cwd() / 'input.txt'
        if path.exists():
            Path.unlink(path)
        path = Path.cwd()
        f = open('input.txt', 'w')
        f.write(str(int(st.session_state.flagForEquationVar)) + '\n')
        f.write(str(int(st.session_state.flagforDynamicModeVar)) + '\n')
        if (path / "dynamicinput.txt").exists():
            Path.unlink(path / "dynamicinput.txt")
        if st.session_state.flagforDynamicModeVar == 1:
            if (path.parent / "dynamicinput.txt").exists():
                shutil.copyfile(path.parent / "dynamicinput.txt",
                                path / "dynamicinput.txt")
                st.session_state.console.put(
                    ("dynamicinput.txt found and copied to inner directory\n\n"))
            else:
                st.session_state.console.put(
                    ("dynamicinput.txt not found\n\n"))

        f.write(str(int(st.session_state.flagForMaskVar))+'\n')
        if st.session_state.flagForMaskVar == 1:
            if (path / "mask.tif").exists():
                self.convert_geotiff_to_txt("mask")
                st.session_state.console.put(("mask.txt generated\n\n"))
            else:
                st.session_state.console.put("mask.tif not found\n")
                st.session_state.flagForMaskVar = 0

        f.write(str(int(st.session_state.flagForTaucSoilAndVegVar))+'\n')
        if (path / "taucsoilandvegfixed.txt").exists():
            Path.unlink(path / "taucsoilandvegfixed.txt")
        if int(st.session_state.flagForTaucSoilAndVegVar) == 1:
            if (path.parent / "taucsoilandvegfixed.txt").exists():
                shutil.copyfile(
                    path.parent / "taucsoilandvegfixed.txt", path / "taucsoilandvegfixed.txt")
                st.session_state.console.put(
                    ("taucsoilandvegfixed.txt found and copied to inner directory\n\n"))
            else:
                st.session_state.console.put(
                    ("taucsoilandvegfixed.txt not found\n"))
        f.write(str(int(st.session_state.flagFord50Var))+'\n')
        if (path / "d50.txt").exists():
            Path.unlink(path / "d50.txt")
        if int(st.session_state.flagFord50Var) == 1:
            if (path.parent / "d50.txt").exists():
                shutil.copyfile(path.parent / "d50.txt", path / "d50.txt")
                st.session_state.console.put(
                    ("d50.txt found and copied to inner directory\n\n"))
            else:
                st.session_state.console.put(
                    ("d50.txt not found\n\n"))
        f.write(str(int(st.session_state.flagForRockCoverVar))+'\n')
        if (path / "rockcover.txt").exists():
            path.unlink(path / "rockcover.txt")
        if int(st.session_state.flagForRockCoverVar) == 1:
            if (path.parent / "rockcover.txt").exists():
                shutil.copyfile(path.parent / "rockcover.txt",
                                path / "rockcover.txt")
                st.session_state.console.put(
                    ("rockcover.txt found and copied to inner directory\n\n"))
            else:
                st.session_state.console.put(
                    ("rockcover.txt not found\n\n"))
        f.write(str(st.session_state.fillIncrementVar)+'\n')
        f.write(str(st.session_state.minSlopeVar)+'\n')
        f.write(str(st.session_state.expansionVar)+'\n')
        f.write(str(st.session_state.yellowThresholdVar)+'\n')
        f.write(str(st.session_state.lattice_size_xVar)+'\n')
        f.write(str(st.session_state.lattice_size_yVar)+'\n')
        f.write(str(st.session_state.deltaXVar)+'\n')
        f.write(str(st.session_state.noDataVar)+'\n')
        f.write(str(st.session_state.smoothingLengthVar)+'\n')
        f.write(str(st.session_state.rainVar)+'\n')
        f.write(str(st.session_state.taucSoilAndVegeVar)+'\n')
        f.write(str(st.session_state.d50Var)+'\n')
        f.write(str(st.session_state.rockCoverVar)+'\n')
        f.write(str(st.session_state.tanAngleOfInternalFrictionVar)+'\n')
        f.write(str(st.session_state.bVar)+'\n')
        f.write(str(st.session_state.cVar)+'\n')
        f.write(str(st.session_state.rillWidthVar)+'\n')
        st.session_state.console.put(("Generated input.txt\n"))
        f.close()

    def run_callback(self, imagePath, console, flagForDyanmicModeVar):
        self.generate_input_txt_file()
        if st.session_state.flagForMaskVar:
            self.getMask()
        if st.session_state.rillgen2d is None or not st.session_state.rillgen2d.is_alive():

            st.session_state.rillgen2d = Thread(
                target=self.run_rillgen, args=(imagePath, console, flagForDyanmicModeVar))
            st.session_state.rillgen2d.start()

    def run_rillgen(self, imagePath, console, flagForDyanmicModeVar):

        rillgen = Rillgen2d(
            imagePath,
            console,
            flagForDyanmicModeVar
        )
        rillgen.convert_geotiff_to_txt(Path(imagePath).stem)
        t1 = Thread(target=rillgen.generate_colorramp,
                    args=(rillgen.filename, 1))
        t1.start()
        rillgen.setup_rillgen()
        t1.join()
        rillgen.set_georeferencing_information()

        self.map = rillgen.populate_view_output_tab()


app = App()
st.title("Rillgen2d")


app_tab, console, readme = st.tabs(["Rillgen2d App", "Console", "Readme"])
while not st.session_state.console.empty():
    st.session_state.console_log.append(st.session_state.console.get())
with st.sidebar:
    st.header("Parameters")
    st.text_input(
        "Image Path",
        key="imagePath",
        value="/Users/elliothagyard/Downloads/output2.tif",
        on_change=app.input_change_callback
    )
    # If I switch to the file upload look at this for rasterio docs on in memoroy files: https://rasterio.readthedocs.io/en/latest/topics/memory-files.html
    generate_parameters_button = st.button(
        "Generate Parameters",
        on_click=app.generate_parameters_button_callback,
        key="genParameter")
    app.populate_parameters_tab()

    #   st.text_input(label, value="",
    #   max_chars=None, key=None, type="default",
    #   help=None, autocomplete=None, on_change=None,
    #   args=None, kwargs=None, *, placeholder=None, disabled=False, label_visibility="visible")
with app_tab:
    if st.session_state.hillshade_generated:
        with st.expander("Preview"):
            _, center, _, _ = st.columns(4)
            with center:
                st.image(PIL.Image.open(r"./hillshade.png"), width=500)
    if Path("./map.html").exists():
        components.html(Path("./map.html").read_text(), height=600)
    if app.map:
        st.session_state.folium_map = app.map
        print("here")

with console:
    for line in st.session_state.console_log:
        st.write(line)
