import cv2
import numpy as np


class fire_detection():
    """
    This class detects fire using a custom algorithm based on color segmentation and contour analysis.

    Args:
    model_path: kept for compatibility with the existing code.
    conf: Minimum confidence to consider detection (not used here).
    """
    def __init__(self, model_path=None, conf=0.85):  # model_path is not used in the custom algorithm
        self.confidence = conf  # Placeholder for compatibility

    def process(self, img, flag=True):
        """
        This function processes the cv2 frame and returns the bounding boxes where fire is detected.
        """
        if not flag:
            return (False, [])

        # Convert the image to HSV color space
        hsv_img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        # Define the fire color range in HSV
        lower_fire = np.array([0, 50, 200])  # Lower HSV bound for fire-like colors
        upper_fire = np.array([35, 255, 255])  # Upper HSV bound for fire-like colors
        
        # Threshold the HSV image to get fire-like colors
        mask = cv2.inRange(hsv_img, lower_fire, upper_fire)
        
        # Optionally clean up the mask using morphological operations
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        
        # Find contours in the mask
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        bb_boxes = []
        for contour in contours:
            area = cv2.contourArea(contour)

            # Filter out small regions based on contour area
            if area > 500:  # Area threshold to filter noise
                x, y, w, h = cv2.boundingRect(contour)
                bb_boxes.append([x, y, x + w, y + h])

        found = len(bb_boxes) > 0
        return (found, bb_boxes)
