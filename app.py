import os
import cv2
import base64
from flask import Flask, render_template, Response, request, redirect, flash, session, jsonify
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import threading
from playsound import playsound
from dotenv import load_dotenv
import logging
from flask_migrate import Migrate


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

from twilio.rest import Client
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
client = Client(account_sid, auth_token)

from models.r_zone import people_detection
from models.fire_detection import fire_detection
from models.gear_detection import gear_detection
from models.Pose_Detect import alert
from models.motion_amp import amp

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///user.db'
app.config["SQLALCHEMY_BINDS"]={"complain":"sqlite:///complain.db",
                                "cams":"sqlite:///cams.db",
                                "alerts":"sqlite:///alerts.db"}

app.config['UPLOAD_FOLDER'] = 'uploads'
ALLOWED_EXTENSIONS = {"mp4"}

db = SQLAlchemy(app)
login_manager = LoginManager(app)


migrate = Migrate(app, db)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    email = db.Column(db.String(100))

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

class Complaint(db.Model):
    __bind_key__ = 'complain'  # Ensure it's connected to the right database
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    full_name = db.Column(db.String(100))
    email = db.Column(db.String(100))
    alert_type = db.Column(db.String(50))
    description = db.Column(db.Text)
    file_data = db.Column(db.LargeBinary)


r_zone = people_detection("models/yolov8n.pt")
fire_det = fire_detection("models/fire.pt", conf=0.60)
gear_det = gear_detection("models/gear.pt")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def play_alert_sound():
    try:
        for _ in range(3):
            playsound('static\sounds\alert.mp3')
        logging.info("Alert sound played successfully.")
    except Exception as e:
        logging.error(f"Error playing alert sound: {str(e)}")

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
        password = request.form['password']

        if not email or not password:
            flash('Email or Password Missing!!')
            return redirect('/login')

        user = User.query.filter_by(email=email).first()

        if user and user.password == password:
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
        password = request.form['password']

        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash('Username or email already exists.')
            logging.warning("Attempted registration with existing username or email.")
            return redirect('/register')

        new_user = User(username=username, email=email, password=password)
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
    if request.method == 'POST':
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
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                in_path = f"uploads/{filename}"
                out_path = f"static/outs/output.avi"
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
            flash("File in wrong Format!!")
            logging.warning("File upload attempted with wrong format.")
            return redirect("/upload")

@app.route('/<int:id>/submit_complaint', methods=['GET', 'POST'])
def submit_complaint(id):
    if request.method == 'POST':
        full_name = request.form['fullName']
        email = request.form['email']
        alert_type = request.form['alertType']
        description = request.form['description']
        file_data = request.files['file'].read() if 'file' in request.files else None

        try:
            complaint = Complaint(full_name=full_name, email=email, alert_type=alert_type, description=description,
                                  file_data=file_data, user_id=id)
            db.session.add(complaint)
            db.session.commit()
            logging.info(f"Complaint submitted successfully by user ID {id}.")
            flash("Your complaint has been recorded. We'll get back to you soon.")
            return redirect(f'/complain/{id}')
        except Exception as e:
            logging.error(f"Error submitting complaint for user ID {id}: {str(e)}")
            flash("Error recording complaint.")
            return redirect(f'/complain/{id}')

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
    if request.method == 'POST':
        camid = request.form['Cam_id']

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
                camera = Camera(user_id=current_user.id, Cam_id=camid, fire_detection=fire_bool, pose_alert=pose_bool,
                                restricted_zone=r_bool, safety_gear_detection=s_gear_bool)

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

@app.route('/complaints')
@login_required
def complaints():
    complaints = Complaint.query.filter_by(user_id=current_user.id).all()
    for complaint in complaints:
        if complaint.file_data:
            complaint.file_data = base64.b64encode(complaint.file_data).decode('utf-8')
    logging.info(f"Complaints accessed by user {current_user.username}.")
    return render_template('complaints.html', complaints=complaints, user=current_user)

@app.route('/complain/<int:id>')
def complain_form(id):
    user = User.query.filter_by(id=id).first()
    logging.info(f"Complaint form accessed for user ID {id}.")
    return render_template("complain_form.html", username=user.username, id=user.id)

