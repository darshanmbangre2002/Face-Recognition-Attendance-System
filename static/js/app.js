/* global Chart */

// -------------------------------------------------------------
// UI State & Global Variables
// -------------------------------------------------------------
let API_URL = window.location.origin;
let jwtToken = localStorage.getItem('auraface_token') || null;
let currentView = 'dashboard';
let employeesList = [];

// Camera Streams
let enrollStream = null;
let verifyStream = null;
let verifyIntervalId = null;

// Chart Instance
let attendanceChart = null;

// -------------------------------------------------------------
// Initialization
// -------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    // Check if token exists, show/hide login overlay
    checkAuth();
    
    // Setup Navigation Tabs
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const view = item.getAttribute('data-view');
            switchView(view);
        });
    });
    
    // Set default report date filters
    const today = new Date().toISOString().split('T')[0];
    const month = new Date().toISOString().slice(0, 7);
    document.getElementById('report-filter-date').value = today;
    document.getElementById('report-filter-month').value = month;
});

// -------------------------------------------------------------
// Authentication (Module 1)
// -------------------------------------------------------------
function checkAuth() {
    const loginOverlay = document.getElementById('login-overlay');
    if (jwtToken) {
        loginOverlay.style.display = 'none';
        // Decode simple base64 payload to retrieve details
        try {
            const payload = JSON.parse(atob(jwtToken.split('.')[1]));
            document.getElementById('user-display-name').textContent = payload.sub.toUpperCase();
            document.getElementById('user-display-role').textContent = payload.role === 'admin' ? 'Administrator' : 'HR User';
        } catch (e) {
            handleLogout();
        }
        // Load initial dashboard telemetry
        loadDashboardData();
    } else {
        loginOverlay.style.display = 'flex';
        stopAllCameras();
    }
}

