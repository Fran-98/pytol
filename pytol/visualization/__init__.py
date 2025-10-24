"""
Visualization module for pytol (requires pyvista).

This module provides 3D visualization capabilities for VTOL VR missions and terrain.
Install with: pip install pytol[viz]
"""

try:
    import pyvista as pv
    PYVISTA_AVAILABLE = True
except ImportError:
    PYVISTA_AVAILABLE = False

if PYVISTA_AVAILABLE:
    from .visualizer import MissionVisualizer, TerrainVisualizer
    
    __all__ = ['MissionVisualizer', 'TerrainVisualizer']
else:
    __all__ = []
    
    def _raise_import_error(*args, **kwargs):
        raise ImportError(
            "Visualization features require pyvista. "
            "Install with: pip install pytol[viz]"
        )
    
    # Create dummy classes that raise helpful errors
    class MissionVisualizer:
        def __init__(self, *args, **kwargs):
            _raise_import_error()
    
    class TerrainVisualizer:
        def __init__(self, *args, **kwargs):
            _raise_import_error()