@app.route('/delete/<int:id>')
@login_required
def delete(id):
    try:
        complaint = Complaint.query.filter_by(id=id, user_id=current_user.id).first()
        if complaint:
            db.session.delete(complaint)
            db.session.commit()
            flash('Complaint deleted successfully!', 'success')
            logging.info(f"Complaint with ID {id} deleted by user {current_user.username}.")
        else:
            flash('Complaint not found or unauthorized access!', 'error')
            logging.warning(f"Unauthorized delete attempt for complaint ID {id} by user {current_user.username}.")
    except Exception as e:
        logging.error(f"Error deleting complaint with ID {id}: {str(e)}")
        flash('An error occurred while deleting the complaint!', 'error')
    return redirect("/complaints")

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
    return redirect('/manage_camera')

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
                                           flag_fire, flag_gear, current_user.id), mimetype='multipart/x-mixed-replace; boundary=frame')
        except Exception as e:
            logging.error(f"Error accessing video feed for camera ID {Cam_id}: {str(e)}")
            return f"Error occurred: {str(e)}"
    else:
        logging.warning(f"Camera ID {Cam_id} not found for user {current_user.username}.")
        return "Camera details not found."

def add_to_db(results, frame, alert_name, user_id=None):
    # Explicitly check if results[0] is True
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

def process_frames(camid, region, flag_r_zone=False, flag_hand_alert=False, flag_fire=False, flag_gear=False, user_id=None):
    """
    Process video frames and apply the necessary detection logic based on the flags set.

    Args:
        camid (str): Camera ID or URL.
        region (bool): Region for restricted zone detection.
        flag_r_zone (bool): Enable restricted zone detection.
        flag_hand_alert (bool): Enable pose/hand gesture detection.
        flag_fire (bool): Enable fire detection.
        flag_gear (bool): Enable safety gear detection.
        user_id (int): ID of the user.

    Yields:
        bytes: Encoded video frame for streaming.
    """
    if len(camid) == 1:
        camid = int(camid)
        cap = cv2.VideoCapture(camid)
    else:
        address = f"http://{camid}/video"
        cap = cv2.VideoCapture(address)

    persistent_boxes = {
        "restricted_zone": [],
        "fire": [],
        "gear": [],
    }

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            logging.warning(f"No frames received from camera ID {camid}.")
            break

        try:
            frame = cv2.resize(frame, (1000, 500))

            # Text overlay for selected processes
            processes = []
            if flag_r_zone:
                processes.append("Restricted Zone Detection")
            if flag_fire:
                processes.append("Fire Detection")
            if flag_gear:
                processes.append("Safety Gear Detection")
            if flag_hand_alert:
                processes.append("Pose Alert")

            overlay_text = " + ".join(processes)
            cv2.putText(frame, overlay_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            # Perform restricted zone detection
            if flag_r_zone:
                r_zone_status, r_zone_boxes = r_zone.process(frame, region=region, flag=flag_r_zone)
                if r_zone_status:
                    persistent_boxes["restricted_zone"] = r_zone_boxes
                for box in persistent_boxes["restricted_zone"]:
                    x1, y1, x2, y2 = box
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                    cv2.putText(frame, "Restricted Zone Violation", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

            # Perform fire detection
            if flag_fire:
                fire_status, fire_boxes = fire_det.process(frame, flag=flag_fire)
                if fire_status:
                    persistent_boxes["fire"] = fire_boxes
                for box in persistent_boxes["fire"]:
                    x1, y1, x2, y2 = box
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    cv2.putText(frame, "Fire Detected", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

                

            # Perform safety gear detection
            if flag_gear:
                gear_status, gear_boxes = gear_det.process(frame, flag=flag_gear)
                if gear_status:
                    persistent_boxes["gear"] = gear_boxes
                for box in persistent_boxes["gear"]:
                    x1, y1, x2, y2 = box
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, "Gear Detected", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # Perform hand gesture detection
            if flag_hand_alert:
                frame, status, data = alert(frame, flag=flag_hand_alert)
                color = (0, 255, 0) if status == "safe" else (0, 0, 255)
                gesture_text = f"Gesture: {data.get('gesture', 'Unknown')}"
                cv2.putText(frame, gesture_text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

                if status == "unsafe":
                    threading.Thread(target=play_alert_sound).start()

            # Encode the frame and yield it
            _, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

        except Exception as e:
            logging.error(f"Error processing frame from camera ID {camid}: {e}")
            continue

    cap.release()


if __name__ == "__main__":
    app.run(debug=True)
