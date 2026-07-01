import os
import sqlite3
import pymysql
import json
from datetime import datetime
from config import Config

class Database:
    @staticmethod
    def get_connection():
        """Returns a connection based on the DB_TYPE config."""
        if Config.DB_TYPE == 'mysql' or Config.DB_HOST:
            # Establish MySQL Connection
            return pymysql.connect(
                host=Config.DB_HOST,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                database=Config.DB_NAME,
                port=Config.DB_PORT,
                cursorclass=pymysql.cursors.DictCursor
            )
        else:
            # Establish SQLite Connection
            conn = sqlite3.connect(Config.SQLITE_PATH)
            # Enable dictionary-like row factory to match PyMySQL DictCursor
            conn.row_factory = sqlite3.Row
            return conn

    @classmethod
    def execute_query(cls, query, params=None, commit=False, fetch_all=False, fetch_one=False):
        """Executes a query safely, handles connections, and returns results."""
        is_mysql = Config.DB_TYPE == 'mysql' or Config.DB_HOST
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        # SQLite uses '?' placeholder while PyMySQL uses '%s'
        if not is_mysql and params:
            # Simple conversion of %s placeholders to SQLite ? if needed
            query = query.replace('%s', '?')
        
        result = None
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
                
            if commit:
                conn.commit()
                if not is_mysql:
                    result = cursor.lastrowid
                else:
                    result = cursor.lastrowid or cursor.rowcount
            elif fetch_all:
                rows = cursor.fetchall()
                if not is_mysql:
                    # Convert sqlite3.Row objects to standard dictionaries
                    result = [dict(row) for row in rows]
                else:
                    result = list(rows)
            elif fetch_one:
                row = cursor.fetchone()
                if row and not is_mysql:
                    result = dict(row)
                else:
                    result = row
        except Exception as e:
            if commit:
                conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()
            
        return result

    @classmethod
    def initialize_db(cls):
        """Creates tables non-destructively, ensuring zero interference with existing tables."""
        is_mysql = Config.DB_TYPE == 'mysql' or Config.DB_HOST
        
        if is_mysql:
            # Create MySQL database if it doesn't exist
            # Note: We need a connection without database selected to create it
            conn = pymysql.connect(
                host=Config.DB_HOST,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                port=Config.DB_PORT
            )
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.DB_NAME}")
            cursor.close()
            conn.close()

        # 1. Employees Table
        if is_mysql:
            create_employees = """
            CREATE TABLE IF NOT EXISTS employees (
                employee_id INT AUTO_INCREMENT PRIMARY KEY,
                employee_name VARCHAR(150) NOT NULL,
                department VARCHAR(100),
                designation VARCHAR(100),
                email VARCHAR(150),
                mobile VARCHAR(20),
                status INT DEFAULT 1
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        else:
            create_employees = """
            CREATE TABLE IF NOT EXISTS employees (
                employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_name TEXT NOT NULL,
                department TEXT,
                designation TEXT,
                email TEXT,
                mobile TEXT,
                status INTEGER DEFAULT 1
            );
            """
        cls.execute_query(create_employees, commit=True)

        # 2. Face Embedding Table
        # We store embedding as a TEXT field containing JSON serialized float arrays.
        # This is fully compatible across SQLite and MySQL.
        if is_mysql:
            create_embeddings = """
            CREATE TABLE IF NOT EXISTS face_embeddings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                employee_id INT NOT NULL,
                embedding LONGTEXT NOT NULL,
                model_version VARCHAR(50) DEFAULT 'v1',
                created_date DATETIME NOT NULL,
                FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        else:
            create_embeddings = """
            CREATE TABLE IF NOT EXISTS face_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                embedding TEXT NOT NULL,
                model_version TEXT DEFAULT 'v1',
                created_date TEXT NOT NULL,
                FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE
            );
            """
        cls.execute_query(create_embeddings, commit=True)

        # 3. Attendance Table
        if is_mysql:
            create_attendance = """
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
            """
        else:
            create_attendance = """
            CREATE TABLE IF NOT EXISTS attendance (
                attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                attendance_date TEXT NOT NULL,
                check_in TEXT NOT NULL,
                check_out TEXT,
                latitude REAL,
                longitude REAL,
                device_id TEXT,
                confidence_score REAL,
                image_path TEXT,
                status TEXT DEFAULT 'Present',
                FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE,
                UNIQUE(employee_id, attendance_date)
            );
            """
        cls.execute_query(create_attendance, commit=True)
        
        # Verify schema integrity - Safely check and add any missing columns in `employees` and `attendance` tables
        cls.verify_and_update_schema()

    @classmethod
    def verify_and_update_schema(cls):
        """Safely alters existing tables to append missing fields without affecting existing records."""
        is_mysql = Config.DB_TYPE == 'mysql' or Config.DB_HOST
        
        if is_mysql:
            # Check fields in employees table
            try:
                columns = cls.execute_query("SHOW COLUMNS FROM employees", fetch_all=True)
                col_names = [col['Field'] for col in columns]
                if 'status' not in col_names:
                    cls.execute_query("ALTER TABLE employees ADD COLUMN status INT DEFAULT 1", commit=True)
            except Exception as e:
                print(f"Error updating MySQL employees schema: {e}")
                
            # Check fields in attendance table
            try:
                columns = cls.execute_query("SHOW COLUMNS FROM attendance", fetch_all=True)
                col_names = [col['Field'] for col in columns]
                if 'status' not in col_names:
                    cls.execute_query("ALTER TABLE attendance ADD COLUMN status VARCHAR(50) DEFAULT 'Present'", commit=True)
            except Exception as e:
                print(f"Error updating MySQL attendance schema: {e}")
                
            # Ensure unique key exists on MySQL attendance
            try:
                cls.execute_query("ALTER TABLE attendance ADD UNIQUE KEY unique_emp_date (employee_id, attendance_date)", commit=True)
            except Exception as e:
                # Already exists or columns contain duplicates (handled gracefully)
                pass
        else:
            # SQLite check columns
            try:
                info = cls.execute_query("PRAGMA table_info(employees)", fetch_all=True)
                col_names = [col['name'] for col in info]
                if 'status' not in col_names:
                    cls.execute_query("ALTER TABLE employees ADD COLUMN status INTEGER DEFAULT 1", commit=True)
            except Exception as e:
                print(f"Error updating SQLite employees schema: {e}")
                
            try:
                info = cls.execute_query("PRAGMA table_info(attendance)", fetch_all=True)
                col_names = [col['name'] for col in info]
                if 'status' not in col_names:
                    cls.execute_query("ALTER TABLE attendance ADD COLUMN status TEXT DEFAULT 'Present'", commit=True)
            except Exception as e:
                print(f"Error updating SQLite attendance schema: {e}")
