import feedparser
import requests
import urllib.parse
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from database import get_all_companies, add_article, update_company_status, init_db
from textblob import TextBlob
from newspaper import Article, Config
from bs4 import BeautifulSoup
import trafilatura
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress trafilatura chatter
logging.getLogger('trafilatura').setLevel(logging.ERROR)
logging.getLogger('hls').setLevel(logging.ERROR) # newspaper uses hls

# Adding +when:1d to filter it at Google's end, and strictly enforcing it in python.
# Base URL for Global and India regions
# India-specific: append &gl=IN&ceid=IN:en
BASE_RSS_URL = "https://news.google.com/rss/search?q={query}+when:1d{suffix}"
BASE_SEARCH_URL = "https://news.google.com/rss/search?q={query}{suffix}"

def is_within_24_hours(published_at: str) -> bool:
    if published_at == 'Unknown Date':
        return False
    try:
        pub_dt = parsedate_to_datetime(published_at)
        now = datetime.now(timezone.utc)
        return (now - pub_dt) <= timedelta(hours=24)
    except Exception:
        return False

def fetch_rss_for_company(company_name: str, company_id: int, region: str = 'Global'):
    # Determine which regions to fetch
    regions_to_fetch = []
    if region == 'Both':
        regions_to_fetch = ['Global', 'India']
    else:
        regions_to_fetch = [region]
        
    all_new_articles = []
    total_found_in_24h = 0
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36'
    }

    # Create a single session for all requests in this company fetch
    # This reuses connections and avoids 'Connection pool is full' warnings
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # helper for parsing feed entries
    def process_entry(entry):
        title = getattr(entry, 'title', 'No Title')
        link = getattr(entry, 'link', '')
        published_at = getattr(entry, 'published', 'Unknown Date')
        source = getattr(entry, 'source', {}).get('title', 'Google News')
        summary = getattr(entry, 'summary', 'No summary available.')
        full_content = "Could not fetch full article content."
        
        # Try to fetch full article content using Newspaper3k and Trafilatura
        if link:
            try:
                # 1. Resolve redirect if it's a Google News link
                final_url = link
                if "news.google.com" in link:
                    try:
                        # Use the shared session for better performance
                        r = session.get(link, headers=headers, timeout=7, allow_redirects=True)
                        final_url = r.url
                    except Exception as e:
                        logger.debug(f"Redirect resolution failed: {e}")
                
                # 2. Try Trafilatura (usually more robust for modern news sites)
                downloaded = trafilatura.fetch_url(final_url)
                if downloaded:
                    extracted = trafilatura.extract(downloaded)
                    if extracted and len(extracted.strip()) > 300: # Threshold for a real article
                        full_content = extracted
                
                # 3. Fallback to Newspaper3k if trafilatura fails or yields very little
                if full_content == "Could not fetch full article content." or len(full_content) < 300:
                    config = Config()
                    config.browser_user_agent = headers['User-Agent']
                    config.request_timeout = 10
                    article = Article(final_url, config=config)
                    article.download()
                    article.parse()
                    if article.text.strip() and len(article.text.strip()) > len(full_content):
                        full_content = article.text

                # 4. Final Fallback to RSS summary if both extraction methods are poor
                if full_content == "Could not fetch full article content." or len(full_content) < 150:
                    summary_text = BeautifulSoup(summary, "html.parser").get_text()
                    full_content = summary_text if summary_text.strip() else summary
                    
            except Exception as e:
                logger.error(f"Error fetching full content from {link}: {e}")
                summary_text = BeautifulSoup(summary, "html.parser").get_text()
                full_content = summary_text if summary_text.strip() else summary
        
        # Simple Sentiment analysis using TextBlob (on full content if available)
        blob = TextBlob(f"{title} {full_content[:1000]}") # Analyze first 1000 chars
        polarity = blob.sentiment.polarity
        
        if polarity > 0.05:
            sentiment = "Positive"
        elif polarity < -0.05:
            sentiment = "Negative"
        else:
            sentiment = "Neutral"
        
        if link:
            is_new = add_article(
                company_id=company_id,
                title=title,
                link=link,
                published_at=published_at,
                source=source,
                summary=full_content, # Now storing full content in summary column
                sentiment=sentiment
            )
            if is_new:
                return {
                    'title': title, 'link': link, 'published_at': published_at,
                    'source': source, 'company_name': company_name,
                    'summary': full_content, 'sentiment': sentiment
                }
        return None

    for r in regions_to_fetch:
        encoded_query = urllib.parse.quote(company_name)
        suffix = "&gl=IN&ceid=IN:en" if r == 'India' else ""
        rss_url = BASE_RSS_URL.format(query=encoded_query, suffix=suffix)
        
        try:
            response = requests.get(rss_url, headers=headers, timeout=10)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            
            # Step 1: 24 Hour Window
            region_found = 0
            for entry in feed.entries:
                if is_within_24_hours(getattr(entry, 'published', 'Unknown Date')):
                    art = process_entry(entry)
                    if art:
                        all_new_articles.append(art)
                        region_found += 1
            
            total_found_in_24h += region_found

            # Step 2: Fallback if NOTHING found in 24h for THIS region
            if region_found == 0:
                if feed.entries:
                    # Try most recent in existing feed
                    art = process_entry(feed.entries[0])
                    if art: all_new_articles.append(art)
                else:
                    # Broad fallback
                    try:
                        fb_url = BASE_SEARCH_URL.format(query=encoded_query, suffix=suffix)
                        fb_resp = requests.get(fb_url, headers=headers, timeout=10)
                        fb_feed = feedparser.parse(fb_resp.content)
                        if fb_feed.entries:
                            art = process_entry(fb_feed.entries[0])
                            if art: all_new_articles.append(art)
                    except: pass
        except Exception as e:
            print(f"Error fetching {r} RSS for {company_name}: {e}")

    # Close session after all regions for this company are done
    session.close()

    # Final Status Update
    now_str = datetime.now().strftime("%H:%M:%S")
    status_msg = f"[{now_str}] Checked {region}: "
    if all_new_articles:
        status_msg += f"Found {len(all_new_articles)} new items"
    else:
        status_msg += "No new items found"
    
    update_company_status(company_id, status_msg)
    return all_new_articles

def fetch_all_companies():
    companies = get_all_companies()
    all_new_articles = []
    
    for comp in companies:
        company_id = comp['id']
        company_name = comp['name']
        region = comp.get('region', 'Global')
        
        new_articles = fetch_rss_for_company(company_name, company_id, region)
        all_new_articles.extend(new_articles)
        
    return all_new_articles

if __name__ == "__main__":
    # Test fetch
    from database import init_db, add_company
    init_db()
    
    comp_added = add_company("Boston Consulting Group")
    new_docs = fetch_all_companies()
    print(f"Fetched {len(new_docs)} new articles.")
