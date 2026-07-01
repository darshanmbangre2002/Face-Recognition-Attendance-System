import os
from datetime import timedelta

class Config:
    # Flask Security
    SECRET_KEY = os.environ.get('SECRET_KEY', 'super-secret-key-change-in-production')
    
    # JWT Config
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
    
    # Database Config
    # Default is SQLite for zero-configuration startup. To use MySQL, set DB_HOST in the environment or .env.
    DB_TYPE = os.environ.get('DB_TYPE', 'sqlite').lower()
    DB_HOST = os.environ.get('DB_HOST', None)
    DB_USER = os.environ.get('DB_USER', 'root')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
    DB_NAME = os.environ.get('DB_NAME', 'face_attendance')
    DB_PORT = int(os.environ.get('DB_PORT', 3306))
    
    SQLITE_PATH = os.environ.get('SQLITE_PATH','attendance.db')
    
    # File Upload Config
    UPLOAD_FOLDER_PROFILES = os.environ.get('UPLOAD_FOLDER_PROFILES', os.path.join('uploads', 'profiles'))
    UPLOAD_FOLDER_ATTENDANCE = os.environ.get('UPLOAD_FOLDER_ATTENDANCE', os.path.join('uploads', 'attendance'))
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    
    # Face recognition matching threshold (similarity). Higher is stricter, lower is looser.
    FACE_MATCH_THRESHOLD = float(os.environ.get('FACE_MATCH_THRESHOLD', 0.45))
    
    # InsightFace model name. Defaults to 'buffalo_sc' for low-memory cloud hosting environments (like Render).
    INSIGHTFACE_MODEL = os.environ.get('INSIGHTFACE_MODEL', 'buffalo_sc')
    
    # Mail Config (Optional)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', None)
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', None)
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', None)

    @classmethod
    def init_app(cls):
        # Create upload directories if they don't exist
        os.makedirs(cls.UPLOAD_FOLDER_PROFILES, exist_ok=True)
        os.makedirs(cls.UPLOAD_FOLDER_ATTENDANCE, exist_ok=True)
