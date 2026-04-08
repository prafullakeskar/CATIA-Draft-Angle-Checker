import cv2
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
    
    def extract_red_mask(self, lower_hue=0, upper_hue=10, lower_sat=100, upper_sat=255, 
                         lower_val=100, upper_val=255):
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
        lower2 = np.array([170, lower_sat, lower_val])
        upper2 = np.array([180, upper_sat, upper_val])
        mask2 = cv2.inRange(self.hsv_image, lower2, upper2)
        
        return cv2.bitwise_or(mask, mask2)
    
    def extract_green_mask(self, lower_hue=40, upper_hue=80, lower_sat=100, upper_sat=255,
                           lower_val=100, upper_val=255):
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
