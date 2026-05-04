try:
    import cv2
except ImportError as exc:
    raise ImportError(
        'OpenCV is required. Install opencv-python-headless or opencv-python.'
    ) from exc

import numpy as np
from pathlib import Path


class ImageProcessor:
    """Handles image loading and preprocessing for draft analysis."""
    
    def __init__(self, image_source):
        """
        Initialize the image processor.
        
        Args:
            image_source: Path to the image file or image bytes
        """
        self.original_image = None
        self.hsv_image = None

        if isinstance(image_source, (bytes, bytearray)):
            self.load_image_from_bytes(image_source)
        else:
            self.image_path = Path(image_source)
            self.load_image()

    def load_image_from_bytes(self, image_bytes):
        """Load image from raw bytes."""
        image_array = np.frombuffer(image_bytes, np.uint8)
        self.original_image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if self.original_image is None:
            raise ValueError('Failed to decode uploaded image')

        self.hsv_image = cv2.cvtColor(self.original_image, cv2.COLOR_BGR2HSV)

    def load_image(self):
        """Load image from file."""
        if not self.image_path.exists():
            raise FileNotFoundError(f"Image not found: {self.image_path}")
        
        self.original_image = cv2.imread(str(self.image_path))
        if self.original_image is None:
            raise ValueError(f"Failed to load image: {self.image_path}")
        
        # Convert BGR to HSV for better color separation
        self.hsv_image = cv2.cvtColor(self.original_image, cv2.COLOR_BGR2HSV)
    
    def get_original_image(self):
        """Return the original image."""
        return self.original_image
    
    def get_hsv_image(self):
        """Return the HSV color space image."""
        return self.hsv_image
    
    def get_image_shape(self):
        """Return image dimensions (height, width, channels)."""
        if self.original_image is None:
            return None
        return self.original_image.shape
    
    def extract_red_mask(self, lower_hue=0, upper_hue=12, lower_sat=60, upper_sat=255,
                         lower_val=40, upper_val=255):
        """
        Extract red regions from the image.
        
        Args:
            lower_hue: Lower hue threshold for red
            upper_hue: Upper hue threshold for red
            lower_sat: Lower saturation threshold
            upper_sat: Upper saturation threshold
            lower_val: Lower value threshold
            upper_val: Upper value threshold
        
        Returns:
            Binary mask of red regions
        """
        if self.hsv_image is None:
            raise ValueError("HSV image not available")
        
        lower = np.array([lower_hue, lower_sat, lower_val])
        upper = np.array([upper_hue, upper_sat, upper_val])
        mask = cv2.inRange(self.hsv_image, lower, upper)
        
        # Also check for red in the upper hue range (170-180)
        lower2 = np.array([168, lower_sat, lower_val])
        upper2 = np.array([180, upper_sat, upper_val])
        mask2 = cv2.inRange(self.hsv_image, lower2, upper2)
        
        return cv2.bitwise_or(mask, mask2)
    
    def extract_blue_mask(self, lower_hue=90, upper_hue=135, lower_sat=60, upper_sat=255,
                          lower_val=40, upper_val=255):
        """
        Extract blue regions from the image.
        
        Args:
            lower_hue: Lower hue threshold for blue
            upper_hue: Upper hue threshold for blue
            lower_sat: Lower saturation threshold
            upper_sat: Upper saturation threshold
            lower_val: Lower value threshold
            upper_val: Upper value threshold
        
        Returns:
            Binary mask of blue regions
        """
        if self.hsv_image is None:
            raise ValueError("HSV image not available")
        
        lower = np.array([lower_hue, lower_sat, lower_val])
        upper = np.array([upper_hue, upper_sat, upper_val])
        return cv2.inRange(self.hsv_image, lower, upper)
    
    def extract_green_mask(self, lower_hue=35, upper_hue=90, lower_sat=50, upper_sat=255,
                           lower_val=35, upper_val=255):
        """
        Extract green regions from the image.
        
        Args:
            lower_hue: Lower hue threshold for green
            upper_hue: Upper hue threshold for green
            lower_sat: Lower saturation threshold
            upper_sat: Upper saturation threshold
            lower_val: Lower value threshold
            upper_val: Upper value threshold
        
        Returns:
            Binary mask of green regions
        """
        if self.hsv_image is None:
            raise ValueError("HSV image not available")
        
        lower = np.array([lower_hue, lower_sat, lower_val])
        upper = np.array([upper_hue, upper_sat, upper_val])
        return cv2.inRange(self.hsv_image, lower, upper)

    def extract_yellow_mask(self, lower_hue=15, upper_hue=40, lower_sat=80, upper_sat=255,
                            lower_val=120, upper_val=255):
        """
        Extract yellow ROI boundary regions from the image.

        CATIA draft analysis often shows the selected/ROI boundary as a dashed
        yellow line. The saturation/value thresholds are intentionally a little
        loose because CATIA anti-aliases selection lines against the model.
        """
        if self.hsv_image is None:
            raise ValueError("HSV image not available")

        lower = np.array([lower_hue, lower_sat, lower_val])
        upper = np.array([upper_hue, upper_sat, upper_val])
        return cv2.inRange(self.hsv_image, lower, upper)
    
    def apply_morphological_operations(self, mask, kernel_size=5):
        """
        Apply morphological operations to clean up the mask.
        
        Args:
            mask: Binary mask
            kernel_size: Size of the morphological kernel
        
        Returns:
            Cleaned mask
        """
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        return mask
    
    def get_histogram(self):
        """Get color histogram of the image."""
        hist = cv2.calcHist([self.original_image], [0, 1, 2], None, [256, 256, 256],
                            [0, 256, 0, 256, 0, 256])
        return hist

    def get_graphics_viewport_mask(self):
        """Return a mask covering the main CATIA graphics viewport rows."""
        if self.original_image is None:
            raise ValueError("Image not loaded")

        height, width = self.original_image.shape[:2]
        top, bottom = self._detect_graphics_viewport_rows()
        mask = np.zeros((height, width), dtype=np.uint8)
        mask[top:bottom, :] = 255
        return mask
    
    def _fill_largest_boundary(self, boundary_mask, min_area_ratio=0.005):
        """Fill the largest boundary-like contour if it is large enough."""
        image_area = boundary_mask.shape[0] * boundary_mask.shape[1]
        contours, _ = cv2.findContours(boundary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = [contour for contour in contours if cv2.contourArea(contour) >= image_area * min_area_ratio]
        if not contours:
            return None

        largest = max(contours, key=cv2.contourArea)
        mask = np.zeros_like(boundary_mask)
        cv2.drawContours(mask, [largest], -1, 255, thickness=-1)
        return mask

    def _get_yellow_roi_mask(self):
        """Detect ROI enclosed by CATIA's dashed yellow boundary line."""
        yellow_mask = self.extract_yellow_mask()
        yellow_mask = self._remove_window_chrome_from_yellow_mask(yellow_mask)
        if np.count_nonzero(yellow_mask) < 25:
            return None

        # Bridge dash gaps and slightly thicken anti-aliased boundary pixels.
        close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (31, 31))
        dilate_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        boundary_mask = cv2.morphologyEx(yellow_mask, cv2.MORPH_CLOSE, close_kernel, iterations=2)
        boundary_mask = cv2.dilate(boundary_mask, dilate_kernel, iterations=1)

        roi_mask = self._fill_yellow_hull(boundary_mask)
        if roi_mask is not None:
            return roi_mask

        roi_mask = self._fill_best_yellow_component(boundary_mask)
        if roi_mask is not None:
            return roi_mask

        # If the dashed line has gaps too large to become a closed contour,
        # use the convex hull of the yellow boundary pixels as a practical ROI.
        points = cv2.findNonZero(boundary_mask)
        if points is None or len(points) < 10:
            return None

        hull = cv2.convexHull(points)
        hull_area = cv2.contourArea(hull)
        image_area = boundary_mask.shape[0] * boundary_mask.shape[1]
        if hull_area < image_area * 0.005:
            return None

        mask = np.zeros_like(boundary_mask)
        cv2.drawContours(mask, [hull], -1, 255, thickness=-1)
        return mask

    def _remove_window_chrome_from_yellow_mask(self, yellow_mask):
        """Remove CATIA toolbar/status yellow icons from full-window captures."""
        cleaned = yellow_mask.copy()
        height, width = cleaned.shape[:2]
        if height < 300 or width < 300:
            return cleaned

        top, bottom = self._detect_graphics_viewport_rows()
        cleaned[:top, :] = 0
        cleaned[bottom:, :] = 0
        return cleaned

    def _detect_graphics_viewport_rows(self):
        """Find the main colored CATIA graphics viewport rows."""
        height, width = self.original_image.shape[:2]
        hsv = self.hsv_image
        saturation = hsv[:, :, 1]
        value = hsv[:, :, 2]
        color_mask = ((saturation > 45) & (value > 35)).astype(np.uint8)
        row_ratio = color_mask.mean(axis=1)

        segments = self._segments_over_threshold(row_ratio, threshold=0.18, min_length=max(80, height // 5))
        if not segments:
            return 0, height

        top, bottom = max(segments, key=lambda segment: segment[1] - segment[0])
        return max(0, top - 3), min(height, bottom + 3)

    def _segments_over_threshold(self, values, threshold, min_length):
        """Return contiguous index ranges where values stay above a threshold."""
        segments = []
        start = None
        for index, value in enumerate(values):
            if value >= threshold and start is None:
                start = index
            elif value < threshold and start is not None:
                if index - start >= min_length:
                    segments.append((start, index))
                start = None

        if start is not None and len(values) - start >= min_length:
            segments.append((start, len(values)))

        return segments

    def _fill_yellow_hull(self, boundary_mask):
        """Fill the combined hull of dashed yellow ROI pixels."""
        points = cv2.findNonZero(boundary_mask)
        if points is None or len(points) < 20:
            return None

        hull = cv2.convexHull(points)
        hull_area = cv2.contourArea(hull)
        image_area = boundary_mask.shape[0] * boundary_mask.shape[1]
        if hull_area < image_area * 0.01 or hull_area > image_area * 0.75:
            return None

        mask = np.zeros_like(boundary_mask)
        cv2.drawContours(mask, [hull], -1, 255, thickness=-1)
        return mask

    def _fill_best_yellow_component(self, boundary_mask):
        """Fill the best connected yellow boundary component as the ROI."""
        image_area = boundary_mask.shape[0] * boundary_mask.shape[1]
        component_count, labels, stats, _ = cv2.connectedComponentsWithStats(boundary_mask, connectivity=8)
        candidates = []

        for label in range(1, component_count):
            pixel_area = stats[label, cv2.CC_STAT_AREA]
            width = stats[label, cv2.CC_STAT_WIDTH]
            height = stats[label, cv2.CC_STAT_HEIGHT]

            if pixel_area < 25 or width < 8 or height < 8:
                continue

            component_mask = np.uint8(labels == label) * 255
            points = cv2.findNonZero(component_mask)
            if points is None or len(points) < 10:
                continue

            hull = cv2.convexHull(points)
            hull_area = cv2.contourArea(hull)
            if hull_area < image_area * 0.0005 or hull_area > image_area * 0.6:
                continue

            # Prefer broad enclosed selection boundaries over tiny dashed axes,
            # text fragments, or long status-bar highlights.
            fill_ratio = pixel_area / max(hull_area, 1)
            aspect_ratio = width / max(height, 1)
            if fill_ratio > 0.75 or aspect_ratio > 12 or aspect_ratio < 0.08:
                continue

            candidates.append((hull_area, pixel_area, hull))

        if not candidates:
            return None

        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        mask = np.zeros_like(boundary_mask)
        cv2.drawContours(mask, [candidates[0][2]], -1, 255, thickness=-1)
        return mask

    def _get_white_roi_mask(self):
        """Detect ROI using the previous white boundary behavior."""
        gray = cv2.cvtColor(self.original_image, cv2.COLOR_BGR2GRAY)
        _, boundary_mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        return self._fill_largest_boundary(boundary_mask)

    def get_roi_mask(self):
        """
        Detect ROI from the selected CATIA analysis boundary.

        Yellow dashed selection lines are preferred. White boundary detection is
        retained as a fallback for older screenshots.
        
        Returns:
            Binary mask of ROI
        """
        if self.original_image is None:
            raise ValueError("Image not loaded")

        yellow_roi = self._get_yellow_roi_mask()
        if yellow_roi is not None:
            return yellow_roi
        return self._get_white_roi_mask()
