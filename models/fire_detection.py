from ultralytics import YOLO
import cv2
from .config_loader import load_config

class fire_detection():
    """
    this class will be used to detect fire.

    Args:
    model_path: path to model.
    conf: minimum confidence to consider detection.
    
    """
    def __init__(self, config=None):
        if config is None:
            config = load_config()
        self.model = YOLO(config['fire_model'])
        self.confidence = config.get('fire_confidence', 0.85)

    def process(self,img,flag=True):
        """
        this function processes the cv2 frame and returns the
        bounding boxes
        """
        if not flag:
            return (False,[])

        bb_boxes=[]
        result=self.model(img,verbose=False)

        for box in result[0].boxes:
            if(float(box.conf[0])>self.confidence):
                bb=list(map(int,box.xyxy[0]))
                bb_boxes.append(bb)

        if(len(bb_boxes)):
            found=True
        else:
            found=False
        return (found,bb_boxes)