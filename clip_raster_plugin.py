import os
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProject
from .clip_raster_dialog import ClipRasterDialog

class ClipRasterPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.dialog = None

    def initGui(self):
        icon = QIcon(os.path.join(os.path.dirname(__file__), "icon", "icon.png"))
        self.action = QAction(icon, "Clip Raster by Polygons", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("Clip Raster by Polygons", self.action)

    def unload(self):
        self.iface.removeToolBarIcon(self.action)
        self.iface.removePluginMenu("Clip Raster by Polygons", self.action)
        del self.action

    def run(self):
        self.dialog = ClipRasterDialog(self.iface)
        self.dialog.show()