async function handleLogin(event) {
    event.preventDefault();
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    
    try {
        const response = await fetch(`${API_URL}/api/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        
        const result = await response.json();
        if (result.success) {
            jwtToken = result.token;
            localStorage.setItem('auraface_token', jwtToken);
            showToast('Login successful. Welcome to AuraFace!', 'success');
            checkAuth();
        } else {
            showToast(result.message || 'Invalid username or password', 'error');
        }
    } catch (e) {
        showToast('Connection to authentication server failed.', 'error');
    }
}

async function handleLogout() {
    try {
        if (jwtToken) {
            await fetch(`${API_URL}/api/logout`, {
                method: 'POST',
                headers: { 
                    'Authorization': `Bearer ${jwtToken}`,
                    'Content-Type': 'application/json'
                }
            });
        }
    } catch (e) {
        console.error("Backend logout failed: ", e);
    }
    
    // Clear tokens
    localStorage.removeItem('auraface_token');
    jwtToken = null;
    
    // Reset sidebar profile summary info
    const nameEl = document.getElementById('user-display-name');
    const roleEl = document.getElementById('user-display-role');
    if (nameEl) nameEl.textContent = 'Administrator';
    if (roleEl) roleEl.textContent = 'System Admin';
    
    showToast('Logged out successfully.', 'success');
    
    // Reload page to clear all internal memory cache, employee tables, and telemetry charts
    setTimeout(() => {
        window.location.reload();
    }, 800);
}

// -------------------------------------------------------------
// Navigation Routing
// -------------------------------------------------------------
function switchView(viewName) {
    if (!jwtToken) return;
    
    // Stop cameras from previous tabs
    stopAllCameras();
    
    // Set active tab classes
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        if (item.getAttribute('data-view') === viewName) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
    
    // Show/Hide Panels
    const panels = document.querySelectorAll('.view-panel');
    panels.forEach(panel => {
        if (panel.id === `${viewName}-view`) {
            panel.classList.add('active');
        } else {
            panel.classList.remove('active');
        }
    });
    
    currentView = viewName;
    
    // View Titles
    const titleEl = document.getElementById('view-title');
    const subtitleEl = document.getElementById('view-subtitle');
    
    if (viewName === 'dashboard') {
        titleEl.textContent = 'Overview Dashboard';
        subtitleEl.textContent = 'Real-time attendance insights and telemetry';
        loadDashboardData();
    } else if (viewName === 'employees') {
        titleEl.textContent = 'Employees Directory';
        subtitleEl.textContent = 'Manage employee details and credentials';
        loadEmployeesData();
    } else if (viewName === 'enroll') {
        titleEl.textContent = 'Biometric Registration';
        subtitleEl.textContent = 'Register employee faces and build embeddings database';
        loadEnrollDropdown();
    } else if (viewName === 'verify') {
        titleEl.textContent = 'Live Verification Hub';
        subtitleEl.textContent = 'Scan faces to verify identity and record attendance';
        resetVerificationUI();
    } else if (viewName === 'reports') {
        titleEl.textContent = 'Reports & Audits';
        subtitleEl.textContent = 'Generate, query, and export logs in PDF/CSV format';
        loadReportsDropdown();
    }
}

// Helper headers
function getHeaders() {
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${jwtToken}`
    };
}

// -------------------------------------------------------------
// Toast Alerts
// -------------------------------------------------------------
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let icon = type === 'success' ? 'bx-check-circle' : 'bx-error-circle';
    toast.innerHTML = `<i class="bx ${icon}" style="font-size: 20px;"></i> <span>${message}</span>`;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(50px)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// -------------------------------------------------------------
// 1. Dashboard Tab Data Rendering
// -------------------------------------------------------------
async function loadDashboardData() {
    try {
        const headers = getHeaders();
        // Load Employees count
        const empRes = await fetch(`${API_URL}/api/employees`, { headers });
        const empResult = await empRes.json();
        
        // Load Today's Attendance
        const attRes = await fetch(`${API_URL}/api/attendance/today`, { headers });
        const attResult = await attRes.json();
        
        // Load all historical records for chart rendering
        const histRes = await fetch(`${API_URL}/api/attendance/history`, { headers });
        const histResult = await histRes.json();
        
        if (empResult.success && attResult.success && histResult.success) {
            const employees = empResult.employees;
            const records = attResult.records;
            
            employeesList = employees;
            
            // Calculate overview numbers
            const totalEmployees = employees.length;
            const checkedIn = records.length;
            
            // Calculate late arrivals (Status matches 'Late' or 'Half-Day')
            let lateCount = 0;
            records.forEach(r => {
                if (r.status === 'Late' || r.status === 'Half-Day') {
                    lateCount++;
                }
            });
            
            const absentCount = Math.max(0, totalEmployees - checkedIn);
            
            document.getElementById('stat-total-employees').textContent = totalEmployees;
            document.getElementById('stat-active-today').textContent = checkedIn;
            document.getElementById('stat-late-today').textContent = lateCount;
            document.getElementById('stat-absent-today').textContent = absentCount;
            
            // Update live feed panel
            renderDashboardLiveFeed(records);
            
            // Render Weekly Attendance Chart with database history records
            renderAttendanceChart(histResult.records || []);
        }
    } catch (e) {
        showToast('Failed to load dashboard statistics.', 'error');
    }
}

function renderDashboardLiveFeed(records) {
    const listEl = document.getElementById('dashboard-feed-list');
    listEl.innerHTML = '';
    
    if (records.length === 0) {
        listEl.innerHTML = `
            <div class="feed-item" style="border: none; justify-content: center; color: var(--text-muted); padding-top: 50px;">
                No transactions logged today.
            </div>`;
        return;
    }
    
    // Render top 5 recent check-ins
    records.slice(0, 5).forEach(rec => {
        const item = document.createElement('div');
        item.className = 'feed-item';
        
        // Initials avatar
        const initials = rec.employee_name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
        const confScore = rec.confidence_score ? `Match: ${(rec.confidence_score * 100).toFixed(0)}%` : 'Manual';
        
        item.innerHTML = `
            <div class="feed-avatar">${initials}</div>
            <div class="feed-details">
                <h5>${rec.employee_name}</h5>
                <p>${rec.department} | ${confScore}</p>
            </div>
            <div class="feed-time">
                <i class="bx bx-time" style="vertical-align: middle;"></i> ${rec.check_in.substring(0, 5)}
            </div>
        `;
        listEl.appendChild(item);
    });
}

async function renderAttendanceChart(historyRecords = []) {
    const canvas = document.getElementById('attendance-weekly-chart');
    if (!canvas) return;
    
    const labels = [];
    const checkInData = [];
    const lateData = [];
    
    // Generate dates for the last 5 days
    for (let i = 4; i >= 0; i--) {
        const d = new Date();
        d.setDate(d.getDate() - i);
        const dateStr = d.toISOString().split('T')[0]; // Format: YYYY-MM-DD
        
        labels.push(d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }));
        
        // Filter records belonging to this date
        const dayRecords = historyRecords.filter(r => r.attendance_date === dateStr);
        const dayCheckinsCount = dayRecords.length;
        // Count how many checkins were 'Late' or 'Half-Day'
        const dayLateCount = dayRecords.filter(r => r.status === 'Late' || r.status === 'Half-Day').length;
        
        checkInData.push(dayCheckinsCount);
        lateData.push(dayLateCount);
    }
    
    if (attendanceChart) {
        attendanceChart.destroy();
    }
    
    attendanceChart = new Chart(canvas, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'On-Time Checkins',
                    data: checkInData.map((v, idx) => v - lateData[idx]),
                    backgroundColor: 'rgba(99, 102, 241, 0.65)',
                    borderColor: '#6366f1',
                    borderWidth: 1,
                    borderRadius: 5
                },
                {
                    label: 'Late Checkins',
                    data: lateData,
                    backgroundColor: 'rgba(245, 158, 11, 0.65)',
                    borderColor: '#f59e0b',
                    borderWidth: 1,
                    borderRadius: 5
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: { color: '#94a3b8', font: { family: 'Inter', size: 11 } }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255,255,255,0.03)' },
                    ticks: { color: '#94a3b8' }
                },
                y: {
                    grid: { color: 'rgba(255,255,255,0.03)' },
                    ticks: { color: '#94a3b8', stepSize: 1 }
                }
            }
        }
    });
}

// -------------------------------------------------------------
// 2. Employees Tab (Module 2)
// -------------------------------------------------------------
async function loadEmployeesData() {
    try {
        const response = await fetch(`${API_URL}/api/employees`, {
            headers: getHeaders()
        });
        const result = await response.json();
        
        if (result.success) {
            employeesList = result.employees;
            renderEmployeesTable(employeesList);
        }
    } catch (e) {
        showToast('Failed to load employee list.', 'error');
    }
}

