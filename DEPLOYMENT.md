# AuraFace Portal — Deployment Guide for Render (Docker)
*Developed by Darshan M Bangre*

This guide outlines the steps to build, configure, and host the Face Recognition Attendance System as a secure Docker container on **Render**.

---

## 🏗️ 1. Render Deployment Steps (Docker Web Service)

1.  **Fork / Push Code to GitHub**:
    Ensure the code (including the newly generated `Dockerfile`) is pushed to your GitHub repository:
    ```bash
    git push -u origin main
    ```
2.  **Create a New Web Service**:
    *   Log in to [Render Dashboard](https://dashboard.render.com).
    *   Click **New +** ➡️ **Web Service**.
    *   Connect your GitHub repository.
3.  **Configure Build & Runtime Settings**:
    *   **Name**: `face-attendance-portal`
    *   **Region**: Select a region close to your user base.
    *   **Runtime**: Select **Docker** (Render will automatically detect your `Dockerfile`).
    *   **Instance Type**: Choose **Free** or **Starter**.
4.  **Add Persistent Storage (Crucial for SQLite and Profile Uploads)**:
    Since Render containers have ephemeral disks (data is wiped on every restart or deployment), you must attach a persistent disk if you are using SQLite:
    *   Scroll down to the **Disks** section.
    *   Click **Add Disk**.
    *   **Name**: `face-storage`
    *   **Mount Path**: `/var/data`
    *   **Size**: `1 GB` (or as required).

---

## ⚙️ 2. Environment Variables Configuration

In the Render Web Service settings, navigate to the **Environment** tab and add the following values:

| Key | Value | Purpose |
| :--- | :--- | :--- |
| `SECRET_KEY` | `your-production-secret-key` | Protects sessions and JWT tokens |
| `JWT_SECRET_KEY` | `your-production-jwt-token-key` | Signs secure administrative payloads |
| `DB_TYPE` | `sqlite` | Selects local database mode |
| `SQLITE_PATH` | `/var/data/attendance.db` | Maps SQLite file inside the **Persistent Disk Mount** |
| `UPLOAD_FOLDER_PROFILES` | `/var/data/profiles` | Saves profile photos on the Persistent Disk |
| `UPLOAD_FOLDER_ATTENDANCE` | `/var/data/attendance` | Saves check-in audit photos on the Persistent Disk |

---

## 🛢️ 3. Scaling to Production Databases (Optional)

For production loads, it is highly recommended to use a managed MySQL or PostgreSQL database instead of a local SQLite file.
To do this on Render:
1.  Click **New +** ➡️ **PostgreSQL** (or setup a MySQL instance).
2.  Add database credentials into your Web Service environment variables:
    *   `DB_TYPE` = `mysql` (or `postgresql`)
    *   `DB_HOST` = `your-render-db-host`
    *   `DB_USER` = `your-username`
    *   `DB_PASSWORD` = `your-password`
    *   `DB_NAME` = `your-database-name`
