# Client News Tracker

A free, automated web application that tracks the latest news articles related to specific companies in near real-time. It fetches articles every 10 minutes using Google News RSS feeds, stores them to avoid duplicates, and sends Email notifications.

## Features
- **Add/Remove Companies**: Track multiple companies effortlessly through the app dashboard.
- **Automated Fetching**: Retrieves Google News RSS feeds continuously every 10 minutes in the background.
- **Email Notifications**: Alerts you via Email using Gmail SMTP when new unique articles are found.
- **Deduplication**: Saves all seen articles into a local SQLite DB to prevent duplicate alerts.
- **Streamlit Dashboard**: Browse fetched articles sorted by newest first.

## Application Architecture
- **Backend**: Python `feedparser` and `requests`.
- **Database**: `SQLite` (built-in).
- **Scheduling**: `APScheduler` (Background process configured to run inside Streamlit).
- **Frontend**: `Streamlit`.

## Prerequisites

- Python 3.9 or higher.
- A Gmail account with **App Passwords** enabled for sending emails.
  - To generate an app password, go to [Google Account > Security > App Passwords](https://myaccount.google.com/apppasswords).

## Setup & Local Execution

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables**
   Set the following variables on your machine or deployment platform to enable email notifications. If these are not set, articles will still be fetched and displayed on the dashboard, but you won't receive emails.

   - `GMAIL_USER`: Your email address (e.g., `you@gmail.com`).
   - `GMAIL_PASS`: Your Gmail App Password.
   - `GMAIL_RECEIVER` (optional): The email address to send to. Defaults to `GMAIL_USER`.

3. **Run the Application**
   ```bash
   streamlit run app.py
   ```
   The database gets automatically initialized on first run and will be stored as `news_tracker.db` in the same directory. The scheduler thread will automatically pick up and run every 10 minutes as long as the application process is alive.

## Deployment Notes

### Deploying on Streamlit Cloud (Free)
1. Push this repository to GitHub.
2. Sign in to [Streamlit Community Cloud](https://share.streamlit.io).
3. Click "New App", select your repository, and set the main file path to `app.py`.
4. Go to **Advanced Settings -> Secrets** and input your environment variables in standard TOML format:
   ```toml
   GMAIL_USER = "you@gmail.com"
   GMAIL_PASS = "xxxx xxxx xxxx xxxx"
   GMAIL_RECEIVER = "optional_alt@domain.com"
   ```
5. Click **Deploy**.

## Using the GSD Methodology
This project was built following the **GSD (Get Shit Done)** methodology.
See `PROJECT_RULES.md` and `.gsd/` folder for specification artifacts.
