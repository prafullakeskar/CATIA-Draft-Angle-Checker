"""Draft Angle Checker - CAD Validation Tool

This package provides image processing and analysis tools for validating
draft angles in CAD parts using CATIA draft analysis screenshots.
"""

from src.image_processor import ImageProcessor
from src.analyzer import DraftAnalyzer
from src.report import Report

__version__ = '1.0.0'
__all__ = ['ImageProcessor', 'DraftAnalyzer', 'Report']
