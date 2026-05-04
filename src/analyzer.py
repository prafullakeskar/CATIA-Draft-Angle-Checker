import numpy as np
import cv2
from src.image_processor import ImageProcessor


class DraftAnalyzer:
    """Analyzes draft angle from CATIA draft analysis images."""
    
    def __init__(self, image_path, use_roi=True, use_graphics_viewport=False):
        """
        Initialize the analyzer with an image.
        
        Args:
            image_path: Path to the CATIA draft analysis image
        """
        self.processor = ImageProcessor(image_path)
        self.use_roi = use_roi
        self.use_graphics_viewport = use_graphics_viewport
        self.blue_mask = None
        self.red_mask = None
        self.fail_mask = None
        self.visual_fail_mask = None
        self.green_mask = None
        self.roi_mask = None
        self.roi_pixels = None
        self.total_pixels = None
        self.blue_pixels = None
        self.red_pixels = None
        self.fail_pixels = None
        self.nok_region_count = None
        self.green_pixels = None
        self.pass_percentage = None
        self.fail_percentage = None
    
    def analyze(self):
        """Perform the draft angle analysis."""
        # Extract masks
        self.blue_mask = self.processor.extract_blue_mask()
        self.red_mask = self.processor.extract_red_mask()
        self.green_mask = self.processor.extract_green_mask()

        # Apply morphological cleanup
        self.blue_mask = self.processor.apply_morphological_operations(self.blue_mask)
        self.red_mask = self.processor.apply_morphological_operations(self.red_mask)
        self.green_mask = self.processor.apply_morphological_operations(self.green_mask)

        self.fail_mask = cv2.bitwise_or(self.blue_mask, self.red_mask)
        self.visual_fail_mask = self.fail_mask.copy()

        # --- ROI MASK ---
        self.roi_mask = self._get_analysis_mask()

        if self.roi_mask is not None:
            # Apply ROI to both masks
            self.blue_mask = cv2.bitwise_and(self.blue_mask, self.blue_mask, mask=self.roi_mask)
            self.red_mask = cv2.bitwise_and(self.red_mask, self.red_mask, mask=self.roi_mask)
            self.fail_mask = cv2.bitwise_and(self.fail_mask, self.fail_mask, mask=self.roi_mask)
            self.green_mask = cv2.bitwise_and(self.green_mask, self.green_mask, mask=self.roi_mask)
            if self.use_graphics_viewport:
                self.visual_fail_mask = cv2.bitwise_and(
                    self.visual_fail_mask,
                    self.visual_fail_mask,
                    mask=self.roi_mask,
                )
        
        # Calculate statistics
        self._calculate_statistics()
    
    def _calculate_statistics(self):
        """Calculate pass/fail percentages."""
        # Count non-zero pixels
        self.blue_pixels = np.count_nonzero(self.blue_mask)
        self.red_pixels = np.count_nonzero(self.red_mask)
        self.fail_pixels = np.count_nonzero(self.fail_mask)
        self.green_pixels = np.count_nonzero(self.green_mask)
        self.roi_pixels = np.count_nonzero(self.roi_mask) if self.roi_mask is not None else 0
        self.nok_region_count = self._count_nok_regions()
        
        # Total analyzed pixels (red/blue fail + green pass)
        self.total_pixels = self.fail_pixels + self.green_pixels
        
        if self.total_pixels == 0:
            self.pass_percentage = 0
            self.fail_percentage = 0
        else:
            self.pass_percentage = (self.green_pixels / self.total_pixels) * 100
            self.fail_percentage = (self.fail_pixels / self.total_pixels) * 100
    
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
            'fail_pixels': self.fail_pixels,
            'blue_fail_pixels': self.blue_pixels,
            'red_fail_pixels': self.red_pixels,
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

    def _count_nok_regions(self):
        """Count meaningful connected NOK regions in the fail mask."""
        if self.fail_mask is None:
            return 0

        highlight_mask = self.visual_fail_mask if self.visual_fail_mask is not None else self.fail_mask

        contours, _ = cv2.findContours(highlight_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_area = max(8, int(highlight_mask.shape[0] * highlight_mask.shape[1] * 0.00002))
        return sum(1 for contour in contours if cv2.contourArea(contour) >= min_area)
    
    def get_blue_mask(self):
        """Return the blue mask."""
        return self.blue_mask

    def get_red_mask(self):
        """Return the red mask."""
        return self.red_mask

    def get_fail_mask(self):
        """Return the combined red/blue fail mask."""
        return self.fail_mask
    
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
            'pass_percentage': float(round(self.pass_percentage, 2)),
            'fail_percentage': float(round(self.fail_percentage, 2)),
            'pass_pixels': int(self.green_pixels) if self.green_pixels is not None else 0,
            'fail_pixels': int(self.fail_pixels) if self.fail_pixels is not None else 0,
            'blue_fail_pixels': int(self.blue_pixels) if self.blue_pixels is not None else 0,
            'red_fail_pixels': int(self.red_pixels) if self.red_pixels is not None else 0,
            'nok_region_count': int(self.nok_region_count) if self.nok_region_count is not None else 0,
            'roi_pixels': int(self.roi_pixels) if self.roi_pixels is not None else 0,
            'analyzed_roi_coverage': self._get_analyzed_roi_coverage(),
            'total_pixels': int(self.total_pixels) if self.total_pixels is not None else 0,
            'pass_threshold': pass_threshold
        }

    def _get_analyzed_roi_coverage(self):
        """Return how much of the detected ROI was classified as pass/fail color."""
        if not self.roi_pixels:
            return 0.0
        return float(round((self.total_pixels / self.roi_pixels) * 100, 2))

    def _get_analysis_mask(self):
        """Return the mask used to limit the pass/fail calculation."""
        if self.use_graphics_viewport:
            return self.processor.get_graphics_viewport_mask()
        if self.use_roi:
            return self.processor.get_roi_mask()
        return None

    def get_overlay_image(self):
        """
        Highlight NOK regions inside ROI.
        """
        image = self.processor.get_original_image().copy()

        if self.fail_mask is None:
            raise ValueError("Analysis not performed. Call analyze() first.")

        # Tint all fail pixels red, then add a bright contour so small NOK
        # regions stay visible on CATIA's colored draft-analysis surface.
        highlight_mask = self.visual_fail_mask if self.visual_fail_mask is not None else self.fail_mask
        red_overlay = image.copy()
        red_overlay[highlight_mask > 0] = [0, 0, 255]
        image = cv2.addWeighted(red_overlay, 0.65, image, 0.35, 0)

        contours, _ = cv2.findContours(highlight_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_area = max(8, int(highlight_mask.shape[0] * highlight_mask.shape[1] * 0.00002))
        nok_contours = [contour for contour in contours if cv2.contourArea(contour) >= min_area]
        if nok_contours:
            cv2.drawContours(image, nok_contours, -1, [0, 255, 255], thickness=2)

        if self.roi_mask is not None:
            roi_contours, _ = cv2.findContours(self.roi_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if roi_contours:
                cv2.drawContours(image, roi_contours, -1, [255, 255, 0], thickness=2)

        return image
