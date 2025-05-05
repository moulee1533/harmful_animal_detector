import cv2
import os
import datetime
import smtplib
from flask import Flask, Response, render_template
from flask_sock import Sock
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from ultralytics import YOLO
from email.mime.base import MIMEBase
from email import encoders

# Initialize Flask and Flask-Sock (WebSocket)
app = Flask(__name__)
sock = Sock(app)

# Load YOLOv8 model
model = YOLO("yolov8n.pt")

# List of harmful animals
harmful_animals = ["bear", "snake", "scorpion"]

# Make detections folder
os.makedirs("detections", exist_ok=True)

# Email alert function
def send_email(subject, body, filename=None):
    sender_email = "moulee410@gmail.com"
    receiver_email = "mouleejas@gmail.com"
    password = "ykvzxgrvtitnwwms"

    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    if filename:
        with open(filename, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={os.path.basename(filename)}",
            )
            message.attach(part)

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, message.as_string())
        server.quit()
        print(f"[Email] Alert sent to {receiver_email}")
    except Exception as e:
        print(f"[Email Error] {str(e)}")

# Global webcam
cap = cv2.VideoCapture(0)
clients = []

# WebSocket handler
@sock.route('/ws')
def websocket(ws):
    clients.append(ws)
    while True:
        try:
            ws.receive()
        except:
            clients.remove(ws)
            break

# Video stream generator
def gen_frames():
    while True:
        success, frame = cap.read()
        if not success:
            break

        results = model(frame)
        annotated_frame = results[0].plot()

        for r in results:
            for c in r.boxes.cls:
                label = model.names[int(c)]
                if label in harmful_animals:
                    print(f"[!] Harmful animal detected: {label}")
                    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"detections/{label}_{timestamp}.jpg"
                    cv2.imwrite(filename, frame)

                    subject = f"Alert: {label} detected"
                    body = f"A {label} was detected at {timestamp}.\nImage saved at {filename}"
                    send_email(subject, body, filename)

                    # Alert all clients via WebSocket
                    for ws in clients:
                        try:
                            ws.send("alert")
                        except:
                            clients.remove(ws)

        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

# Home route
@app.route('/')
def index():
    return render_template('index.html')

# Video feed route
@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
