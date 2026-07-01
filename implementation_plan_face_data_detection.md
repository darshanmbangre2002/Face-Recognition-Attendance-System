# Multi-Sample Dataset Capture & KNN Face Training Plan
*Developed by Darshan M Bangre*

This implementation plan outlines the steps to resolve the false positive face verification issue (where different faces are recognized as registered employees). We will implement a multi-sample dataset capture system that records employees in multiple camera angles, and train a K-Nearest Neighbors (KNN) classifier backend.

## User Review Required

> [!IMPORTANT]
> **Biometric Registration Update**: The Face Registration dashboard tab will be upgraded from capturing a single picture to guiding the user through capturing **5 distinct facial angles** (Straight, Left, Right, Up, Smile/Blink) sequentially.
> **Database Retention**: All existing face records will remain fully intact, but to achieve high-precision verification, we recommend enrolling new multi-angle profiles for existing employees.

## Proposed Changes

### Biometric Engine & Classifier

#### [MODIFY] [face_engine.py](file:///c:/Users/HP/OneDrive/Desktop/face_detection/face_engine.py)
* Refine the `match_face_in_database` method to use a **K-Nearest Neighbors (KNN) classification algorithm** (with $K=3$) instead of simple best-single-score lookup.
* Calculate distances of the query embedding to all registered dataset embeddings in the database.
* Return a valid match only if the closest neighbor matches the voted employee majority, and the confidence falls within strict threshold parameters.

---

### Dashboard Interface & Guidance Loop

#### [MODIFY] [static/js/app.js](file:///c:/Users/HP/OneDrive/Desktop/face_detection/static/js/app.js)
* Upgrade `triggerEnrollment()` to run a state-guided loop that captures **5 samples** sequentially:
  1. **Straight**: *"Please look directly at the camera."*
  2. **Left**: *"Turn your head slightly to the left."*
  3. **Right**: *"Turn your head slightly to the right."*
  4. **Up**: *"Tilt your head slightly upwards."*
  5. **Neutral/Smile**: *"Blink or smile gently for a final sample."*
* The UI progress bar will animate dynamically (0% ➡️ 20% ➡️ 40% ➡️ 60% ➡️ 80% ➡️ 100%) as each successful angle crop is validated and saved.
* Display custom notifications and speak guide prompts using Text-to-Speech (TTS).

#### [MODIFY] [templates/dashboard.html](file:///c:/Users/HP/OneDrive/Desktop/face_detection/templates/dashboard.html)
* Add a dedicated step guideline textbox (`#enroll-guide-prompt`) to output the active capture instructions dynamically to the employee.

---

### Verification and Unit Tests

#### [MODIFY] [tests/test_api.py](file:///c:/Users/HP/OneDrive/Desktop/face_detection/tests/test_api.py)
* Update unit tests to register multiple face samples for testing and verify the KNN classification matcher behavior.

## Verification Plan

### Automated Tests
* Run Python unit tests:
  `venv\Scripts\python.exe -m unittest tests/test_api.py`

### Manual Verification
* Navigate to the **Face Registration** tab.
* Enroll a new employee: Verify that the UI guides you step-by-step to capture 5 different angles, showing a progressing bar.
* Navigate to the **Live Verification Hub**:
  * Scan the enrolled employee's face (verify access is granted).
  * Scan an unregistered face (verify it is rejected as "Unregistered Employee" and does not trigger false matches).
