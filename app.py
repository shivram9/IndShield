import os
import cv2
import base64
import threading
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, Response, request, redirect, flash, jsonify, session
import requests
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from playsound import playsound
from dotenv import load_dotenv
from twilio.rest import Client

# Load environment variables
load_dotenv()

# Logging configuration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.FileHandler("error.log"),
        logging.StreamHandler()
    ]
)

# Twilio client setup
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
client = Client(account_sid, auth_token)

# Import detection models
from models.r_zone import people_detection
from models.fire_detection import fire_detection
from models.gear_detection import gear_detection
from models.pose_detection import PoseEmergencyDetector
from models.motion_amp import amp


# Flask app configuration
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///user.db'
app.config["SQLALCHEMY_BINDS"] = {
    "complaint": "sqlite:///complaint.db",
    "cams": "sqlite:///cams.db",
    "alerts": "sqlite:///alerts.db"
}
app.config['UPLOAD_FOLDER'] = 'uploads'
ALLOWED_EXTENSIONS = {"mp4"}

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Database models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)  # increased length for hashed passwords
    email = db.Column(db.String(100), unique=True, nullable=False)

class Camera(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    Cam_id = db.Column(db.String(100))
    fire_detection = db.Column(db.Boolean, default=False)
    pose_alert = db.Column(db.Boolean, default=False)
    restricted_zone = db.Column(db.Boolean, default=False)
    safety_gear_detection = db.Column(db.Boolean, default=False)
    region = db.Column(db.Boolean, default=False)

class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date_time = db.Column(db.DateTime)
    alert_type = db.Column(db.String(50))
    frame_snapshot = db.Column(db.LargeBinary)

class complaint(db.Model):
    __bind_key__ = 'complaint'  # Ensure it's connected to the right database
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    full_name = db.Column(db.String(100))
    email = db.Column(db.String(100))
    alert_type = db.Column(db.String(50))
    description = db.Column(db.Text)
    file_data = db.Column(db.LargeBinary)

# Initialize detection models
r_zone = people_detection("models/yolov8n.pt")
fire_det = fire_detection("models/fire.pt", conf=0.60)
gear_det = gear_detection("models/gear.pt")
pose_detector = PoseEmergencyDetector()

# Helper function to check file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Play alert sound
def play_alert_sound():
    try:
        for _ in range(3):
            playsound(os.path.join('static', 'sounds', 'alert.mp3'))
        logging.info("Alert sound played successfully.")
    except Exception as e:
        logging.error(f"Error playing alert sound: {str(e)}")

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login_page')
def login_page():
    return render_template("login.html")

@app.route('/register_page')
def register_page():
    return render_template("register.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password_input = request.form['password']

        if not email or not password_input:
            flash('Email or Password Missing!!')
            return redirect('/login')

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password_input):
            login_user(user)
            logging.info(f"User {user.username} logged in successfully.")
            return redirect('/dashboard')
        else:
            flash('Invalid email or password')
            logging.warning("Invalid login attempt.")
            return redirect('/login')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['name']
        email = request.form['email']
        password_input = request.form['password']

        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash('Username or email already exists.')
            logging.warning("Attempted registration with existing username or email.")
            return redirect('/register')

        hashed_password = generate_password_hash(password_input)
        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash('User registered successfully! Please log in.')
        logging.info(f"New user {username} registered successfully.")
        return redirect('/login')

    return render_template('register.html')

@app.route('/upload')
def upload():
    return render_template('VideoUpload.html')

@app.route('/upload_file', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash("No file part")
        logging.warning("File upload attempted with no file part.")
        return redirect("/upload")
    file = request.files['file']
    if file.filename == '':
        flash('No File Selected')
        logging.warning("File upload attempted with no file selected.")
        return redirect("/upload")
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(upload_path)

            in_path = upload_path
            out_path = os.path.join("static", "outs", "output.avi")
            if os.path.exists(out_path):
                os.remove(out_path)
            amp(in_path=in_path, out_path=out_path, alpha=2.5, beta=0.5, m=3)
            os.remove(in_path)

            flash(f"Your processed video is available <a href='/{out_path}' target='_blank'>here</a>")
            logging.info(f"File {filename} processed successfully.")
            return redirect("/upload")
        except Exception as e:
            logging.error(f"Error during file processing: {str(e)}")
            flash("Error processing file.")
            return redirect("/upload")
    else:
        flash("File in wrong format!")
        logging.warning("File upload attempted with wrong format.")
        return redirect("/upload")

@app.route('/<int:id>/submit_complaintt', methods=['GET', 'POST'])
def submit_complaintt(id):
    if request.method == 'POST':
        full_name = request.form['fullName']
        email = request.form['email']
        alert_type = request.form['alertType']
        description = request.form['description']
        file_data = request.files['file'].read() if 'file' in request.files else None

        try:
            complaintt = complaint(full_name=full_name, email=email, alert_type=alert_type, description=description,
                                  file_data=file_data, user_id=id)
            db.session.add(complaintt)
            db.session.commit()
            logging.info(f"complaint submitted successfully by user ID {id}.")
            flash("Your complaintt has been recorded. We'll get back to you soon.")
            return redirect(f'/complaint/{id}')
        except Exception as e:
            logging.error(f"Error submitting complaintt for user ID {id}: {str(e)}")
            flash("Error recording complaintt.")
            return redirect(f'/complaint/{id}')

@app.route('/fire-detected', methods=['POST'])
def fire_detected():
    try:
        send_alert_message()
        threading.Thread(target=play_alert_sound).start()
        logging.info("Fire alert triggered.")
        return jsonify({"message": "Fire alert triggered successfully!"}), 200
    except Exception as e:
        logging.error(f"Error triggering fire alert: {str(e)}")
        return jsonify({"error": str(e)}), 500

def send_alert_message():
    try:
        message = client.messages.create(
            body="Fire detected! Please take immediate action.",
            from_=os.getenv('TWILIO_PHONE_NUMBER'),
            to=os.getenv('ADMIN_PHONE_NUMBER')
        )
        logging.info(f"SMS sent successfully. Message SID: {message.sid}")
    except Exception as e:
        logging.error(f"Error sending SMS: {str(e)}")

@app.route('/dashboard')
@login_required
def dash_page():
    cameras = Camera.query.filter_by(user_id=current_user.id).all()
    logging.info(f"Dashboard accessed by user {current_user.username}.")
    return render_template('dash.html', cameras=cameras)

@app.route('/manage_camera')
@login_required
def manage_cam_page():
    cameras = Camera.query.filter_by(user_id=current_user.id).all()
    return render_template('manage_cam.html', cameras=cameras)

@app.route('/get_cam_details', methods=['POST'])
@login_required
def getting_cam_details():
    camid = request.form.get('Cam_id')
    fire_bool = "fire" in request.form
    pose_bool = "pose_alert" in request.form
    r_bool = "R_zone" in request.form
    s_gear_bool = "Safety_gear" in request.form

    try:
        camera = Camera.query.filter_by(Cam_id=camid, user_id=current_user.id).first()
        if camera:
            camera.fire_detection = fire_bool
            camera.pose_alert = pose_bool
            camera.restricted_zone = r_bool
            camera.safety_gear_detection = s_gear_bool
        else:
            camera = Camera(user_id=current_user.id, Cam_id=camid, fire_detection=fire_bool,
                            pose_alert=pose_bool, restricted_zone=r_bool, safety_gear_detection=s_gear_bool)
        db.session.add(camera)
        db.session.commit()
        logging.info(f"Camera details updated for user ID {current_user.id}.")
    except Exception as e:
        logging.error(f"Error updating camera details for user ID {current_user.id}: {str(e)}")
    return redirect("/manage_camera")

@app.route('/notifications')
@login_required
def notifications():
    try:
        alerts = Alert.query.filter_by(user_id=current_user.id).order_by(Alert.date_time.desc()).all()
        for alert in alerts:
            if alert.frame_snapshot:
                alert.frame_snapshot = base64.b64encode(alert.frame_snapshot).decode('utf-8')
        logging.info(f"Notifications accessed by user {current_user.username}.")
        return render_template('notifications.html', alerts=alerts)
    except Exception as e:
        logging.error(f"Error loading notifications: {str(e)}")
        flash("Error loading notifications.")
        return redirect('/dashboard')

@app.route('/complaint')
@login_required
def complaint():
    complaint = complaint.query.filter_by(user_id=current_user.id).all()
    for complaintt in complaint:
        if complaintt.file_data:
            complaintt.file_data = base64.b64encode(complaintt.file_data).decode('utf-8')
    logging.info(f"complaints accessed by user {current_user.username}.")
    return render_template('complaint.html', complaint=complaint, user=current_user)

@app.route('/complaint/<int:id>')
def complaint_form(id):
    user = User.query.filter_by(id=id).first()
    logging.info(f"complaint form accessed for user ID {id}.")
    return render_template("complaint_form.html", username=user.username, id=user.id)

@app.route('/delete/<int:id>')
@login_required
def delete(id):
    try:
        complaintt = complaint.query.filter_by(id=id, user_id=current_user.id).first()
        if complaintt:
            db.session.delete(complaintt)
            db.session.commit()
            flash('complaint deleted successfully!', 'success')
            logging.info(f"complaint with ID {id} deleted by user {current_user.username}.")
        else:
            flash('complaint not found or unauthorized access!', 'error')
            logging.warning(f"Unauthorized delete attempt for complaintt ID {id} by user {current_user.username}.")
    except Exception as e:
        logging.error(f"Error deleting complaintt with ID {id}: {str(e)}")
        flash('An error occurred while deleting the complaintt!', 'error')
    return redirect("/complaint")

@app.route('/delete_notification/<int:id>')
@login_required
def delete_notification(id):
    try:
        alert = Alert.query.filter_by(id=id, user_id=current_user.id).first()
        if alert:
            db.session.delete(alert)
            db.session.commit()
            flash('Notification deleted successfully!', 'success')
            logging.info(f"Notification with ID {id} deleted by user {current_user.username}.")
        else:
            flash('Notification not found or unauthorized access!', 'error')
            logging.warning(f"Unauthorized delete attempt for notification ID {id} by user {current_user.username}.")
    except Exception as e:
        logging.error(f"Error deleting notification with ID {id}: {str(e)}")
        flash('An error occurred while deleting the notification!', 'error')
    return redirect("/notifications")

@app.route('/delete_camera/<int:id>', methods=['GET', 'POST'])
@login_required
def delete_camera(id):
    try:
        camera = Camera.query.filter_by(id=id, user_id=current_user.id).first()
        if camera:
            db.session.delete(camera)
            db.session.commit()
            flash('Camera deleted successfully!', 'success')
            logging.info(f"Camera with ID {id} deleted by user {current_user.username}.")
        else:
            flash('Camera not found or unauthorized access!', 'error')
            logging.warning(f"Unauthorized delete attempt for camera ID {id} by user {current_user.username}.")
    except Exception as e:
        logging.error(f"Error deleting camera with ID {id}: {str(e)}")
        flash('An error occurred while deleting the camera!', 'error')

    # Keep only the last 2 flash messages
    session["_flashes"] = session.get("_flashes", [])[-2:]

    return redirect('/manage_camera')

@app.route('/analytics')
def analytics():
    return render_template('analytics.html')

@app.route('/logout')
@login_required
def logout():
    try:
        logging.info(f"User {current_user.username} logged out.")
        logout_user()
    except Exception as e:
        logging.error(f"Error during logout: {str(e)}")
    return redirect('/')

@app.route('/video_feed/<string:Cam_id>')
@login_required
def video_feed(Cam_id):
    camera = Camera.query.filter_by(Cam_id=str(Cam_id), user_id=current_user.id).first()
    if camera:
        flag_r_zone = camera.restricted_zone
        flag_pose_alert = camera.pose_alert
        flag_fire = camera.fire_detection
        flag_gear = camera.safety_gear_detection
        region = camera.region

        try:
            logging.info(f"Video feed accessed for camera ID {Cam_id} by user {current_user.username}.")
            return Response(process_frames(str(Cam_id), region, flag_r_zone, flag_pose_alert,
                                           flag_fire, flag_gear, current_user.id),
                            mimetype='multipart/x-mixed-replace; boundary=frame')
        except Exception as e:
            logging.error(f"Error accessing video feed for camera ID {Cam_id}: {str(e)}")
            return f"Error occurred: {str(e)}"
    else:
        logging.warning(f"Camera ID {Cam_id} not found for user {current_user.username}.")
        return "Camera details not found."
    
#-----------CHATBOT-----------------
API_KEY = os.getenv("GEMINI_API_KEY")

@app.route('/chatbot')
def chatbot():
    return render_template('chatbot.html') 

#----------------------



def add_to_db(results, frame, alert_name, user_id=None):
    if isinstance(results[0], bool) and results[0]:
        for box in results[1]:
            x1, y1, x2, y2 = box
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)

        with app.app_context():
            latest_alert = Alert.query.filter_by(alert_type=alert_name, user_id=user_id).order_by(Alert.date_time.desc()).first()
            if (latest_alert is None) or ((datetime.now() - latest_alert.date_time) > timedelta(minutes=1)):
                new_alert = Alert(
                    date_time=datetime.now(),
                    alert_type=alert_name,
                    frame_snapshot=cv2.imencode('.jpg', frame)[1].tobytes(),
                    user_id=user_id
                )
                db.session.add(new_alert)
                db.session.commit()
                logging.info(f"Added alert of type {alert_name} for user ID {user_id}.")

def process_frames(camid, region, flag_r_zone=False, flag_pose_alert=False, flag_fire=False, flag_gear=False, user_id=None):
    """
    Process video frames and apply detection logic.
    """
    # Use numeric camera index if camid is digit, else assume URL
    if camid.isdigit():
        cap = cv2.VideoCapture(int(camid))
    else:
        address = f"http://{camid}/video"
        cap = cv2.VideoCapture(address)

    persistent_boxes = {
        "restricted_zone": [],
        "fire": [],
        "gear": []
    }

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            logging.warning(f"No frames received from camera ID {camid}.")
            break

        try:
            # Resize frame to desired size
            frame = cv2.resize(frame, (1280, 720))

            # Build overlay text for active processes
            processes = []
            if flag_r_zone:
                processes.append("Restricted Zone Detection")
            if flag_fire:
                processes.append("Fire Detection")
            if flag_gear:
                processes.append("Safety Gear Detection")
            if flag_pose_alert:
                processes.append("Pose Detection")

            # Pose detection processing
            if flag_pose_alert:
                def alert_callback(alerts):
                    for alert in alerts:
                        threading.Thread(target=play_alert_sound).start()
                        add_to_db((True, [alert['bbox']]), alert['frame'], "Emergency Pose Detected", user_id)
                frame = pose_detector.process_frame(frame, alert_callback)

            # Restricted zone detection
            if flag_r_zone:
                r_zone_status, r_zone_boxes = r_zone.process(frame, region=region, flag=flag_r_zone)
                if r_zone_status:
                    persistent_boxes["restricted_zone"] = r_zone_boxes
                for box in persistent_boxes["restricted_zone"]:
                    x1, y1, x2, y2 = box
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                    cv2.putText(frame, "Restricted Zone Violation", (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

            # Fire detection
            if flag_fire:
                fire_status, fire_boxes = fire_det.process(frame, flag=flag_fire)
                if fire_status:
                    persistent_boxes["fire"] = fire_boxes
                for box in persistent_boxes["fire"]:
                    x1, y1, x2, y2 = box
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    cv2.putText(frame, "Fire Detected", (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

            # Safety gear detection
            if flag_gear:
                gear_status, gear_boxes = gear_det.process(frame, flag=flag_gear)
                if gear_status:
                    persistent_boxes["gear"] = gear_boxes
                for box in persistent_boxes["gear"]:
                    x1, y1, x2, y2 = box
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, "Gear Detected", (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # Overlay active process text
            overlay_text = " + ".join(processes)
            cv2.putText(frame, overlay_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            # Encode and yield the frame
            _, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        except Exception as e:
            logging.error(f"Error processing frame from camera ID {camid}: {e}")
            continue

    cap.release()

if __name__ == "__main__":
    app.run(debug=True)
