import os
import traceback
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QVBoxLayout, QProgressBar
import os
from qgis.core import (
    QgsRasterBlock,
    QgsGeometry,
    QgsRasterLayer,
    QgsCoordinateTransform,
    QgsProject,
    QgsRasterProjector,
    QgsRasterPipe,
    QgsRasterFileWriter,
    QgsPointXY,
    QgsRaster,
    QgsVectorLayer,
    Qgis


)
from osgeo import gdal
from qgis.gui import QgsMessageBar

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'clip_raster_dialog_base.ui'))
from qgis.PyQt.QtCore import QTimer


class ClipRasterDialog(QDialog, FORM_CLASS):
    def __init__(self, iface, parent=None):
        super(ClipRasterDialog, self).__init__(parent)
        self.setupUi(self)
        self.iface = iface

        # Populate combo boxes with layers
        self.populateLayers()

        # Connect buttons
        self.btnBrowse.clicked.connect(self.browseOutputFolder)
        self.btnOk.clicked.connect(self.runClipRaster)
        self.btnCancel.clicked.connect(self.close)



    def populateLayers(self):
        layers = QgsProject.instance().mapLayers().values()
        for layer in layers:
            if isinstance(layer, QgsVectorLayer):
                self.cboVectorLayer.addItem(layer.name(), layer)
            elif isinstance(layer, QgsRasterLayer):
                self.cboRasterLayer.addItem(layer.name(), layer)

    def browseOutputFolder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.txtOutputFolder.setText(folder)

    def runClipRaster(self):
        self.vector_layer = self.cboVectorLayer.currentData()
        self.raster_layer = self.cboRasterLayer.currentData()
        self.output_folder = self.txtOutputFolder.text()
        self.add_to_qgis = self.chkAddToQGIS.isChecked()

        if not self.vector_layer or not self.raster_layer or not self.output_folder:
            self.iface.messageBar().pushMessage("Error", "Please select all required inputs", level=Qgis.Critical)
            return

        # Create output folder if it doesn't exist
        os.makedirs(self.output_folder, exist_ok=True)

        # Get total number of features for progress bar
        self.total_features = self.vector_layer.featureCount()
        self.progressBar.setMaximum(self.total_features)

        # Initialize feature iterator
        self.feature_iterator = self.vector_layer.getFeatures()
        self.current_feature_index = 0

        # Start processing features
        QTimer.singleShot(0, self.processNextFeature)

    def processNextFeature(self):
        try:
            if self.current_feature_index >= self.total_features:
                self.iface.messageBar().pushMessage("Success", "Operation completed", level=Qgis.Success)
                self.close()
                return

            feature = next(self.feature_iterator)
            geometry = feature.geometry()

            if not geometry or geometry.isEmpty():
                print(f"Empty or invalid geometry for feature {self.current_feature_index + 1}")
                self.current_feature_index += 1
                QTimer.singleShot(0, self.processNextFeature)
                return

            # Define output path
            output_path = os.path.join(self.output_folder, f"clip_{feature.id()}.tif")

            # Create the clipped raster
            result = self.clipRaster(self.raster_layer, geometry, output_path, self.vector_layer)

            if result:
                self.iface.messageBar().pushMessage("Success",
                                                    f"Clip completed for feature {self.current_feature_index + 1}/{self.total_features}",
                                                    level=Qgis.Info)
                if self.add_to_qgis:
                    self.iface.addRasterLayer(output_path, f"Clip_{feature.id()}")
            else:
                self.iface.messageBar().pushMessage("Warning",
                                                    f"Skipping feature {self.current_feature_index + 1}/{self.total_features}",
                                                    level=Qgis.Warning)

            # Update progress bar
            self.progressBar.setValue(self.current_feature_index + 1)

            # Move to next feature
            self.current_feature_index += 1

            # Process next feature
            QTimer.singleShot(0, self.processNextFeature)
        except StopIteration:
            self.iface.messageBar().pushMessage("Success", "Operation completed", level=Qgis.Success)
            self.close()
        except Exception as e:
            self.iface.messageBar().pushMessage("Error", f"Unexpected error: {str(e)}", level=Qgis.Critical)
            print(f"Error details: {traceback.format_exc()}")
            # Continue with the next feature instead of closing
            self.current_feature_index += 1
            QTimer.singleShot(0, self.processNextFeature)

    def clipRaster(self, raster_layer, clip_geometry, output_path, vector_layer):
        try:
            # Get raster data provider
            provider = raster_layer.dataProvider()

            # Get raster extent and CRS
            raster_crs = raster_layer.crs()
            vector_crs = vector_layer.crs()

            # Create a coordinate transform if needed
            if raster_crs != vector_crs:
                transform = QgsCoordinateTransform(vector_crs, raster_crs, QgsProject.instance())
                clip_geometry.transform(transform)

            # Get the bounding box of the clip geometry
            bbox = clip_geometry.boundingBox()

            # Clip the raster extent to the bounding box
            raster_bbox = raster_layer.extent()
            intersection = raster_bbox.intersect(bbox)

            if intersection.isNull() or intersection.isEmpty():
                print(f"No intersection between raster and clip geometry")
                return False
            if intersection.width() <= 0 or intersection.height() <= 0:
                print(f"Invalid intersection: width={intersection.width()}, height={intersection.height()}")
                return False
            # Calculate the resolution for 300 DPI (assuming units are in meters)
            dpi = 300
            inches_per_meter = 39.3701
            pixels_per_meter = dpi * inches_per_meter
            # Calcola la risoluzione basata sul raster di input
            xres = raster_layer.rasterUnitsPerPixelX()
            yres = raster_layer.rasterUnitsPerPixelY()

            # Calcola le dimensioni dell'output
            cols = max(1, int((intersection.xMaximum() - intersection.xMinimum()) / xres))
            rows = max(1, int((intersection.yMaximum() - intersection.yMinimum()) / yres))

            print(f"Output size: {cols}x{rows}")

            if cols * rows > 1000000000:  # Limit to 1 billion pixels to prevent excessive memory usage
                print(f"Output size too large: {cols}x{rows}")
                return False

            # Create output raster
            output_file = QgsRasterFileWriter(output_path)
            output_file.driverForExtension(os.path.splitext(output_path)[1])

            # Set up raster pipe
            pipe = QgsRasterPipe()
            pipe.set(provider.clone())

            # Set up projector if needed
            projector = QgsRasterProjector()
            projector.setCrs(provider.crs(), provider.crs())
            pipe.insert(2, projector)

            # Write raster
            error = output_file.writeRaster(
                pipe,
                cols,
                rows,
                intersection,
                raster_crs
            )

            if error != QgsRasterFileWriter.NoError:
                print(f"Failed to write raster: {error}")
                return False

            # Open the output raster for editing
            output_layer = QgsRasterLayer(output_path, "clipped")
            if not output_layer.isValid():
                print(f"Invalid output layer: {output_path}")
                return False

            output_provider = output_layer.dataProvider()

            # Prepare the clip geometry
            geom = QgsGeometry(clip_geometry)

            # Create a raster block for each band
            blocks = []
            for band in range(1, output_provider.bandCount() + 1):
                block = QgsRasterBlock(output_provider.dataType(band), cols, rows)
                if not block.isValid():
                    print(f"Invalid raster block created for band {band}")
                    return False
                blocks.append(block)

            # Iterate over each pixel in the output raster
            for y in range(rows):
                for x in range(cols):
                    # Get the pixel coordinates in the raster CRS
                    point = QgsPointXY(
                        intersection.xMinimum() + (x + 0.5) * xres,
                        intersection.yMaximum() - (y + 0.5) * yres
                    )

                    # Check if the point is inside the clip geometry
                    if geom.contains(point):
                        # If inside, copy the pixel value from the input raster
                        pixel_value = provider.identify(point, QgsRaster.IdentifyFormatValue).results()
                        for band, block in enumerate(blocks, 1):
                            block.setValue(y, x, pixel_value[band])
                    else:
                        # If outside, set the pixel value to transparent (all bands to 0)
                        for block in blocks:
                            block.setValue(y, x, 0)

            # Write the blocks to the output raster
            for band, block in enumerate(blocks, 1):
                output_provider.writeBlock(block, band, 0, 0)

            # Set the no data value for all bands to 0 (transparent)
            for band in range(1, output_provider.bandCount() + 1):
                output_provider.setNoDataValue(band, 0)

            # Flush the data provider
            output_provider.setEditable(True)
            output_provider.setEditable(False)

            # Compress the output file if it's larger than 5 MB
            if os.path.getsize(output_path) > 5 * 1024 * 1024:
                self.compressRaster(output_path)

            return True
        except Exception as e:
            print(f"Error in clipRaster: {str(e)}")
            print(f"Error details: {traceback.format_exc()}")
            return False

    def compressRaster(self, input_path):
        try:
            # Open the input file
            src_ds = gdal.Open(input_path)

            # Create a temporary file for the compressed output
            temp_path = input_path + "_temp.tif"

            # Create the compressed copy
            driver = gdal.GetDriverByName("GTiff")
            dst_ds = driver.CreateCopy(temp_path, src_ds, 0,
                                       ['COMPRESS=JPEG', 'JPEG_QUALITY=85', 'TILED=YES'])

            # Close the datasets
            src_ds = None
            dst_ds = None

            # Replace the original file with the compressed one
            os.remove(input_path)
            os.rename(temp_path, input_path)
        except Exception as e:
            print(f"Error in compressRaster: {str(e)}")
            print(f"Error details: {traceback.format_exc()}")