async function renderEmployeesTable(list) {
    const tbody = document.getElementById('employee-table-body');
    tbody.innerHTML = '';
    
    if (list.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" style="text-align: center; color: var(--text-muted); padding: 40px 0;">
                    No employees found matching the search context.
                </td>
            </tr>`;
        return;
    }
    
    for (const emp of list) {
        const tr = document.createElement('tr');
        
        // Fetch biometric status for this employee
        let faceStatusBadge = `<span class="badge warning"><i class="bx bx-error-circle"></i> Unregistered</span>`;
        try {
            const statusRes = await fetch(`${API_URL}/api/face-status?employee_id=${emp.employee_id}`, {
                headers: getHeaders()
            });
            const statusResult = await statusRes.json();
            if (statusResult.success && statusResult.enrolled) {
                faceStatusBadge = `<span class="badge success"><i class="bx bx-check-shield"></i> Enrolled (${statusResult.enrollment_count})</span>`;
            }
        } catch (e) {}
        
        const statusText = emp.status === 1 ? 'Active' : 'Suspended';
        const statusBadge = emp.status === 1 ? 'success' : 'danger';
        
        tr.innerHTML = `
            <td>${emp.employee_id}</td>
            <td style="font-weight: 600; color: #fff;">${emp.employee_name}</td>
            <td>${emp.department || '-'}</td>
            <td>${emp.designation || '-'}</td>
            <td>${emp.email || '-'}</td>
            <td>${emp.mobile || '-'}</td>
            <td><span class="badge ${statusBadge}">${statusText}</span></td>
            <td>
                <div class="action-btn-group">
                    <button class="action-btn" title="Edit Profile" onclick="openEmployeeModal(${emp.employee_id})">
                        <i class="bx bx-edit-alt"></i>
                    </button>
                    <button class="action-btn" title="Biometric Status" onclick="enrollFaceForEmployee(${emp.employee_id})">
                        <i class="bx bx-scan"></i>
                    </button>
                    <button class="action-btn delete-btn" title="Delete Profile" onclick="deleteEmployee(${emp.employee_id})">
                        <i class="bx bx-trash"></i>
                    </button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    }
}

