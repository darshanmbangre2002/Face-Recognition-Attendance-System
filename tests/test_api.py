import os
import unittest
import json
import sqlite3
from app import app
from config import Config
from database import Database

class TestAttendanceAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configure testing environments
        Config.SQLITE_PATH = 'test_attendance.db'
        Config.DB_TYPE = 'sqlite'
        Config.DB_HOST = None
        
        # Initialize test database
        Database.initialize_db()
        
        # Enable Flask Testing mode
        app.config['TESTING'] = True
        cls.client = app.test_client()
        cls.token = None

    @classmethod
    def tearDownClass(cls):
        # Delete test database and logs
        if os.path.exists('test_attendance.db'):
            try:
                os.remove('test_attendance.db')
            except OSError:
                pass

    def test_01_login_admin(self):
        """Test admin login and token generation."""
        payload = {
            'username': 'admin',
            'password': 'admin123'
        }
        response = self.client.post('/api/login', 
                                   data=json.dumps(payload),
                                   content_type='application/json')
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertIn('token', data)
        
        # Save token for subsequent tests
        self.__class__.token = data['token']

    def test_02_login_invalid(self):
        """Test admin login with wrong password."""
        payload = {
            'username': 'admin',
            'password': 'wrongpassword'
        }
        response = self.client.post('/api/login', 
                                   data=json.dumps(payload),
                                   content_type='application/json')
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 401)
        self.assertFalse(data['success'])

    def test_03_create_employee(self):
        """Test employee profile registration (requires token)."""
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
        payload = {
            'employee_name': 'Test Engineer',
            'department': 'QA Department',
            'designation': 'QA Lead',
            'email': 'qa_lead@company.com',
            'mobile': '+61400111222',
            'status': 1
        }
        
        response = self.client.post('/api/employee',
                                   data=json.dumps(payload),
                                   headers=headers)
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 211)
        self.assertTrue(data['success'])
        self.assertIn('employee_id', data)
        self.__class__.employee_id = data['employee_id']

    def test_04_list_employees(self):
        """Test retrieving employee directories."""
        headers = {
            'Authorization': f'Bearer {self.token}'
        }
        response = self.client.get('/api/employees', headers=headers)
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertGreater(len(data['employees']), 0)

    def test_05_update_employee(self):
        """Test editing employee information."""
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
        payload = {
            'employee_id': self.employee_id,
            'employee_name': 'Test Engineer Updated',
            'department': 'QA Division',
            'designation': 'QA Manager',
            'email': 'qa_mgr@company.com',
            'mobile': '+61400111333',
            'status': 1
        }
        
        response = self.client.put('/api/employee',
                                  data=json.dumps(payload),
                                  headers=headers)
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])

    def test_06_checkin_attendance(self):
        """Test check-in logs for employee."""
        payload = {
            'employee_id': self.employee_id,
            'confidence_score': 0.95,
            'latitude': -37.8136,
            'longitude': 144.9631,
            'device_id': 'TestRunner'
        }
        response = self.client.post('/api/attendance/checkin',
                                   data=json.dumps(payload),
                                   content_type='application/json')
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertIn('check_in', data)
        self.assertIn('status', data)

    def test_07_duplicate_checkin_blocked(self):
        """Test that duplicate check-in for same day is blocked."""
        payload = {
            'employee_id': self.employee_id,
            'confidence_score': 0.95,
            'latitude': -37.8136,
            'longitude': 144.9631,
            'device_id': 'TestRunner'
        }
        response = self.client.post('/api/attendance/checkin',
                                   data=json.dumps(payload),
                                   content_type='application/json')
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 400)
        self.assertFalse(data['success'])
        self.assertIn('Duplicate', data['message'])

    def test_08_face_status(self):
        """Test retrieving face registration status."""
        headers = {
            'Authorization': f'Bearer {self.token}'
        }
        response = self.client.get(f'/api/face-status?employee_id={self.employee_id}', headers=headers)
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertEqual(data['employee_id'], self.employee_id)
        self.assertIn('enrolled', data)
        self.assertIn('enrollment_count', data)

    def test_09_late_arrivals_report(self):
        """Test fetching late check-ins report."""
        headers = {
            'Authorization': f'Bearer {self.token}'
        }
        response = self.client.get('/api/reports/late', headers=headers)
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertIn('records', data)

if __name__ == '__main__':
    unittest.main()
