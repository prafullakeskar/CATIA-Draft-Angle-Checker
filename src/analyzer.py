import numpy as np
from src.image_processor import ImageProcessor


class DraftAnalyzer:
    """Analyzes draft angle from CATIA draft analysis images."""
    
    def __init__(self, image_path):
        """
        Initialize the analyzer with an image.
        
        Args:
            image_path: Path to the CATIA draft analysis image
        """
        self.processor = ImageProcessor(image_path)
        self.red_mask = None
        self.green_mask = None
        self.total_pixels = None
        self.red_pixels = None
        self.green_pixels = None
        self.pass_percentage = None
        self.fail_percentage = None
    
    def analyze(self):
        """Perform the draft angle analysis."""
        # Extract color masks
        self.red_mask = self.processor.extract_red_mask()
        self.green_mask = self.processor.extract_green_mask()
        
        # Apply morphological operations to clean up
        self.red_mask = self.processor.apply_morphological_operations(self.red_mask)
        self.green_mask = self.processor.apply_morphological_operations(self.green_mask)
        
        # Calculate statistics
        self._calculate_statistics()
    
    def _calculate_statistics(self):
        """Calculate pass/fail percentages."""
        # Count non-zero pixels
        self.red_pixels = np.count_nonzero(self.red_mask)
        self.green_pixels = np.count_nonzero(self.green_mask)
        
        # Total analyzed pixels (red + green)
        self.total_pixels = self.red_pixels + self.green_pixels
        
        if self.total_pixels == 0:
            self.pass_percentage = 0
            self.fail_percentage = 0
        else:
            self.pass_percentage = (self.green_pixels / self.total_pixels) * 100
            self.fail_percentage = (self.red_pixels / self.total_pixels) * 100
    
    def get_pass_percentage(self):
        """Return the pass percentage."""
        return self.pass_percentage
    
    def get_fail_percentage(self):
        """Return the fail percentage."""
        return self.fail_percentage
    
    def get_pixel_counts(self):
        """Return pixel count statistics."""
        return {
            'pass_pixels': self.green_pixels,
            'fail_pixels': self.red_pixels,
            'total_pixels': self.total_pixels
        }
    
    def get_status(self, pass_threshold=80):
        """
        Determine if the draft angle is acceptable.
        
        Args:
            pass_threshold: Minimum pass percentage required (default: 80%)
        
        Returns:
            str: 'PASS' or 'FAIL'
        """
        if self.pass_percentage is None:
            raise ValueError("Analysis not performed. Call analyze() first.")
        
        return 'PASS' if self.pass_percentage >= pass_threshold else 'FAIL'
    
    def get_red_mask(self):
        """Return the red mask."""
        return self.red_mask
    
    def get_green_mask(self):
        """Return the green mask."""
        return self.green_mask
    
    def get_analysis_summary(self, pass_threshold=80):
        """
        Get a summary of the analysis.
        
        Returns:
            dict: Summary of the analysis results
        """
        return {
            'status': self.get_status(pass_threshold),
            'pass_percentage': round(self.pass_percentage, 2),
            'fail_percentage': round(self.fail_percentage, 2),
            'pass_pixels': self.green_pixels,
            'fail_pixels': self.red_pixels,
            'total_pixels': self.total_pixels,
            'pass_threshold': pass_threshold
        }
