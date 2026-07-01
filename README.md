# AuraFace Attendance Portal — Integration & Backend Engine
*Developed by Darshan M Bangre*

A comprehensive, state-of-the-art **Face Recognition Attendance System** featuring a JWT-secured REST API, dynamic SQLite/MySQL dual database support, a multi-tier facial verification engine, a guided multi-angle enrollment flow, and a gorgeous glassmorphic Admin Dashboard.

---

## 🚀 Key Features

*   **Secure Administration**: JWT token authorization (HMAC-SHA256) protects all core HR and employee metadata directories.
*   **Dual-Database Auto-Setup**: Detects MySQL parameters in environmental files, otherwise defaults to a lightweight local SQLite database (`attendance.db`) for immediate out-of-the-box local executions.
*   **Multi-Tier Face Engine**:
    1.  *InsightFace (Primary)*: Runs high-precision ONNX models (**RetinaFace** for face detection, **ArcFace w600k_r50** for 512D face embeddings) via CPU ONNX Runtime.
    2.  *dlib (Legacy option)*: Automatically falls back to the standard `face_recognition` library (128D embeddings).
    3.  *OpenCV DNN (ONNX option)*: Fallback for **YuNet** detector and **SFace** (112D embeddings) in OpenCV's DNN module.
    4.  *Haar Cascade (Failsafe local option)*: Runs OpenCV Haar Cascades and crops/normalizes grayscale face features to calculate scale-invariant pixel similarity vectors (256D vectors).
*   **Guided Multi-Angle Enrollment**: Guides employees through capturing **5 distinct facial poses** (Straight, Left, Right, Up, Smile) to build a robust dataset.
*   **Strict Concurrency Checks**: A multi-layered lock system (at both the frontend loop level and backend database constraint level) prevents duplicate check-ins.
*   **Verify Cool-Down Security**: Automatically shuts down camera streams on a match and enforces a **5-second cool-down delay** to avoid spamming.
*   **Lateness Threshold Calculations**: Logs check-in status automatically (09:00 to 09:30 is *Present*, 09:45 onwards is *Late*, and 12:00 onwards is *Half-Day*).
*   **Export Center**: Generates formatted daily, monthly, late arrival, and employee attendance summaries as **CSV** or **PDF Reports** (via `reportlab`).

---

## 🛠️ Technology Stack

*   **Backend Server**: Python 3.11+, Flask, PyJWT, PyMySQL, Flask-CORS
*   **Computer Vision**: OpenCV (cv2), NumPy, Pillow (PIL), MediaPipe, InsightFace, ONNX Runtime
*   **Reports Engine**: ReportLab (PDF generators)
*   **Frontend UI**: HTML5 Semantic Grid, Custom Vanilla CSS, Boxicons, Chart.js

---

## 📦 Getting Started

### 1. Installation
Install dependencies in your python environment:
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables (.env)
To use a production MySQL database and SMTP mail system, configure a `.env` file in the root directory:
```env
# Flask Settings
SECRET_KEY=super-secret-key-change-in-production
JWT_SECRET_KEY=jwt-secret-key-change-in-production

# DB Config (Omit to fallback to SQLite local file database)
DB_TYPE=sqlite
SQLITE_PATH=attendance.db

# Production MySQL DB Config (Uncomment to use MySQL)
# DB_TYPE=mysql
# DB_HOST=127.0.0.1
# DB_USER=root
# DB_PASSWORD=your_root_password
# DB_NAME=face_attendance
# DB_PORT=3306

# SMTP Mail Settings (Optional)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your_hr_email@gmail.com
MAIL_PASSWORD=your_app_password
MAIL_DEFAULT_SENDER=your_hr_email@gmail.com
```

