# Project Specification: Client News Tracker

## Status
Status: FINALIZED

## Objective
Build a free, automated web application called **Client News Tracker**. The application will track the latest news articles related to specific companies (e.g., "Boston Consulting Group") in near real time (every 10–20 minutes) using free tools and APIs.

## Core Requirements

1. **News Source:** Use **Google News RSS feeds** (e.g., `https://news.google.com/rss/search?q=<company_name>`).
2. **Data Fetching:** Fetch articles every 10 minutes automatically.
3. **Storage:** Use a local JSON or SQLite database to avoid duplicate articles.
4. **Notification System:**
   - Email via Gmail SMTP.
5. **Dashboard:**
   - Build a simple dashboard using **Streamlit** (preferred over FastAPI+React for simplicity and speed).
   - Show latest articles, publication time, and link to the source.
6. **Scheduling:**
   - Use Python’s `schedule` or `APScheduler` library for background jobs.
   - Ensure updates every 10 mins.
7. **Deployment:**
   - Deploy the app on a **free tier** platform (Streamlit Cloud preferred for Streamlit apps or Render).

## Tech Stack
* **Backend:** Python (`requests`, `feedparser`, `schedule`/`APScheduler`)
* **Storage:** SQLite (better for concurrency compared to JSON)
* **Frontend:** Streamlit
* **Notifications:** Email (Gmail SMTP)

## Features Summary
* Add/Remove companies to track with region specification (India/Global).
* Automatically fetch latest articles via Google News RSS with regional filters.
* Send Email when a new article is detected.
* Store all seen articles to prevent duplicate notifications.
* Simple dashboard to browse all tracked articles with IST and relative time.

## Regional & Time Enhancements
1. **Timezone:** Display publication time in **India Standard Time (IST)**.
2. **Relative Time:** Add a column for relative time (e.g., "5 minutes ago", "2 hours ago").
3. **Region Selection:** Allow specifying news region per company (India vs Global).
   - Global: Standard query.
   - India: Appending `&gl=IN&ceid=IN:en` or similar to RSS URL.

## Constraints & Notes
* Entire solution must be **free to run**.
* Clean, well-documented Python code.
* Include setup instructions (Email app password, scheduling, etc.).
* No paid API keys should be required.
* Deliverables: Full Python project code with dependencies, configuration, and a README explaining setup.
