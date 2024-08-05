import os
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QVBoxLayout, QProgressBar
from qgis.core import (
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
    QgsCoordinateReferenceSystem,
    Qgis,
    QgsRasterFileWriter,
    QgsRasterPipe,
    QgsRasterProjector,
    QgsRasterBlock,
    QgsGeometry,
    QgsRectangle,
    QgsCoordinateTransform,
    QgsPointXY,
    QgsRaster
)
from qgis.gui import QgsMessageBar

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'clip_raster_dialog_base.ui'))


class ClipRasterDialog(QDialog, FORM_CLASS):
    def __init__(self, iface, parent=None):
        super(ClipRasterDialog, self).__init__(parent)
        self.setupUi(self)
        self.iface = iface

        # Populate combo boxes with layers
        self.populateLayers()
        # Aggiungi la progress bar
        self.progressBar = QProgressBar(self)
        layout = self.layout()
        layout.addWidget(self.progressBar)

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
        vector_layer = self.cboVectorLayer.currentData()
        raster_layer = self.cboRasterLayer.currentData()
        output_folder = self.txtOutputFolder.text()
        add_to_qgis = self.chkAddToQGIS.isChecked()

        if not vector_layer or not raster_layer or not output_folder:
            self.iface.messageBar().pushMessage("Error", "Please select all required inputs", level=Qgis.Critical)
            return

        # Create output folder if it doesn't exist
        os.makedirs(output_folder, exist_ok=True)

        # Get total number of features for progress bar
        total_features = vector_layer.featureCount()
        self.progressBar.setMaximum(total_features)

        # Iterate over vector features
        features = vector_layer.getFeatures()

        for index, feature in enumerate(features, 1):
            geometry = feature.geometry()

            # Define output path
            output_path = os.path.join(output_folder, f"clip_{feature.id()}.tif")

            # Create the clipped raster
            result = self.clipRaster(raster_layer, geometry, output_path, vector_layer)

            if result:
                self.iface.messageBar().pushMessage("Success", f"Clip completed for feature {index}/{total_features}",
                                                    level=Qgis.Info)
                if add_to_qgis:
                    self.iface.addRasterLayer(output_path, f"Clip_{feature.id()}")
            else:
                self.iface.messageBar().pushMessage("Error", f"Error clipping feature {index}/{total_features}",
                                                    level=Qgis.Critical)

            # Update progress bar
            self.progressBar.setValue(index)

        self.iface.messageBar().pushMessage("Success", "Operation completed", level=Qgis.Success)
        self.close()

    def clipRaster(self, raster_layer, clip_geometry, output_path, vector_layer):
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

        # Compute the output size
        xres = raster_layer.rasterUnitsPerPixelX()
        yres = raster_layer.rasterUnitsPerPixelY()
        cols = int((intersection.xMaximum() - intersection.xMinimum()) / xres)
        rows = int((intersection.yMaximum() - intersection.yMinimum()) / yres)

        # Create output raster
        output_file = QgsRasterFileWriter(output_path)
        output_format = output_file.driverForExtension(os.path.splitext(output_path)[1])

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
            return False

        # Open the output raster for editing
        output_layer = QgsRasterLayer(output_path, "clipped")
        output_provider = output_layer.dataProvider()

        # Prepare the clip geometry
        geom = QgsGeometry(clip_geometry)

        # Create a raster block for each band
        blocks = []
        for band in range(1, output_provider.bandCount() + 1):
            blocks.append(QgsRasterBlock(output_provider.dataType(band), cols, rows))

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

        return True

