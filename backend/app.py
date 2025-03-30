from flask import Flask, request, jsonify,send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
import smtplib
from email.message import EmailMessage
from bson import ObjectId
from datetime import datetime
import time
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import os 
import sys
import bcrypt
from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
from bson import ObjectId
from fastapi.middleware.cors import CORSMiddleware
from werkzeug.utils import secure_filename 

app = Flask(__name__)

CORS(app, resources={r"/*": {"origins": "http://localhost:5173"}}, supports_credentials=True)
app = Flask(__name__)

CORS(app) 

client = MongoClient("mongodb://localhost:27017/")
db = client["event_db"]
collection = db["registrations"]
hall_collections = {
    "Seminar Hall 1": db["seminar_hall_1"],
    "Seminar Hall 2": db["seminar_hall_2"],
    "Seminar Hall 3": db["seminar_hall_3"]
}


COORDINATOR_EMAIL = "coordinator@example.com"  # Replace with actual coordinator email
APPROVED_EMAILS = ["ajaiks2005@gmail.com", "tm07hariharan2122@gmail.com", "ajaisha2021@gmail.com"]

users = {
    "kncet@principal": {"password": bcrypt.hashpw("principal@123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'), "role": "principal"},
    "hod.it@kncet": {"password": bcrypt.hashpw("hodit@123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'), "role": "hod", "department": "IT"},
    "hod.cse@kncet": {"password": bcrypt.hashpw("hodcse@123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'), "role": "hod", "department": "CSE"},
    "hod.ece@kncet": {"password": bcrypt.hashpw("hodece@123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'), "role": "hod", "department": "ECE"},
    "hod.eee@kncet": {"password": bcrypt.hashpw("hodeee@123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'), "role": "hod", "department": "EEE"},
    "hod.civil@kncet": {"password": bcrypt.hashpw("hodcivil@123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'), "role": "hod", "department": "Civil"},
    "hod.bme@kncet": {"password": bcrypt.hashpw("hodbme@123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'), "role": "hod", "department": "BME"},
    "hod.agri@kncet": {"password": bcrypt.hashpw("hodagri@123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'), "role": "hod", "department": "Agri"},
    "hod.ads@kncet": {"password": bcrypt.hashpw("hodads@123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'), "role": "hod", "department": "ADS"},
    "hod.mech@kncet": {"password": bcrypt.hashpw("hodmech@123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'), "role": "hod", "department": "Mech"},
}

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    user_id = data.get("id")
    password = data.get("password")

    user = users.get(user_id)
    
    if user and bcrypt.checkpw(password.encode('utf-8'), user["password"].encode('utf-8')):
        response = {"message": "Login successful", "user": user_id, "role": user["role"]}
        if user["role"] == "hod":
            response["department"] = user["department"]
        return jsonify(response), 200
    else:
        return jsonify({"message": "Invalid credentials"}), 401


@app.route("/approved_bookings", methods=["GET"])
def get_approved_bookings():
    try:
        approved_bookings = {}
        current_time = datetime.now()

        for hall_name, collection in hall_collections.items():
            bookings = list(collection.find({"status": "approved"}))

            for booking in bookings:
                booking["_id"] = str(booking["_id"]) 

                print(f"Checking booking: {booking}")

                if "Date" not in booking or "TimeTo" not in booking:
                    print(f"Skipping booking due to missing Date or TimeTo: {booking}")
                    continue

                try:
                    booking_date = datetime.strptime(booking["Date"], "%Y-%m-%d")
                    end_time = datetime.strptime(booking["TimeTo"], "%H:%M")
                    booking_end_datetime = datetime.combine(booking_date.date(), end_time.time())

                    if booking_end_datetime < current_time:
                        collection.update_one(
                            {"_id": ObjectId(booking["_id"])},
                            {"$set": {"status": "Completed"}}
                        )
                        booking["status"] = "Completed"
                        print(f"✅ Status updated to 'Completed' for booking: {booking}")

                except ValueError as e:
                    print(f"❌ Error parsing date/time: {e}")

            approved_bookings[hall_name] = bookings

        return jsonify(approved_bookings)

    except Exception as e:
        print(f"🔥 Server error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/cancel_booking/<booking_id>", methods=["PUT"])
def cancel_booking(booking_id):
    try:
        if not ObjectId.is_valid(booking_id):
            return jsonify({"error": "Invalid booking ID"}), 400

        data = request.json 
        cancel_reason = data.get("cancel_reason", "")

        if not cancel_reason:
            return jsonify({"error": "Cancellation reason is required"}), 400

        for hall_name, collection in hall_collections.items():
            booking = collection.find_one({"_id": ObjectId(booking_id)})
            if booking:
                result = collection.update_one(
                    {"_id": ObjectId(booking_id)},
                    {"$set": {"status": "Cancelled", "cancel_reason": cancel_reason}}
                )

                if result.modified_count == 1:
                    return jsonify({"message": f"Booking in {hall_name} cancelled successfully"})

                return jsonify({"error": "Failed to update booking status"}), 500

        return jsonify({"error": "Booking not found"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/canceled_bookings", methods=["GET"])
def get_canceled_bookings():
    try:
        canceled_bookings = {}

        for hall_name, collection in hall_collections.items():
            bookings = list(collection.find({"status": "Cancelled"}))

            for booking in bookings:
                booking["_id"] = str(booking["_id"])

            canceled_bookings[hall_name] = bookings  

        return jsonify(canceled_bookings)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def update_completed_bookings():
    """Automatically updates completed seminar hall bookings and sends emails."""
    try:
        current_time = datetime.now()

        for hall_name, collection in hall_collections.items():
            bookings = list(collection.find({"status": "approved"}))

            for booking in bookings:
                try:
                    booking["_id"] = str(booking["_id"])  # Convert ObjectId to string

                    booking_date_str = booking.get("Date")
                    end_time_str = booking.get("TimeTo")

                    if not booking_date_str or not end_time_str:
                        print(f"⚠️ Skipping booking due to missing Date or TimeTo: {booking}")
                        continue

                    # Convert booking date and time correctly
                    booking_date = datetime.strptime(booking_date_str, "%Y-%m-%d")
                    end_time = datetime.strptime(end_time_str, "%H:%M")
                    booking_end_datetime = datetime.combine(booking_date.date(), end_time.time())

                    if booking_end_datetime < current_time:
                        # Update status to 'Completed'
                        collection.update_one(
                            {"_id": ObjectId(booking["_id"])},
                            {"$set": {"status": "Completed"}}
                        )
                        print(f"✅ Status updated to 'Completed' for booking: {booking}")

                        # Send automatic email for completed booking
                        send_completed_booking_email(hall_name, booking)

                except ValueError as e:
                    print(f"❌ Error parsing date/time: {e}")
                except Exception as e:
                    print(f"🔥 Unexpected error: {e}")

    except Exception as e:
        print(f"🔥 Server error: {e}")


def send_completed_booking_email(selected_hall, booking):
    """Sends an automatic email when a seminar hall booking is marked as 'Completed'."""
    try:
        coordinator_email = booking.get("CoordinatorEmail")

        subject = f"Seminar Hall Booking Completed - {selected_hall}"
        email_body = f"""
        <h2>Your seminar hall booking has been successfully completed.</h2>
        <p><strong>Coordinator Name:</strong> {booking.get("CoordinatorName", "N/A")}</p>
        <p><strong>Department:</strong> {booking.get("Department", "N/A")}</p>
        <p><strong>Event Name:</strong> {booking.get("EventName", "N/A")}</p>
        <p><strong>Total Participants:</strong> {booking.get("TotalParticipants", "N/A")}</p>
        <p><strong>Seminar Hall:</strong> {selected_hall}</p>
        <p><strong>Date:</strong> {booking.get("Date", "N/A")}</p>
        <p><strong>Time:</strong> {booking.get("TimeFrom", "N/A")} - {booking.get("TimeTo", "N/A")}</p>
        <p><strong>Coordinator Email:</strong> {coordinator_email}</p>
        <p><strong>Coordinator Phone:</strong> {booking.get("CoordinatorPhone", "N/A")}</p>
        <p><strong>Organized By:</strong> {booking.get("OrganizedBy", "N/A")}</p>
        """

        recipients = [coordinator_email, "yuthikam2005@gmail.com", "sahanamagesh72@gmail.com", "darav4852@gmail.com"]

        for recipient in recipients:
            send_email(recipient, subject, email_body)

        print(f"📧 Automatic completion email sent to: {recipients}")

    except Exception as e:
        print(f"❌ Error sending completion email: {e}")

@app.route("/completed_bookings", methods=["GET"])
def get_completed_bookings():
    try:
        completed_bookings = {}

        for hall_name, collection in hall_collections.items():
            bookings = list(collection.find({"status": "Completed"}))

            for booking in bookings:
                booking["_id"] = str(booking["_id"])

            completed_bookings[hall_name] = bookings  

        return jsonify(completed_bookings)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route("/upload_details", methods=["POST"])
def upload_details():
    try:
        booking_id = request.form.get("bookingId")
        hall_name = request.form.get("hallName")
        extra_details = request.form.get("extraDetails")
        image_file = request.files.get("image")

        if not (booking_id and hall_name and extra_details and image_file):
            return jsonify({"success": False, "message": "Missing required fields"}), 400

        if hall_name not in hall_collections:
            return jsonify({"success": False, "message": "Invalid seminar hall"}), 400

        collection = hall_collections[hall_name]

        filename = secure_filename(image_file.filename)
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        image_file.save(image_path)

        try:
            booking_object_id = ObjectId(booking_id)
        except Exception as e:
            return jsonify({"success": False, "message": "Invalid booking ID", "error": str(e)}), 400

        update_result = collection.update_one(
            {"_id": booking_object_id},
            {"$set": {
                "status": "Total Completed",
                "extraDetails": extra_details,
                "imagePath": filename 
            }}
        )

        if update_result.modified_count == 0:
            return jsonify({"success": False, "message": "Booking not found or update failed"}), 500

        return jsonify({"success": True, "message": "Details uploaded and status updated successfully!"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory("uploads", filename)

@app.route("/total_completed_bookings", methods=["GET"])
def get_total_completed_bookings():
    try:
        total_completed_bookings = {}

        for hall_name, collection in hall_collections.items():
            bookings = list(collection.find({"status": "Total Completed"}))

            for booking in bookings:
                booking["_id"] = str(booking["_id"]) 

                if "imagePath" in booking and booking["imagePath"]:
                    booking["imagePath"] = f"http://127.0.0.1:5000/uploads/{booking['imagePath']}"
                else:
                    booking["imagePath"] = None 

            total_completed_bookings[hall_name] = bookings

        return jsonify(total_completed_bookings), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    
@app.route("/bookings", methods=["GET"])
def get_all_bookings():
    try:
        all_bookings = {}
        for hall, collection in hall_collections.items():
            bookings = list(collection.find({}, {"_id": 1, "CoordinatorName": 1, "EventName": 1, "Date": 1, "TimeFrom": 1, "TimeTo": 1, "status": 1}))
            for booking in bookings:
                booking["_id"] = str(booking["_id"]) 
            all_bookings[hall] = bookings

        return jsonify(all_bookings), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    
@app.route("/update_booking_status", methods=["POST"])
def update_booking_status():
    try:
        data = request.json
        selected_hall = data.get("SelectedSeminarHall")
        coordinator_email = data.get("CoordinatorEmail")
        status = data.get("status")

        if status not in ["approved", "declined"]:
            return jsonify({"error": "Invalid status update"}), 400

        booking = hall_collections[selected_hall].find_one(
            {"CoordinatorEmail": coordinator_email, "status": "pending"}
        )

        if not booking:
            return jsonify({"error": "Booking not found or already processed"}), 404

        hall_collections[selected_hall].update_one(
            {"CoordinatorEmail": coordinator_email, "status": "pending"},
            {"$set": {"status": status}}
        )

        subject = f"Seminar Hall Booking {status.capitalize()} - {selected_hall}"
        email_body = f"""
        <h2>Your seminar hall booking has been {status}.</h2>
        <p><strong>Coordinator Name:</strong> {booking["CoordinatorName"]}</p>
        <p><strong>Department:</strong> {booking["Department"]}</p>
        <p><strong>Event Name:</strong> {booking["EventName"]}</p>
        <p><strong>Total Participants:</strong> {booking["TotalParticipants"]}</p>
        <p><strong>Seminar Hall:</strong> {selected_hall}</p>
        <p><strong>Date:</strong> {booking["Date"]}</p>
        <p><strong>Time:</strong> {booking["TimeFrom"]} - {booking["TimeTo"]}</p>
        <p><strong>Coordinator Email:</strong> {booking["CoordinatorEmail"]}</p>
        <p><strong>Coordinator Phone:</strong> {booking["CoordinatorPhone"]}</p>
        <p><strong>Organized By:</strong> {booking["OrganizedBy"]}</p>
        """

        if status == "approved":
            recipients = [coordinator_email, "yuthikam2005@gmail.com", "sahanamagesh72@gmail.com", "darav4852@gmail.com"]
        else: 
            recipients = [coordinator_email]

        for recipient in recipients:
            send_email(recipient, subject, email_body)

        return jsonify({"success": True, "message": f"Booking {status} and email sent!"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route("/pending_bookings", methods=["GET"])
def get_pending_bookings():
    try:
        pending_bookings = {}
        for hall_name, collection in hall_collections.items():
            pending_bookings[hall_name] = list(collection.find({"status": "pending"}, {"_id": 0}))

        return jsonify(pending_bookings)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/bookings/<hall_name>", methods=["GET"])
def get_hall_bookings(hall_name):
    try:
        if hall_name not in hall_collections:
            return jsonify({"error": "Invalid seminar hall"}), 400

        bookings = list(hall_collections[hall_name].find({}, {"_id": 1, "CoordinatorName": 1, "EventName": 1, "Date": 1, "TimeFrom": 1, "TimeTo": 1, "status": 1}))
        for booking in bookings:
            booking["_id"] = str(booking["_id"])

        return jsonify(bookings), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


pending_bookings = {}

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_SENDER = "ajaiks2005@gmail.com" 
EMAIL_PASSWORD = "zenc picd tkwb tewq"  

def send_email(to_email, subject, body):
    try:
        msg = EmailMessage()
        msg.set_content(body, subtype="html")  
        msg["Subject"] = subject
        msg["From"] = EMAIL_SENDER
        msg["To"] = to_email

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"✅ Email sent to {to_email}")
    except Exception as e:
        print(f"❌ Error sending email: {e}")

@app.route("/check_availability", methods=["POST"])
def check_availability():
    try:
        data = request.json
        selected_hall = data.get("SelectedSeminarHall")
        date = data.get("Date")
        time_from = data.get("TimeFrom")
        time_to = data.get("TimeTo")

        if not selected_hall or not date or not time_from or not time_to:
            return jsonify({"available": False, "message": "Invalid input"}), 400

        existing_booking = hall_collections[selected_hall].find_one({
            "Date": date,
            "$or": [
                {"TimeFrom": {"$lte": time_to}, "TimeTo": {"$gte": time_from}}
            ],
            "status": {"$in": ["pending", "approved"]}
        })

        if existing_booking:
            return jsonify({"available": False, "message": "Slot already booked!"}), 200

        return jsonify({"available": True}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/book", methods=["POST"])
def book_seminar():
    try:
        data = request.json
        selected_hall = data.get("SelectedSeminarHall")

        if not selected_hall or selected_hall not in hall_collections:
            return jsonify({"error": "Invalid seminar hall selection"}), 400
        
        data["status"] = "pending"
        booking_id = hall_collections[selected_hall].insert_one(data).inserted_id

        login_link = "http://localhost:5173/"

        products_html = ""
        if "products" in data and isinstance(data["products"], list):
            products_html += "<ul>"
            for product in data["products"]:
                product_name = product.get("name", "Unknown Product")
                product_quantity = product.get("quantity", 0)
                products_html += f"<li>{product_name} - {product_quantity}</li>"
            products_html += "</ul>"
        else:
            products_html = "<p>No products selected</p>"

        admin_email_body = f'''
        <h2>New Seminar Hall Booking Request</h2>
        <p><strong>Coordinator Name:</strong> {data["CoordinatorName"]}</p>
        <p><strong>Department:</strong> {data["Department"]}</p>
        <p><strong>Event Name:</strong> {data["EventName"]}</p>
        <p><strong>Total Participants:</strong> {data["TotalParticipants"]}</p>
        <p><strong>Seminar Hall:</strong> {selected_hall}</p>
        <p><strong>Date:</strong> {data["Date"]}</p>
        <p><strong>Time:</strong> {data["TimeFrom"]} - {data["TimeTo"]}</p>
        <p><strong>Coordinator Email:</strong> {data["CoordinatorEmail"]}</p>
        <p><strong>Coordinator Phone:</strong> {data["CoordinatorPhone"]}</p>
        <p><strong>Organized By:</strong> {data["OrganizedBy"]}</p>
        <p><strong>Products Requested:</strong></p>
        {products_html}
        <p>Please log in, approve, or decline:</p>
        <a href="{login_link}" style="padding:10px; background-color:blue; color:white; text-decoration:none; display:block; margin-bottom:10px;">Login</a>
        '''

        send_email("ajaisha2021@gmail.com", "Seminar Hall Booking Approval", admin_email_body)

        return jsonify({
            "success": True,
            "message": f"Booking request for {selected_hall} stored and approval email sent!",
            "booking_id": str(booking_id)
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/image", methods=["POST"])
def image():
    try:
        image = request.files["image"]
        image.save("image.jpg")
        return "Image uploaded successfully!", 200
    except Exception as e:
        return str(e), 500

if __name__ == "__main__":
    app.run(debug=True, port=5001)


