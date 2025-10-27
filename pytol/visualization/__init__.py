"""
Visualization module for pytol.

This module provides both 2D (matplotlib) and 3D (pyvista) visualization capabilities.

2D Visualization (lightweight):
- Install with: pip install pytol[viz-light]
- Provides: Map2DVisualizer, save_mission_map

3D Visualization (interactive):  
- Install with: pip install pytol[viz]
- Provides: MissionVisualizer, TerrainVisualizer
"""

import importlib.util

# Check for matplotlib (2D visualization)
MATPLOTLIB_AVAILABLE = importlib.util.find_spec("matplotlib") is not None

# Check for pyvista (3D visualization) - test actual import
try:
    import pyvista
    PYVISTA_AVAILABLE = True
except ImportError:
    PYVISTA_AVAILABLE = False

# Import available visualizers
__all__ = []

if MATPLOTLIB_AVAILABLE:
    from .map2d import Map2DVisualizer, save_mission_map
    __all__.extend(['Map2DVisualizer', 'save_mission_map'])

if PYVISTA_AVAILABLE:
    from .visualizer import MissionVisualizer, TerrainVisualizer
    __all__.extend(['MissionVisualizer', 'TerrainVisualizer'])

# Create helpful error messages for missing dependencies
if not MATPLOTLIB_AVAILABLE:
    def _raise_matplotlib_error(*args, **kwargs):
        raise ImportError(
            "2D visualization features require matplotlib. "
            "Install with: pip install pytol[viz-light]"
        )
    
    class Map2DVisualizer:
        def __init__(self, *args, **kwargs):
            _raise_matplotlib_error()
    
    def save_mission_map(*args, **kwargs):
        _raise_matplotlib_error()

if not PYVISTA_AVAILABLE:
    def _raise_pyvista_error(*args, **kwargs):
        raise ImportError(
            "3D visualization features require pyvista. "
            "Install with: pip install pytol[viz]"
        )
    
    class MissionVisualizer:
        def __init__(self, *args, **kwargs):
            _raise_pyvista_error()
    
    class TerrainVisualizer:
        def __init__(self, *args, **kwargs):
            _raise_pyvista_error()