### 3. Running the Server
Run the Flask server:
```bash
python app.py
```
Open [http://localhost:5000](http://localhost:5000) in your web browser.
*   **Default Admin Username**: `admin`
*   **Default Admin Password**: `admin123`

---

## 🛢️ Database Schema & Integration Guide

The database manager in [database.py](file:///c:/Users/HP/OneDrive/Desktop/face_detection/database.py) executes non-destructive schema migrations on startup. If columns are missing in your existing employee tables, they will be appended safely without data loss.

### SQL Tables DDL (SQLite & MySQL)

```sql
-- 1. Employees Table
CREATE TABLE IF NOT EXISTS employees (
    employee_id INT AUTO_INCREMENT PRIMARY KEY,
    employee_name VARCHAR(100) NOT NULL,
    department VARCHAR(100),
    designation VARCHAR(100),
    email VARCHAR(100),
    mobile VARCHAR(20),
    status INT DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. Face Embeddings Dataset Table (Allows multiple poses/angles per employee)
CREATE TABLE IF NOT EXISTS face_embeddings (
    embedding_id INT AUTO_INCREMENT PRIMARY KEY,
    employee_id INT NOT NULL,
    embedding JSON NOT NULL,
    model_version VARCHAR(50) DEFAULT 'v1',
    created_date DATETIME NOT NULL,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. Attendance Table (Armed with a unique constraint on employee_id and date)
CREATE TABLE IF NOT EXISTS attendance (
    attendance_id INT AUTO_INCREMENT PRIMARY KEY,
    employee_id INT NOT NULL,
    attendance_date DATE NOT NULL,
    check_in TIME NOT NULL,
    check_out TIME,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    device_id VARCHAR(100),
    confidence_score FLOAT,
    image_path VARCHAR(255),
    status VARCHAR(50) DEFAULT 'Present',
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE,
    UNIQUE KEY unique_emp_date (employee_id, attendance_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 📱 Mobile Application Integration (API Reference)

### 1. Admin Authentication
Before calling enrollment or protected reporting APIs, acquire a JWT token.
*   **URL**: `/api/login`
*   **Method**: `POST`
*   **Headers**: `Content-Type: application/json`
*   **Request JSON**:
    ```json
    {
        "username": "admin",
        "password": "admin123"
    }
    ```
*   **Response JSON (200 OK)**:
    ```json
    {
        "success": true,
        "token": "eyJhbGciOiJIUzI1NiIsIn..."
    }
    ```

---

### 2. Guided Face Enrollment
Saves one of the facial training poses to the employee's dataset.
*   **URL**: `/api/enroll-face`
*   **Method**: `POST`
*   **Headers**: `Authorization: Bearer <jwt_token>`
*   **Request JSON**:
    ```json
    {
        "employee_id": 1,
        "image": "data:image/jpeg;base64,/9j/4AA..." // Base64 data URI
    }
    ```
*   **Response JSON (200 OK)**:
    ```json
    {
        "success": true,
        "message": "Face credentials successfully registered for Darshan.",
        "face_box": [192, 161, 148, 195]
    }
    ```

---

### 3. Edit/Overwrite Face Data
Re-registers or edits the face embeddings for an existing employee. Removes any old face models for this ID.
*   **URL**: `/api/enroll-face`
*   **Method**: `PUT`
*   **Headers**: `Authorization: Bearer <jwt_token>`
*   **Request JSON**:
    ```json
    {
        "employee_id": 1,
        "image": "data:image/jpeg;base64,/9j/4AA..." // Base64 data URI
    }
    ```
*   **Response JSON (200 OK)**:
    ```json
    {
        "success": true,
        "message": "Face credentials successfully updated (overwritten) for Darshan M Bangre.",
        "face_box": [192, 161, 148, 195]
    }
    ```

---

### 3. Face Verification
Matches a camera frame against registered face coordinates using Cosine Similarity (Dot Product).
*   **URL**: `/api/verify-face`
*   **Method**: `POST`
*   **Headers**: `Content-Type: application/json`
*   **Request JSON**:
    ```json
    {
        "image": "data:image/jpeg;base64,/9j/4AA..."
    }
    ```
*   **Response JSON (200 OK - Match)**:
    ```json
    {
        "success": true,
        "message": "Face recognized successfully!",
        "employee": {
            "employee_id": 1,
            "employee_name": "Darshan M Bangre",
            "department": "Engineering",
            "designation": "Solutions Architect",
            "email": "darshan@company.com"
        },
        "confidence_score": 0.892
    }
    ```

---

### 4. Log Attendance (Check-In)
Records check-in timestamp. Enforces database-level duplicate check-in prevention.
*   **URL**: `/api/attendance/checkin`
*   **Method**: `POST`
*   **Headers**: `Content-Type: application/json`
*   **Request JSON**:
    ```json
    {
        "employee_id": 1,
        "confidence_score": 0.892,
        "latitude": 12.9716,
        "longitude": 77.5946,
        "device_id": "Mobile_Android_14",
        "image": "data:image/jpeg;base64,/9j/4AA..." // Optional check-in photo
    }
    ```
*   **Response JSON (200 OK)**:
    ```json
    {
        "success": true,
        "message": "Check-in successfully recorded for Darshan M Bangre. Status: Present",
        "attendance_id": 42,
        "check_in": "09:15:30",
        "status": "Present"
    }
    ```
*   **Response JSON (400 Bad Request - Duplicate Entry)**:
    ```json
    {
        "success": false,
        "message": "Duplicate check-in blocked. Darshan M Bangre has already checked in today."
    }
    ```

---

## 🔒 Security & Verification Pipelines

### Bimeotric Pipeline Sequence
```
[Capture webcam/device frame] 
       ↓
[MediaPipe / RetinaFace Detection] 
       ↓
[Facial Landmark Crop & Alignment]
       ↓
[InsightFace ArcFace 512D Embeddings]
       ↓
[Dot Product (Cosine Similarity) Check]
       ↓
[KNN Voting Majority Classification (K=3)]
       ↓
[Validate Database UNIQUE Constraint]
       ↓
[Record check-in / Block duplicates]
```

### Verification Cool-Down UX
*   Once a matched face is detected, the frontend immediately shuts down all camera streams to release resources.
*   The "Start Verification" toggle button is disabled for **5 seconds** immediately following matching, blocking immediate camera re-activation and double checks.
*   If attendance is already marked today, the verify panel transitions into a static dark-red warning card: *"Already Marked: Attendance already registered for employee today. Camera closed."*

---

## 🧪 Postman Testing Collections
To test the server APIs immediately:
1.  Open **Postman**.
2.  Click **Import** and upload `postman_collection.json` from the root directory.
3.  Set the `base_url` variable to your server host (e.g. `http://127.0.0.1:5000`).
4.  Execute the **Login** API. The integrated post-request scripts will capture the JWT token and load it into your Postman environment automatically. Protected requests (like employee creation or audits) will work seamlessly!
