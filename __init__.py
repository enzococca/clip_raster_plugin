from .clip_raster_plugin import ClipRasterPlugin

def classFactory(iface):
    return ClipRasterPlugin(iface)
