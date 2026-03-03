import smtplib
from email.message import EmailMessage
import os
from dotenv import load_dotenv

load_dotenv()

def send_notification(new_articles):
    if not new_articles:
        return
        
    sender_email = os.getenv("GMAIL_USER")
    receiver_email = os.getenv("GMAIL_RECEIVER") or sender_email
    password = os.getenv("GMAIL_PASS")
    
    if not sender_email or not password:
        print("Gmail credentials are not configured. Skipping email notification.")
        return
        
    msg = EmailMessage()
    msg['Subject'] = f"Client News Tracker: {len(new_articles)} New Articles Found"
    msg['From'] = sender_email
    msg['To'] = receiver_email
    
    content = "New articles found:\n\n"
    
    for article in new_articles:
        content += f"Company: {article['company_name']}\n"
        content += f"Title: {article['title']}\n"
        content += f"Link: {article['link']}\n"
        content += f"Published: {article['published_at']}\n"
        content += "-"*40 + "\n"
        
    msg.set_content(content)
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(sender_email, password)
            smtp.send_message(msg)
            print("Successfully sent email notification.")
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == "__main__":
    # Test notification
    test_arts = [{
        "company_name": "Test Company",
        "title": "Test Title",
        "link": "http://example.com",
        "published_at": "Today"
    }]
    send_notification(test_arts)
