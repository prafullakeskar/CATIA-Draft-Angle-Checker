import numpy as np
import cv2
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
        self.blue_mask = None
        self.green_mask = None
        self.total_pixels = None
        self.blue_pixels = None
        self.green_pixels = None
        self.pass_percentage = None
        self.fail_percentage = None
    
    def analyze(self):
        """Perform the draft angle analysis."""
        # Extract masks
        self.blue_mask = self.processor.extract_blue_mask()
        self.green_mask = self.processor.extract_green_mask()

        # Apply morphological cleanup
        self.blue_mask = self.processor.apply_morphological_operations(self.blue_mask)
        self.green_mask = self.processor.apply_morphological_operations(self.green_mask)

        # --- ROI MASK ---
        roi_mask = self.processor.get_roi_mask()

        if roi_mask is not None:
            # Apply ROI to both masks
            self.blue_mask = cv2.bitwise_and(self.blue_mask, self.blue_mask, mask=roi_mask)
            self.green_mask = cv2.bitwise_and(self.green_mask, self.green_mask, mask=roi_mask)
        
        # Calculate statistics
        self._calculate_statistics()
    
    def _calculate_statistics(self):
        """Calculate pass/fail percentages."""
        # Count non-zero pixels
        self.blue_pixels = np.count_nonzero(self.blue_mask)
        self.green_pixels = np.count_nonzero(self.green_mask)
        
        # Total analyzed pixels (blue + green)
        self.total_pixels = self.blue_pixels + self.green_pixels
        
        if self.total_pixels == 0:
            self.pass_percentage = 0
            self.fail_percentage = 0
        else:
            self.pass_percentage = (self.green_pixels / self.total_pixels) * 100
            self.fail_percentage = (self.blue_pixels / self.total_pixels) * 100
    
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
            'fail_pixels': self.blue_pixels,
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
    
    def get_blue_mask(self):
        """Return the blue mask."""
        return self.blue_mask
    
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
            'pass_pixels': int(self.green_pixels) if self.green_pixels is not None else 0,
            'fail_pixels': int(self.blue_pixels) if self.blue_pixels is not None else 0,
            'total_pixels': int(self.total_pixels) if self.total_pixels is not None else 0,
            'pass_threshold': pass_threshold
        }

    def get_overlay_image(self):
        """
        Highlight fail regions inside ROI.
        """
        image = self.processor.get_original_image().copy()

        # Highlight blue (fail) regions
        image[self.blue_mask > 0] = [0, 0, 255]

        return image