function filterEmployees() {
    const q = document.getElementById('employee-search').value.toLowerCase();
    const filtered = employeesList.filter(emp => {
        return emp.employee_name.toLowerCase().includes(q) ||
               (emp.department && emp.department.toLowerCase().includes(q)) ||
               (emp.designation && emp.designation.toLowerCase().includes(q)) ||
               (emp.email && emp.email.toLowerCase().includes(q)) ||
               (emp.mobile && emp.mobile.includes(q)) ||
               emp.employee_id.toString().includes(q);
    });
    // Fast render
    const tbody = document.getElementById('employee-table-body');
    tbody.innerHTML = '';
    filtered.forEach(emp => {
        // Fast template injection without nested async status badge loops for latency
        const statusText = emp.status === 1 ? 'Active' : 'Suspended';
        const statusBadge = emp.status === 1 ? 'success' : 'danger';
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${emp.employee_id}</td>
            <td style="font-weight: 600; color: #fff;">${emp.employee_name}</td>
            <td>${emp.department || '-'}</td>
            <td>${emp.designation || '-'}</td>
            <td>${emp.email || '-'}</td>
            <td>${emp.mobile || '-'}</td>
            <td><span class="badge ${statusBadge}">${statusText}</span></td>
            <td>
                <div class="action-btn-group">
                    <button class="action-btn" title="Edit Profile" onclick="openEmployeeModal(${emp.employee_id})">
                        <i class="bx bx-edit-alt"></i>
                    </button>
                    <button class="action-btn" title="Biometric Status" onclick="enrollFaceForEmployee(${emp.employee_id})">
                        <i class="bx bx-scan"></i>
                    </button>
                    <button class="action-btn delete-btn" title="Delete Profile" onclick="deleteEmployee(${emp.employee_id})">
                        <i class="bx bx-trash"></i>
                    </button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function openEmployeeModal(empId = null) {
    const backdrop = document.getElementById('employee-modal');
    const title = document.getElementById('employee-modal-title');
    const form = document.getElementById('employee-form');
    const btn = document.getElementById('btn-save-employee');
    
    form.reset();
    document.getElementById('modal-employee-id').value = '';
    
    if (empId) {
        title.textContent = 'Edit Employee Profile';
        btn.textContent = 'Save Changes';
        const emp = employeesList.find(e => e.employee_id === empId);
        if (emp) {
            document.getElementById('modal-employee-id').value = emp.employee_id;
            document.getElementById('modal-employee-name').value = emp.employee_name;
            document.getElementById('modal-department').value = emp.department || '';
            document.getElementById('modal-designation').value = emp.designation || '';
            document.getElementById('modal-email').value = emp.email || '';
            document.getElementById('modal-mobile').value = emp.mobile || '';
            document.getElementById('modal-status').value = emp.status;
        }
    } else {
        title.textContent = 'Register New Employee';
        btn.textContent = 'Create Record';
    }
    
    backdrop.classList.add('active');
}

function closeEmployeeModal() {
    document.getElementById('employee-modal').classList.remove('active');
}

async function saveEmployee(event) {
    event.preventDefault();
    const id = document.getElementById('modal-employee-id').value;
    const name = document.getElementById('modal-employee-name').value.trim();
    const dept = document.getElementById('modal-department').value.trim();
    const desg = document.getElementById('modal-designation').value.trim();
    const email = document.getElementById('modal-email').value.trim();
    const mobile = document.getElementById('modal-mobile').value.trim();
    const status = parseInt(document.getElementById('modal-status').value);
    
    const payload = {
        employee_name: name,
        department: dept,
        designation: desg,
        email: email,
        mobile: mobile,
        status: status
    };
    
    let url = `${API_URL}/api/employee`;
    let method = 'POST';
    
    if (id) {
        payload.employee_id = parseInt(id);
        method = 'PUT';
    }
    
    try {
        const response = await fetch(url, {
            method: method,
            headers: getHeaders(),
            body: JSON.stringify(payload)
        });
        
        const result = await response.json();
        if (result.success) {
            showToast(result.message || 'Profile saved successfully.', 'success');
            closeEmployeeModal();
            loadEmployeesData();
        } else {
            showToast(result.message || 'Error occurred while saving profile.', 'error');
        }
    } catch (e) {
        showToast('Network error while saving profile.', 'error');
    }
}

async function deleteEmployee(empId) {
    if (!confirm('Are you absolutely sure you want to delete this employee? This will permanently wipe all metadata, attendance files, and registered face embeddings!')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/api/employee?employee_id=${empId}`, {
            method: 'DELETE',
            headers: getHeaders()
        });
        const result = await response.json();
        if (result.success) {
            showToast(result.message || 'Profile deleted successfully.', 'success');
            loadEmployeesData();
        } else {
            showToast(result.message || 'Error deleting employee.', 'error');
        }
    } catch (e) {
        showToast('Network error while deleting employee.', 'error');
    }
}

function enrollFaceForEmployee(empId) {
    switchView('enroll');
    document.getElementById('enroll-employee-select').value = empId;
    updateEnrollmentStatus();
}

// -------------------------------------------------------------
// 3. Face Enrollment Tab (Module 3)
// -------------------------------------------------------------
async function loadEnrollDropdown() {
    const select = document.getElementById('enroll-employee-select');
    select.innerHTML = '<option value="">-- Choose Employee --</option>';
    
    try {
        const response = await fetch(`${API_URL}/api/employees`, {
            headers: getHeaders()
        });
        const result = await response.json();
        if (result.success) {
            result.employees.forEach(emp => {
                const opt = document.createElement('option');
                opt.value = emp.employee_id;
                opt.textContent = `${emp.employee_name} (ID: ${emp.employee_id})`;
                select.appendChild(opt);
            });
        }
    } catch (e) {
        showToast('Failed to load employee list for enrollment dropdown.', 'error');
    }
}

async function updateEnrollmentStatus() {
    const empId = document.getElementById('enroll-employee-select').value;
    const textBox = document.getElementById('enrollment-status-text');
    const capBtn = document.getElementById('btn-enroll-capture');
    
    if (!empId) {
        textBox.textContent = 'Select an employee to verify their registration.';
        capBtn.disabled = true;
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/api/face-status?employee_id=${empId}`, {
            headers: getHeaders()
        });
        const result = await response.json();
        if (result.success) {
            if (result.enrolled) {
                textBox.innerHTML = `<span style="color: var(--success); font-weight: 600;">ENROLLED</span>: ${result.enrollment_count} face sample(s) registered. You can add more samples for better accuracy.`;
            } else {
                textBox.innerHTML = `<span style="color: var(--warning); font-weight: 600;">UNREGISTERED</span>: No face profiles enrolled yet.`;
            }
            // Allow capture if camera stream is active
            if (enrollStream) {
                capBtn.disabled = false;
            }
        }
    } catch (e) {
        textBox.textContent = 'Connection error checking credentials status.';
    }
}

function getCameraErrorMessage(e) {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        return 'Camera access requires a secure connection (HTTPS) or localhost. Please check your browser address bar URL.';
    }
    if (e) {
        if (e.name === 'NotAllowedError' || e.name === 'PermissionDeniedError') {
            return 'Camera permission denied. Please click the site/lock icon in your address bar and set Camera to Allow.';
        }
        if (e.name === 'NotFoundError' || e.name === 'DevicesNotFoundError') {
            return 'No camera hardware detected. Please connect a webcam and verify device manager recognition.';
        }
        if (e.name === 'NotReadableError' || e.name === 'TrackStartError') {
            return 'Camera is already in use by another browser tab or meeting application.';
        }
        if (e.name === 'OverconstrainedError') {
            return 'The requested camera resolution is not supported by your hardware device.';
        }
    }
    return 'Unable to access web camera. Grant permissions and verify device connections.';
}

async function toggleEnrollCamera() {
    const video = document.getElementById('enroll-video');
    const btn = document.getElementById('btn-enroll-camera-toggle');
    const capBtn = document.getElementById('btn-enroll-capture');
    const empSelect = document.getElementById('enroll-employee-select');
    
    if (enrollStream) {
        stopAllCameras();
        btn.innerHTML = '<i class="bx bx-video"></i> Start Camera';
        capBtn.disabled = true;
    } else {
        try {
            enrollStream = await navigator.mediaDevices.getUserMedia({
                video: { width: 640, height: 480, facingMode: 'user' }
            });
            video.srcObject = enrollStream;
            btn.innerHTML = '<i class="bx bx-video-off"></i> Stop Camera';
            btn.style.background = 'rgba(239, 68, 68, 0.1)';
            btn.style.borderColor = 'rgba(239, 68, 68, 0.2)';
            btn.style.color = 'var(--danger)';
            
            if (empSelect.value) {
                capBtn.disabled = false;
            }
        } catch (e) {
            showToast(getCameraErrorMessage(e), 'error');
        }
    }
}

async function triggerEnrollment() {
    const empId = document.getElementById('enroll-employee-select').value;
    if (!empId) {
        showToast('Please select an employee before capturing!', 'warning');
        return;
    }
    
    const capBtn = document.getElementById('btn-enroll-capture');
    const empSelect = document.getElementById('enroll-employee-select');
    const camToggleBtn = document.getElementById('btn-enroll-camera-toggle');
    
    // Disable controls during active capture session
    capBtn.disabled = true;
    empSelect.disabled = true;
    camToggleBtn.disabled = true;
    
    const video = document.getElementById('enroll-video');
    const progressBar = document.getElementById('enroll-progress-bar');
    const promptEl = document.getElementById('enroll-guide-prompt');
    const panel = document.getElementById('enroll-camera-panel');
    
    const steps = [
        { text: "Pose 1/5: Please look straight ahead at the camera.", voice: "Please look straight ahead." },
        { text: "Pose 2/5: Turn your head slightly to the left.", voice: "Now, turn your head slightly to the left." },
        { text: "Pose 3/5: Turn your head slightly to the right.", voice: "Turn your head slightly to the right." },
        { text: "Pose 4/5: Tilt your head slightly upwards.", voice: "Tilt your head slightly upwards." },
        { text: "Pose 5/5: Smile or blink gently for the final capture.", voice: "Smile or blink for the final capture." }
    ];
    
    progressBar.style.width = '0%';
    promptEl.style.color = 'var(--accent)';
    
    let stepIndex = 0;
    while (stepIndex < steps.length) {
        const step = steps[stepIndex];
        
        // Show step instruction
        promptEl.textContent = step.text;
        speak(step.voice);
        showToast(step.text, 'info');
        
        // Delay to allow face positioning adjustment
        await new Promise(resolve => setTimeout(resolve, 2200));
        
        // Check if stream was closed during delay
        if (!enrollStream) {
            promptEl.textContent = "Enrollment aborted. Camera was stopped.";
            promptEl.style.color = "var(--danger)";
            progressBar.style.width = '0%';
            empSelect.disabled = false;
            camToggleBtn.disabled = false;
            return;
        }
        
        // Capture frame from video feed
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
        const ctx = canvas.getContext('2d');
        ctx.translate(canvas.width, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        const base64Image = canvas.toDataURL('image/jpeg', 0.9);
        
        // Flash visual shutter effect
        panel.classList.add('scanning');
        setTimeout(() => panel.classList.remove('scanning'), 300);
        
        promptEl.textContent = "Analyzing facial signature...";
        
        try {
            const response = await fetch(`${API_URL}/api/enroll-face`, {
                method: 'POST',
                headers: getHeaders(),
                body: JSON.stringify({
                    employee_id: parseInt(empId),
                    image: base64Image
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                stepIndex++;
                progressBar.style.width = `${stepIndex * 20}%`;
                showToast(`Pose ${stepIndex}/5 registered successfully!`, 'success');
            } else {
                speak("Face not detected. Please adjust position.");
                showToast(result.message || "Failed to capture face. Retrying...", "error");
                promptEl.textContent = `Retrying Pose ${stepIndex + 1}/5. Keep face centered.`;
                await new Promise(resolve => setTimeout(resolve, 1500));
            }
        } catch (e) {
            showToast("Network error uploading frame. Retrying...", "error");
            await new Promise(resolve => setTimeout(resolve, 2000));
        }
    }
    
    // Complete registration
    speak("Face registration successfully completed!");
    promptEl.textContent = "All 5 angles successfully trained!";
    promptEl.style.color = "var(--success)";
    showToast("All 5 facial dataset samples successfully enrolled and trained!", "success");
    
    // Enable controls
    capBtn.disabled = false;
    empSelect.disabled = false;
    camToggleBtn.disabled = false;
    updateEnrollmentStatus();
}

// -------------------------------------------------------------
// 4. Live Verification Tab (Module 4 & 5)
// -------------------------------------------------------------
function resetVerificationUI() {
    const card = document.getElementById('verify-status-card');
    card.className = 'glass-card verification-status-panel';
    
    document.querySelector('.verify-badge-icon').innerHTML = '<i class="bx bx-aperture"></i>';
    document.getElementById('verify-header').textContent = 'Verification Standby';
    document.getElementById('verify-description').textContent = 'Click "Start Verification" to initiate live scanning. Position your face in front of the camera.';
    document.getElementById('verify-details-table').style.display = 'none';
}

async function toggleVerifyCamera() {
    const video = document.getElementById('verify-video');
    const btn = document.getElementById('btn-verify-camera-toggle');
    const statusBadge = document.getElementById('verification-camera-status');
    const card = document.getElementById('verify-status-card');
    
    if (verifyStream) {
        stopAllCameras();
        btn.innerHTML = '<i class="bx bx-video"></i> Start Verification';
        statusBadge.textContent = 'Offline';
        statusBadge.className = 'badge danger';
        resetVerificationUI();
    } else {
        try {
            verifyStream = await navigator.mediaDevices.getUserMedia({
                video: { width: 640, height: 480, facingMode: 'user' }
            });
            video.srcObject = verifyStream;
            btn.innerHTML = '<i class="bx bx-video-off"></i> Stop Verification';
            btn.style.background = 'rgba(239, 68, 68, 0.1)';
            btn.style.borderColor = 'rgba(239, 68, 68, 0.2)';
            btn.style.color = 'var(--danger)';
            statusBadge.textContent = 'Active Scanning';
            statusBadge.className = 'badge success';
            
            card.classList.add('scanning');
            document.getElementById('verify-header').textContent = 'Scanning Face...';
            document.getElementById('verify-description').textContent = 'Live camera matches facial signatures against database files.';
            
            // Start verification capture loop using setTimeout instead of setInterval to avoid overlapping ticks
            verifyIntervalId = setTimeout(triggerVerificationCheck, 2500);
        } catch (e) {
            showToast(getCameraErrorMessage(e), 'error');
        }
    }
}

async function triggerVerificationCheck() {
    // Lock: If verification was stopped or is already processing a match, exit immediately
    if (!verifyStream || !verifyIntervalId) return;
    
    const video = document.getElementById('verify-video');
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    
    // Draw mirrored frame
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    const base64Image = canvas.toDataURL('image/jpeg', 0.85);
    
    try {
        const response = await fetch(`${API_URL}/api/verify-face`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: base64Image })
        });
        
        const result = await response.json();
        
        // Double-check lock in case stream was closed while request was in-flight
        if (!verifyStream || !verifyIntervalId) return;
        
        // Match found!
        if (result.success && result.employee) {
            // Lock immediately to prevent any concurrent checks
            const currentTimer = verifyIntervalId;
            verifyIntervalId = null;
            clearTimeout(currentTimer);
            clearInterval(currentTimer);
            
            const emp = result.employee;
            const confidence = result.confidence_score;
            
            // Visual feedback
            const card = document.getElementById('verify-status-card');
            card.className = 'glass-card verification-status-panel success';
            document.querySelector('.verify-badge-icon').innerHTML = '<i class="bx bx-check-shield"></i>';
            document.getElementById('verify-header').textContent = 'Access Granted!';
            document.getElementById('verify-description').textContent = `Matched employee profile: ${emp.employee_name}`;
            
            // Populate table details
            document.getElementById('verify-details-table').style.display = 'block';
            document.getElementById('verify-emp-name').textContent = emp.employee_name;
            document.getElementById('verify-emp-dept').textContent = emp.department || '-';
            document.getElementById('verify-emp-desg').textContent = emp.designation || '-';
            document.getElementById('verify-emp-confidence').textContent = `${(confidence * 100).toFixed(1)}%`;
            document.getElementById('verify-emp-time').textContent = new Date().toLocaleTimeString();
            
            // Voice response - WOW effect!
            speak(`Welcome, ${emp.employee_name}`);
            
            // Log Attendance if Auto Check-In enabled
            const autoAtt = document.getElementById('verify-auto-attendance').checked;
            let attendanceLogged = false;
            if (autoAtt) {
                attendanceLogged = await logAttendance(emp.employee_id, confidence, base64Image);
            } else {
                showToast(`Face recognized: ${emp.employee_name}`, 'success');
                attendanceLogged = true;
            }
            
            // Shut down the camera stream automatically on match to avoid multiple triggers
            stopAllCameras();
            
            // Reset Verification camera controls in the UI
            const toggleBtn = document.getElementById('btn-verify-camera-toggle');
            const verifyStatus = document.getElementById('verification-camera-status');
            if (toggleBtn) {
                toggleBtn.innerHTML = '<i class="bx bx-video"></i> Start Verification';
                toggleBtn.style.background = '';
                toggleBtn.style.borderColor = '';
                toggleBtn.style.color = '';
                
                // Enforce a strict 5-second delay before the user can turn the camera back on
                toggleBtn.disabled = true;
                setTimeout(() => {
                    toggleBtn.disabled = false;
                }, 5000);
            }
            if (verifyStatus) {
                verifyStatus.textContent = 'Offline';
                verifyStatus.className = 'badge danger';
            }
            
            if (attendanceLogged) {
                // Display success detail state
                document.getElementById('verify-header').textContent = 'Verification Completed';
                document.getElementById('verify-description').textContent = 'Attendance registered successfully. Camera closed.';
                
                // Voice and Popup alert!
                speak("Attendance captured successfully!");
                showToast("Attendance captured successfully!", "success");
                
                // Show custom premium popup
                setTimeout(() => {
                    showCustomAlert(`Attendance captured successfully for ${emp.employee_name}!`, 'success');
                }, 100);
            } else {
                // Duplicate check-in / duplicate warning details
                const card = document.getElementById('verify-status-card');
                card.className = 'glass-card verification-status-panel error';
                document.querySelector('.verify-badge-icon').innerHTML = '<i class="bx bx-error-circle"></i>';
                
                document.getElementById('verify-header').textContent = 'Already Marked';
                document.getElementById('verify-description').textContent = `Attendance already registered for ${emp.employee_name} today. Camera closed.`;
            }
            
        } else {
            // No face / unrecognized face
            const card = document.getElementById('verify-status-card');
            const header = document.getElementById('verify-header');
            const desc = document.getElementById('verify-description');
            
            if (result.message && result.message.includes('No face')) {
                card.className = 'glass-card verification-status-panel scanning';
                document.querySelector('.verify-badge-icon').innerHTML = '<i class="bx bx-aperture"></i>';
                header.textContent = 'Scanning Face...';
                desc.textContent = 'Please look directly into the camera lens.';
                
                // Continue scanning loop immediately
                verifyIntervalId = setTimeout(triggerVerificationCheck, 2500);
            } else {
                // Unrecognized/unregistered face! Show Access Denied.
                // Stop scanning loop temporarily so they can see the error
                const currentTimer = verifyIntervalId;
                verifyIntervalId = null;
                clearTimeout(currentTimer);
                clearInterval(currentTimer);
                
                card.className = 'glass-card verification-status-panel error';
                document.querySelector('.verify-badge-icon').innerHTML = '<i class="bx bx-user-x"></i>';
                header.textContent = 'Unregistered Employee';
                desc.textContent = 'Access Denied. Face signature not found in the database. Attendance not marked.';
                document.getElementById('verify-details-table').style.display = 'none';
                
                // Voice notification
                speak('Access Denied. Unregistered employee.');
                showToast('Verification failed: Unregistered employee.', 'error');
                
                // Resume scanning after 3.5 seconds
                setTimeout(() => {
                    if (verifyStream) {
                        resetVerificationUI();
                        card.classList.add('scanning');
                        verifyIntervalId = setTimeout(triggerVerificationCheck, 2500);
                    }
                }, 3500);
            }
        }
    } catch (e) {
        console.error("Verification loop request failure: ", e);
        // Retry loop in case of transient network errors
        if (verifyStream && verifyIntervalId) {
            verifyIntervalId = setTimeout(triggerVerificationCheck, 3000);
        }
    }
}

async function logAttendance(empId, confidence, imageBase64) {
    // Only check in once. Prevent duplicate calls.
    try {
        const headers = getHeaders();
        const historyRes = await fetch(`${API_URL}/api/attendance/history?employee_id=${empId}`, { headers });
        const historyData = await historyRes.json();
        
        const todayStr = new Date().toISOString().split('T')[0];
        let hasCheckedInToday = false;
        
        if (historyData.success && historyData.records) {
            hasCheckedInToday = historyData.records.some(r => r.attendance_date === todayStr);
        }
        
        if (hasCheckedInToday) {
            showToast('Attendance already marked for today.', 'warning');
            speak('Attendance already marked for today.');
            return false;
        }
        
        let endpoint = '/api/attendance/checkin';
        let payload = {
            employee_id: empId,
            confidence_score: confidence,
            latitude: null,
            longitude: null,
            device_id: 'WebPortal',
            image: imageBase64
        };
        
        // Wrap request in a Promise to await geo location if needed
        const success = await new Promise((resolve) => {
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(async (pos) => {
                    payload.latitude = pos.coords.latitude;
                    payload.longitude = pos.coords.longitude;
                    const ok = await sendAttendanceRequest(endpoint, payload);
                    resolve(ok);
                }, async () => {
                    const ok = await sendAttendanceRequest(endpoint, payload);
                    resolve(ok);
                });
            } else {
                sendAttendanceRequest(endpoint, payload).then(ok => resolve(ok));
            }
        });
        
        return success;
        
    } catch (e) {
        showToast('Error negotiating attendance validation state.', 'error');
        return false;
    }
}

async function sendAttendanceRequest(endpoint, payload) {
    try {
        const response = await fetch(`${API_URL}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        const result = await response.json();
        if (result.success) {
            showToast(result.message, 'success');
            return true;
        } else {
            showToast(result.message || 'Failed to log attendance transaction.', 'error');
            return false;
        }
    } catch (e) {
        showToast('Network error recording attendance.', 'error');
        return false;
    }
}

// -------------------------------------------------------------
// Voice Assist (Web Speech API)
// -------------------------------------------------------------
function speak(phrase) {
    if ('speechSynthesis' in window) {
        const utterance = new SpeechSynthesisUtterance(phrase);
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        window.speechSynthesis.speak(utterance);
    }
}

// Helper to shut down camera captures cleanly
function stopAllCameras() {
    if (enrollStream) {
        enrollStream.getTracks().forEach(track => track.stop());
        enrollStream = null;
    }
    if (verifyStream) {
        verifyStream.getTracks().forEach(track => track.stop());
        verifyStream = null;
    }
    if (verifyIntervalId) {
        clearTimeout(verifyIntervalId);
        clearInterval(verifyIntervalId);
        verifyIntervalId = null;
    }
}

// -------------------------------------------------------------
// 5. Reports Center Tab (Module 6)
// -------------------------------------------------------------
function loadReportsDropdown() {
    const select = document.getElementById('report-filter-employee');
    select.innerHTML = '<option value="">-- All Employees --</option>';
    
    employeesList.forEach(emp => {
        const opt = document.createElement('option');
        opt.value = emp.employee_id;
        opt.textContent = `${emp.employee_name} (ID: ${emp.employee_id})`;
        select.appendChild(opt);
    });
}

function toggleReportFilters() {
    const type = document.getElementById('report-filter-type').value;
    const dateGroup = document.getElementById('filter-date-group');
    const monthGroup = document.getElementById('filter-month-group');
    const empGroup = document.getElementById('filter-employee-group');
    
    dateGroup.style.display = 'none';
    monthGroup.style.display = 'none';
    empGroup.style.display = 'none';
    
    if (type === 'daily') {
        dateGroup.style.display = 'block';
    } else if (type === 'monthly') {
        monthGroup.style.display = 'block';
    } else if (type === 'late') {
        dateGroup.style.display = 'block'; // Range dates can be optional, standard date works
    } else if (type === 'employee') {
        empGroup.style.display = 'block';
    }
}

async function queryReports() {
    const type = document.getElementById('report-filter-type').value;
    const dateVal = document.getElementById('report-filter-date').value;
    const monthVal = document.getElementById('report-filter-month').value;
    const empId = document.getElementById('report-filter-employee').value;
    
    let url = '';
    const headers = getHeaders();
    
    if (type === 'daily') {
        url = `${API_URL}/api/reports/daily?date=${dateVal}`;
    } else if (type === 'monthly') {
        url = `${API_URL}/api/reports/monthly?month=${monthVal}`;
    } else if (type === 'late') {
        url = `${API_URL}/api/reports/late?start_date=${dateVal}&end_date=${dateVal}`;
    } else if (type === 'employee') {
        if (!empId) {
            showToast('Please select a specific employee for this report query.', 'warning');
            return;
        }
        url = `${API_URL}/api/reports/employee?employee_id=${empId}`;
    }
    
    try {
        const tbody = document.getElementById('report-table-body');
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 40px 0;"><i class="bx bx-loader-alt bx-spin" style="font-size: 20px;"></i> Querying database...</td></tr>`;
        
        const response = await fetch(url, { headers });
        const result = await response.json();
        
        if (result.success) {
            renderReportsTable(result.records);
        } else {
            showToast(result.message || 'Report retrieval failed.', 'error');
        }
    } catch (e) {
        showToast('Network error querying database reports.', 'error');
    }
}

function renderReportsTable(records) {
    const tbody = document.getElementById('report-table-body');
    tbody.innerHTML = '';
    
    if (!records || records.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 40px 0;">No attendance records matching the selected parameters.</td></tr>`;
        return;
    }
    
    records.forEach(rec => {
        const tr = document.createElement('tr');
        const confidence = rec.confidence_score ? `${(rec.confidence_score * 100).toFixed(0)}%` : 'Manual';
        
        let imgTag = '<span style="color: var(--text-muted);">None</span>';
        if (rec.image_path) {
            imgTag = `<a href="${API_URL}/${rec.image_path.replace(/\\/g, '/')}" target="_blank" style="color: var(--accent); font-weight: 500;"><i class="bx bx-image" style="vertical-align: middle;"></i> View</a>`;
        }
        
        const status = rec.status || 'Present';
        let statusBadge = '';
        if (status === 'Present') {
            statusBadge = `<span class="badge success">Present</span>`;
        } else if (status === 'Late') {
            statusBadge = `<span class="badge warning">Late</span>`;
        } else {
            statusBadge = `<span class="badge danger">Half-Day</span>`;
        }
        
        tr.innerHTML = `
            <td>${rec.attendance_date}</td>
            <td>${rec.employee_id}</td>
            <td style="font-weight: 600; color: #fff;">${rec.employee_name}</td>
            <td>${rec.department || '-'}</td>
            <td style="color: var(--success); font-weight: 500;">${rec.check_in}</td>
            <td>${statusBadge}</td>
            <td>${confidence}</td>
            <td>${rec.device_id || '-'}</td>
            <td>${imgTag}</td>
        `;
        tbody.appendChild(tr);
    });
}

function exportReport(exportType) {
    const type = document.getElementById('report-filter-type').value;
    const dateVal = document.getElementById('report-filter-date').value;
    const monthVal = document.getElementById('report-filter-month').value;
    const empId = document.getElementById('report-filter-employee').value;
    
    let path = '';
    let params = `export=${exportType}&token=${jwtToken}`;
    
    if (type === 'daily') {
        path = '/api/reports/daily';
        params += `&date=${dateVal}`;
    } else if (type === 'monthly') {
        path = '/api/reports/monthly';
        params += `&month=${monthVal}`;
    } else if (type === 'late') {
        path = '/api/reports/late';
        params += `&start_date=${dateVal}&end_date=${dateVal}`;
    } else if (type === 'employee') {
        if (!empId) {
            showToast('Please select a specific employee for this report export.', 'warning');
            return;
        }
        path = '/api/reports/employee';
        params += `&employee_id=${empId}`;
    }
    
    // Redirect to download via token parameter inside requests URL query
    window.open(`${API_URL}${path}?${params}`, '_blank');
}

// -------------------------------------------------------------
// PREMIUM CUSTOM ALERT FUNCTIONS
// -------------------------------------------------------------
window.showCustomAlert = function(message, type = 'info', title = null) {
    const modal = document.getElementById('custom-alert-modal');
    if (!modal) return;
    
    const content = modal.querySelector('.alert-modal-content');
    const iconContainer = document.getElementById('alert-modal-icon-container');
    const titleEl = document.getElementById('alert-modal-title');
    const messageEl = document.getElementById('alert-modal-message');
    
    // Set icon & colors based on type
    let iconHTML = '';
    let defaultTitle = 'Notification';
    if (type === 'success') {
        iconHTML = '<i class="bx bx-check-circle" style="color: #10b981; filter: drop-shadow(0 0 10px rgba(16,185,129,0.3));"></i>';
        defaultTitle = 'Success';
    } else if (type === 'error') {
        iconHTML = '<i class="bx bx-error" style="color: #ef4444; filter: drop-shadow(0 0 10px rgba(239,68,68,0.3));"></i>';
        defaultTitle = 'Error';
    } else if (type === 'warning') {
        iconHTML = '<i class="bx bx-info-circle" style="color: #f59e0b; filter: drop-shadow(0 0 10px rgba(245,158,11,0.3));"></i>';
        defaultTitle = 'Warning';
    } else {
        iconHTML = '<i class="bx bx-bell" style="color: #6366f1; filter: drop-shadow(0 0 10px rgba(99,102,241,0.3));"></i>';
        defaultTitle = 'Information';
    }
    
    if (iconContainer) iconContainer.innerHTML = iconHTML;
    if (titleEl) titleEl.textContent = title || defaultTitle;
    if (messageEl) messageEl.textContent = message;
    
    modal.style.display = 'flex';
    setTimeout(() => {
        if (content) content.style.transform = 'scale(1)';
    }, 10);
};

window.closeCustomAlert = function() {
    const modal = document.getElementById('custom-alert-modal');
    if (!modal) return;
    
    const content = modal.querySelector('.alert-modal-content');
    if (content) content.style.transform = 'scale(0.9)';
    setTimeout(() => {
        modal.style.display = 'none';
    }, 150);
};
