# Development Roadmap: Client News Tracker

## Phase 1: Foundation & Database
- [x] Initialize project structure (requirements.txt, README outline).
- [x] Create SQLite database schema: `articles` table and `companies` table.
- [x] Write functions to add/remove companies to track.
- [x] Write functions to check for article duplicates and insert new ones.

## Phase 2: RSS Fetching & Processing
- [x] Implement `feedparser` logic to fetch Google News RSS for a given company.
- [x] Extract article title, link, publication date, and source.
- [x] Implement logic to iterate over all tracked companies and save new articles.

## Phase 3: Notifications
- [x] Set up Gmail SMTP sender function.
- [x] Format email content summarizing new articles.
- [x] Trigger email only when new (deduplicated) articles are found during a fetch.

## Phase 4: UI & Dashboard
- [x] Build a Streamlit app (`app.py`).
- [x] Add a sidebar to manage (add/remove) tracked companies.
- [x] Implement a main view showing the latest fetched articles (title, time, source link).

## Phase 5: Scheduling
- [x] Integrate background scheduling (`APScheduler` or Streamlit's mechanisms / `schedule` for a separate worker process).
- [x] Ensure fetching runs every 10 minutes continuously when the app is active.

## Phase 6: Polish and Deployment
- [x] Finalize `README.md` with detailed setup instructions (Gmail App Password, Streamlit Cloud deployment).
- [x] Prepare `requirements.txt`.
- [x] Final end-to-end testing and verification.

## Phase 7: Regional Context & Specialized Time Display
- [x] Update Database: Add `region` column to `companies` table.
- [x] Update UI: Add Region selector (India/Global) in company management.
- [x] Update Fetcher: Implement regional Google News RSS feeds based on company setting.
- [x] Update UI Dashboard: Convert timestamps to India Standard Time (IST).
- [x] Update UI Dashboard: Add "Time Ago" column (Relative Time).
