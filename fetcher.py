import feedparser
import requests
import urllib.parse
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from database import get_all_companies, add_article, update_company_status

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

    # helper for parsing feed entries
    def process_entry(entry):
        title = getattr(entry, 'title', 'No Title')
        link = getattr(entry, 'link', '')
        published_at = getattr(entry, 'published', 'Unknown Date')
        source = getattr(entry, 'source', {}).get('title', 'Google News')
        
        if link:
            is_new = add_article(
                company_id=company_id,
                title=title,
                link=link,
                published_at=published_at,
                source=source
            )
            if is_new:
                return {
                    'title': title, 'link': link, 'published_at': published_at,
                    'source': source, 'company_name': company_name
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
