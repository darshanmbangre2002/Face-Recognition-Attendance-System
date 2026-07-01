# Implementation Plan - Face Recognition Attendance System
*Developed by Darshan M Bangre*

This plan details the implementation of a comprehensive Face Recognition Attendance System inside the `c:\Users\HP\OneDrive\Desktop\face_detection` folder. The system features a secure, JWT-authenticated Flask backend, support for both SQLite and MySQL databases, a flexible facial recognition engine, a premium glassmorphic Admin Panel, and mobile-friendly APIs.

---

## User Review Required

> [!IMPORTANT]
> **Mobile API Integration & Postman Testing**
> - The backend will support file uploads (multipart/form-data) or Base64 strings for mobile clients to easily submit face photos.
> - We will generate a **Postman Collection JSON** file (`postman_collection.json`) directly in the workspace so you can import it into Postman and test all authentication, employee, face, and attendance APIs immediately.

---

## Proposed Changes

We will create a structured Python Flask project in the workspace folder `c:\Users\HP\OneDrive\Desktop\face_detection`.

```
c:\Users\HP\OneDrive\Desktop\face_detection\
├── config.py                 # Configures database, upload folders, JWT secret, and mail
├── database.py               # Database abstraction layer (supports SQLite / MySQL)
├── face_engine.py            # Face detection and embedding generator (with OpenCV DNN fallback)
├── utils.py                  # Utility helper functions (JWT helper, mail sender, Excel/PDF exporter)
├── app.py                    # Main Flask API and Web server
├── requirements.txt          # Dependency list
├── .gitignore                # Git exclude list
├── README.md                 # Project guide, API details, and mobile integration instructions
├── postman_collection.json   # Exported Postman collection for direct import and testing
├── static/                   # Static assets for the frontend
│   ├── css/
│   │   └── style.css         # Dark-mode glassmorphic CSS styling
│   └── js/
│       └── app.js            # Frontend WebRTC camera, API clients, and UI routing
├── templates/
│   └── dashboard.html        # Single Page Admin Panel / Verification UI
└── uploads/                  # Storage for profiles and captured attendance photos
    ├── profiles/
    └── attendance/
```

### 1. Backend Core & Configuration

#### [NEW] [config.py](file:///c:/Users/HP/OneDrive/Desktop/face_detection/config.py)
- Configuration class reading environment variables via `python-dotenv`.
- Defines JWT expiration, database connection parameters, secure folders, and mail configuration.

#### [NEW] [database.py](file:///c:/Users/HP/OneDrive/Desktop/face_detection/database.py)
- Detects whether MySQL credentials are provided in the environment.
- Automatically falls back to local SQLite if MySQL is not available, allowing instant runtime.
- Creates `employees`, `face_embeddings`, and `attendance` tables automatically on startup.

#### [NEW] [face_engine.py](file:///c:/Users/HP/OneDrive/Desktop/face_detection/face_engine.py)
- Encapsulates face detection and embedding logic.
- Integrates a fallback model using a pre-trained ONNX face model or OpenCV Face Recognizer if the dlib-based `face_recognition` package is not found.
- Detects coordinates, computes facial embeddings, and compares embeddings using Cosine Similarity / Euclidean Distance.

#### [NEW] [utils.py](file:///c:/Users/HP/OneDrive/Desktop/face_detection/utils.py)
- Token-based JWT generation and validation helper.
- Excel/CSV exporter and PDF report generator using `reportlab`.
- Email notification helper for attendance updates.

#### [NEW] [app.py](file:///c:/Users/HP/OneDrive/Desktop/face_detection/app.py)
- Flask server exposing API endpoints under `/api`.
- Routes:
  - **Auth**: `/api/login`, `/api/logout`, `/api/refresh-token`
  - **Employee**: `GET/POST/PUT/DELETE /api/employee`
  - **Face**: `/api/enroll-face`, `/api/verify-face`, `/api/face-status`
  - **Attendance**: `/api/attendance/checkin`, `/api/attendance/checkout`, `/api/attendance/history`, `/api/attendance/today`
  - **Reports**: `/api/reports/daily`, `/api/reports/monthly`, `/api/reports/late`, `/api/reports/employee`

### 2. Frontend User Interface

#### [NEW] [style.css](file:///c:/Users/HP/OneDrive/Desktop/face_detection/static/css/style.css)
- Custom CSS utilizing HSL color palettes.
- Features: Sleek dark-mode grid, glassmorphic card containers (`backdrop-filter: blur()`), glowing status badges, smooth transitions, and animated dashboard widgets.

#### [NEW] [dashboard.html](file:///c:/Users/HP/OneDrive/Desktop/face_detection/templates/dashboard.html)
- Clean, semantic HTML5 structure with a sidebar for views (Overview Dashboard, Employee Manager, Face Enrollment, Attendance History, Reports Engine, Live Camera Verification Hub).

#### [NEW] [app.js](file:///c:/Users/HP/OneDrive/Desktop/face_detection/static/js/app.js)
- Manages routing between the dashboard panels dynamically without full page reloads.
- Controls browser camera capturing (single frames for verify, burst of frames for enroll).
- Renders attendance history charts, formats timestamps, and triggers downloads for CSV and PDF reports.

### 3. Project Configuration & Integrations

#### [NEW] [.gitignore](file:///c:/Users/HP/OneDrive/Desktop/face_detection/.gitignore)
- Git ignore rule file to ignore local environments, upload images, SQLite databases, and temporary caches.

#### [NEW] [README.md](file:///c:/Users/HP/OneDrive/Desktop/face_detection/README.md)
- Complete user manual describing features, API specifications, installation steps, database structure, and how to test.
- Includes a dedicated section on **Mobile Application Integration** outlining exactly how to capture an image on Android/iOS (Flutter, React Native, Native Kotlin/Swift) and send it via multipart POST request to the API.

#### [NEW] [postman_collection.json](file:///c:/Users/HP/OneDrive/Desktop/face_detection/postman_collection.json)
- Postman Collection (v2.1 format) detailing all endpoints, headers, test scripts for saving the JWT token, and JSON body templates for quick import and testing.

---

## Verification Plan

### Automated Tests
- Run `python -m unittest tests/test_api.py` (we will create a suite of mock unit tests to verify the authentication flow, employee creation, and attendance logs).

### Manual Verification
1. Start the Flask server by running `python app.py`.
2. Open the web browser to `http://localhost:5000`.
3. Log in with the default admin credentials (`admin` / `admin123`).
4. Navigate to the **Employee Management** page and create a test employee.
5. Navigate to the **Face Enrollment** page, grant webcam permission, select the employee, and record their face.
6. Open the **Live Verification Hub**, point the webcam to your face, and verify that the system successfully recognizes you, greets you with audio feed, and logs a check-in.
7. Import `postman_collection.json` into Postman, run requests against `http://127.0.0.1:5000/api/...`, verify JWT generation and route protection.
8. Verify that you can view and export daily/monthly attendance logs as PDF/CSV from the **Reports Engine**.
