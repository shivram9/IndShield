import cv2
import time
import mediapipe as mp

class PoseEmergencyDetector:
    def __init__(self, confidence=0.5):
        self.pose = mp.solutions.pose.Pose(min_detection_confidence=confidence)
        self.alert_triggered = False
        self.start_time = None

    def detect_pose(self, frame):
        image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(image_rgb)
        
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            
            # Extract wrist and shoulder positions
            left_wrist = landmarks[mp.solutions.pose.PoseLandmark.LEFT_WRIST]
            right_wrist = landmarks[mp.solutions.pose.PoseLandmark.RIGHT_WRIST]
            left_shoulder = landmarks[mp.solutions.pose.PoseLandmark.LEFT_SHOULDER]
            right_shoulder = landmarks[mp.solutions.pose.PoseLandmark.RIGHT_SHOULDER]
            
            # Check if both hands are above shoulders
            if left_wrist.y < left_shoulder.y and right_wrist.y < right_shoulder.y:
                if self.start_time is None:
                    self.start_time = time.time()
                
                elapsed_time = time.time() - self.start_time
                if elapsed_time >= 5 and not self.alert_triggered:
                    self.alert_triggered = True
                    return True, frame  # Alert triggered
            else:
                self.start_time = None
                self.alert_triggered = False
        
        return False, frame  # No alert

    def process_frame(self, frame, alert_callback):
        alert, processed_frame = self.detect_pose(frame)
        if alert:
            cv2.putText(processed_frame, "EMERGENCY DETECTED!", (50, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cv2.rectangle(processed_frame, (10, 10), (frame.shape[1]-10, frame.shape[0]-10), (0, 0, 255), 5)
            alert_callback({"frame": processed_frame, "bbox": (10, 10, frame.shape[1]-10, frame.shape[0]-10)})
        return processed_frame
