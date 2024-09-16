import cv2
import numpy as np
import pygame
import time
import threading

class fire_detection():
    """
    This class detects fire using a custom algorithm based on color segmentation and contour analysis.
    Includes improved visuals, a delay for fire confirmation, and a background sound alert system.
    """
    def __init__(self, model_path=None, conf=0.85, confirmation_delay=1.0):
        self.confidence = conf  # Placeholder for compatibility
        self.sound_playing = False  # Flag to prevent multiple sound playbacks
        self.fire_detected_time = None  # Time when fire was first detected
        self.confirmation_delay = confirmation_delay  # Delay before confirming fire (in seconds)

    def process(self, img, flag=True):
        """
        This function processes the cv2 frame and returns the bounding boxes where fire is detected.
        Additionally, it plays a sound when fire is detected and draws visual indicators for intensity.
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

                # Calculate fire intensity based on contour area
                intensity = area / (img.shape[0] * img.shape[1]) * 100  # Intensity as percentage of image area
                
                # Set color based on intensity
                if intensity < 1:
                    color = (0, 255, 0)  # Green for small fires
                elif intensity < 5:
                    color = (0, 255, 255)  # Yellow for moderate fires
                else:
                    color = (0, 0, 255)  # Red for large fires

                # Draw the bounding box with color and intensity information
                cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
                cv2.putText(img, f"Intensity: {int(intensity)}%", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        found = len(bb_boxes) > 0

        # Add confirmation delay logic
        current_time = time.time()
        if found:
            if self.fire_detected_time is None:
                self.fire_detected_time = current_time
            elif current_time - self.fire_detected_time >= self.confirmation_delay:
                # Fire has been detected for longer than the confirmation delay, play sound
                if not self.sound_playing:
                    threading.Thread(target=self.play_sound).start()  # Play sound in background
        else:
            self.fire_detected_time = None  # Reset detection timer when no fire is found

        return (found, bb_boxes)

    def play_sound(self):
        """
        Plays a sound alert for 1 minute when fire is detected. Runs in a background thread.
        """
        # Initialize pygame mixer for sound
        pygame.mixer.init()
        pygame.mixer.music.load("E:/SRS/CODES/FINAL YEAR PROJECT/INDUSTRY/IndShield/models/fire_alarm.mp3")
        pygame.mixer.music.play(loops=-1)  # Play the sound in a loop
        
        self.sound_playing = True
        
        # Stop the sound after 1 minute
        time.sleep(15)
        pygame.mixer.music.stop()
        self.sound_playing = False
