import cv2
import numpy as np
from tensorflow.keras.models import load_model

# Load the model
model = load_model('models\hand_gesture_cnn_model.h5')

# Gesture mapping
gesture_map = {
    0: "Palm",
    1: "L Sign",
    2: "Fist",
    3: "Fist Moved",
    4: "Thumbs Up",
    5: "Index Finger",  # Issue
    6: "OK Sign",       # Safe
    7: "Palm Moved",
    8: "C Shape",
    9: "Thumbs Down"
}

def preprocess_frame(frame):
    """
    Preprocess the input frame for prediction.
    Args:
        frame (np.array): Input frame in BGR format.
    Returns:
        np.array: Preprocessed frame.
    """
    try:
        # Convert frame to grayscale
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        resized_frame = cv2.resize(gray_frame, (64, 64))  # Match model input size
        normalized_frame = resized_frame / 255.0  # Normalize pixel values to [0, 1]
        reshaped_frame = np.reshape(normalized_frame, (1, 64, 64, 1))  # Add batch and channel dimensions
        # Debugging: Save the preprocessed frame for verification
        cv2.imwrite("preprocessed_frame.jpg", (normalized_frame * 255).astype(np.uint8))
        return reshaped_frame
    except Exception as e:
        print(f"Error in preprocess_frame: {e}")
        return None

def alert(frame, flag=True):
    """
    Perform hand gesture detection and return an alert status.
    Args:
        frame (np.array): Input frame.
        flag (bool): If False, skip detection.
    Returns:
        tuple: Processed frame, Boolean indicating alert, and detected gesture.
    """
    if not flag:
        return frame, "safe", {}

    try:
        # Preprocess the frame
        preprocessed_data = preprocess_frame(frame)
        if preprocessed_data is None:
            return frame, "safe", {}

        # Predict gesture
        prediction = model.predict(preprocessed_data)
        gesture_label = np.argmax(prediction)  # Get class with highest probability
        gesture_name = gesture_map[gesture_label]  # Map to gesture name

        # Trigger alert based on gesture
        if gesture_name == "Index Finger":
            return frame, "unsafe", {"gesture": gesture_name}
        elif gesture_name == "OK Sign":
            return frame, "safe", {"gesture": gesture_name}
        else:
            return frame, "safe", {"gesture": "Unknown"}

    except Exception as e:
        print(f"Error in detect_hand_gesture: {e}")
        return frame, "safe", {}
