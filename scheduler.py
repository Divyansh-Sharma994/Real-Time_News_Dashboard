import os
import atexit
from apscheduler.schedulers.background import BackgroundScheduler
from fetcher import fetch_all_companies
from notifier import send_notification
import datetime
from database import init_db, set_last_fetch_time

def run_job():
    print("Running scheduled job: fetching tracking tasks...")
    init_db()
    new_articles = fetch_all_companies()
    if new_articles:
        print(f"Found {len(new_articles)} new articles. Sending notification.")
        send_notification(new_articles)
    else:
        print("No new articles found.")

def init_scheduler():
    # Only run in main process (prevents duplicate jobs in certain WSGI environments)
    if os.environ.get("SCHEDULER_STARTED") == "1":
        return
        
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_job, 'interval', minutes=5, id='fetch_job', replace_existing=True)
    # Start the scheduler
    scheduler.start()
    os.environ["SCHEDULER_STARTED"] = "1"
    
    # Run once immediately in a SEPARATE thread so we don't block Streamlit UI
    import threading
    threading.Thread(target=run_job, daemon=True).start()
    
    atexit.register(lambda: scheduler.shutdown())
    print("Background scheduler initialized. Running every 5 minutes.")

if __name__ == "__main__":
    init_scheduler()
    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Scheduler stopped.")
