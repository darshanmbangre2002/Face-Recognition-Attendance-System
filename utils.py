import jwt
import csv
import io
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from config import Config
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# -------------------------------------------------------------
# JWT Authentication Helpers
# -------------------------------------------------------------
def generate_token(username, role='admin'):
    """Generates a JWT access token for a user."""
    payload = {
        'exp': datetime.now(timezone.utc) + Config.JWT_ACCESS_TOKEN_EXPIRES,
        'iat': datetime.now(timezone.utc),
        'sub': username,
        'role': role
    }
    return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm='HS256')

def decode_token(token):
    """Decodes a JWT access token. Returns the payload or None if invalid/expired."""
    try:
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None  # Token expired
    except jwt.InvalidTokenError:
        return None  # Token invalid

# -------------------------------------------------------------
# Notification System (Email Exporter)
# -------------------------------------------------------------
def send_email_notification(to_email, subject, body_html):
    """Sends an email notification. Logs message if SMTP credentials are not configured."""
    if not Config.MAIL_USERNAME or not Config.MAIL_PASSWORD or not to_email:
        print(f"[Email Logger] (SMTP not configured) To: {to_email} | Subject: {subject} | Body: {body_html[:150]}...")
        return True
        
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = Config.MAIL_DEFAULT_SENDER or Config.MAIL_USERNAME
        msg['To'] = to_email
        
        part = MIMEText(body_html, 'html')
        msg.attach(part)
        
        server = smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT)
        if Config.MAIL_USE_TLS:
            server.starttls()
            
        server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
        server.sendmail(msg['From'], to_email, msg.as_string())
        server.quit()
        print(f"[Email Notification] Email sent successfully to {to_email}.")
        return True
    except Exception as e:
        print(f"[Email Error] Failed to send email to {to_email}: {e}")
        return False

# -------------------------------------------------------------
# Report Exporters (Excel CSV and PDF)
# -------------------------------------------------------------
def generate_attendance_csv(attendance_records):
    """Generates a CSV format attendance report in memory."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        'Attendance ID', 'Employee ID', 'Employee Name', 'Department', 
        'Designation', 'Date', 'Check In', 'Status', 
        'Latitude', 'Longitude', 'Device ID', 'Confidence Score'
    ])
    
    # Rows
    for rec in attendance_records:
        writer.writerow([
            rec.get('attendance_id', ''),
            rec.get('employee_id', ''),
            rec.get('employee_name', ''),
            rec.get('department', ''),
            rec.get('designation', ''),
            rec.get('attendance_date', ''),
            rec.get('check_in', ''),
            rec.get('status', 'Present'),
            rec.get('latitude', '') or 'N/A',
            rec.get('longitude', '') or 'N/A',
            rec.get('device_id', '') or 'N/A',
            f"{rec.get('confidence_score', 0.0):.2f}" if rec.get('confidence_score') is not None else 'N/A'
        ])
        
    output.seek(0)
    return output.getvalue()

def generate_attendance_pdf(attendance_records, title="Attendance Report"):
    """Generates a styled PDF report in memory using ReportLab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Styles for Premium Look
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=colors.HexColor('#0F172A'), # Slate 900
        spaceAfter=15
    )
    
    meta_style = ParagraphStyle(
        'ReportMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#64748B'), # Slate 500
        spaceAfter=25
    )
    
    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=colors.white
    )
    
    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        textColor=colors.HexColor('#334155') # Slate 700
    )
    
    story = []
    
    # Document Header
    story.append(Paragraph(title, title_style))
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    story.append(Paragraph(f"Generated On: {date_str} | Total Records: {len(attendance_records)}", meta_style))
    story.append(Spacer(1, 10))
    
    # Table Header Row
    headers = [
        Paragraph("ID", table_header_style),
        Paragraph("Employee Name", table_header_style),
        Paragraph("Dept", table_header_style),
        Paragraph("Date", table_header_style),
        Paragraph("Check In", table_header_style),
        Paragraph("Status", table_header_style),
        Paragraph("Confidence", table_header_style)
    ]
    
    table_data = [headers]
    
    for rec in attendance_records:
        confidence = f"{rec.get('confidence_score', 0.0):.2f}" if rec.get('confidence_score') is not None else 'N/A'
        row = [
            Paragraph(str(rec.get('employee_id', '')), table_cell_style),
            Paragraph(str(rec.get('employee_name', '')), table_cell_style),
            Paragraph(str(rec.get('department', '')), table_cell_style),
            Paragraph(str(rec.get('attendance_date', '')), table_cell_style),
            Paragraph(str(rec.get('check_in', '')), table_cell_style),
            Paragraph(str(rec.get('status', 'Present')), table_cell_style),
            Paragraph(confidence, table_cell_style)
        ]
        table_data.append(row)
        
    # Table Styling
    # Widths sum up to 540 (Letter printable width is 8.5in * 72 - 72 = 540)
    col_widths = [40, 140, 90, 70, 70, 70, 60]
    
    t = Table(table_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')), # Slate 800
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')), # Slate 200 grid
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]), # Zebra styling
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]))
    
    story.append(t)
    doc.build(story)
    
    buffer.seek(0)
    return buffer.getvalue()
