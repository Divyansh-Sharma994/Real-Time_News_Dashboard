import feedparser
import requests
import urllib.parse
import warnings
warnings.filterwarnings("ignore", category=SyntaxWarning)
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from database import get_all_companies, add_article, update_company_status, init_db
from textblob import TextBlob
from newspaper import Article, Config
from bs4 import BeautifulSoup
import trafilatura
import logging
from concurrent.futures import ThreadPoolExecutor # For parallel extraction
from googlenewsdecoder import gnewsdecoder
import time


# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress chatter
logging.getLogger('trafilatura').setLevel(logging.ERROR)
logging.getLogger('hls').setLevel(logging.ERROR) 
# Suppress urllib3 connection pool warnings (caused by newspaper3k/trafilatura internal requests)
logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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

def fetch_rss_for_company(company_name: str, company_id: int, region: str = 'Global', sync_time=None):
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
        import time # Local import for tiny sleep
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
                        # Use googlenewsdecoder (handles the internal Google redirect)
                        decoded = gnewsdecoder(link)
                        if decoded.get("status"):
                            final_url = decoded["decoded_url"]
                            logger.debug(f"Decoded Google News URL → {final_url}")
                        else:
                            logger.warning(f"gnewsdecoder failed: {decoded.get('message')}")
                    except Exception as e:
                        logger.error(f"Error using gnewsdecoder: {e}")
                # Optional retry if decoder didn't change URL
                def fetch_with_retry(url, hdrs, tries=3, backoff=2):
                    for i in range(1, tries + 1):
                        try:
                            r = session.get(url, headers=hdrs, timeout=7, allow_redirects=True)
                            if r.status_code == 200:
                                return r
                        except Exception as exc:
                            logger.debug(f"Retry {i}/{tries} failed: {exc}")
                        time.sleep(backoff * i)
                    return None
                if final_url == link:
                    r = fetch_with_retry(link, headers)
                    if r:
                        final_url = r.url
                
                # Mandatory Date Verification: Use Newspaper3k to check metadata date BEFORE extraction
                # This catches articles where RSS says "now" but metadata says "last week"
                try:
                    config = Config()
                    config.browser_user_agent = headers['User-Agent']
                    config.request_timeout = 8
                    article = Article(final_url, config=config)
                    article.download()
                    article.parse()
                    
                    if article.publish_date:
                        ext_date = article.publish_date
                        if ext_date.tzinfo is None:
                            ext_date = ext_date.replace(tzinfo=timezone.utc)
                        
                        now = datetime.now(timezone.utc)
                        if (now - ext_date) > timedelta(hours=24):
                            logger.warning(f"Discarding old article based on metadata ({ext_date}): {final_url}")
                            return None
                    
                    # If it passed date check, we can use the text already parsed by newspaper3k if it's good
                    if article.text and len(article.text.strip()) > 300:
                        full_content = article.text
                except Exception as e:
                    logger.debug(f"Metadata date extraction failed for {final_url}: {e}")

                # 2. Try Trafilatura (if newspaper3k didn't already get good content)
                if full_content == "Could not fetch full article content." or len(full_content) < 300:
                    downloaded = trafilatura.fetch_url(final_url)
                    if downloaded:
                        extracted = trafilatura.extract(downloaded)
                        if extracted and len(extracted.strip()) > 300:
                            full_content = extracted
                
                # 3. Final Fallback - RSS summary
                if full_content == "Could not fetch full article content." or len(full_content) < 150:
                    summary_text = BeautifulSoup(summary, "html.parser").get_text()
                    full_content = summary_text if summary_text.strip() else summary
                
                if full_content != "Could not fetch full article content.":
                    logger.info(f"Successfully extracted content for {final_url}")
                else:
                    logger.warning(f"All extraction methods failed for {final_url}")
            except Exception as e:
                logger.error(f"Error fetching article content from {link}: {e}")
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
        # Determine extraction method for storage
        extraction_method = 'summary'
        if full_content != "Could not fetch full article content." and len(full_content) >= 150:
            extraction_method = 'full'
        
        if link:
            is_new = add_article(
                company_id=company_id,
                title=title,
                link=link,
                published_at=published_at,
                source=source,
                summary=full_content, # Now storing full content in summary column
                sentiment=sentiment,
                extraction_method=extraction_method # Pass the extraction method
            )
            if is_new:
                return {
                    'title': title, 'link': link, 'published_at': published_at,
                    'source': source, 'company_name': company_name,
                    'summary': full_content, 'sentiment': sentiment,
                    'extraction_method': extraction_method
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
            entries_to_process = [e for e in feed.entries if is_within_24_hours(getattr(e, 'published', 'Unknown Date'))]
            
            # Process entries in parallel (max 2 threads per company to avoid 503s from Google)
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(process_entry, entries_to_process))
                
            for art in results:
                if art:
                    all_new_articles.append(art)
                    region_found += 1
            
            total_found_in_24h += region_found

        except Exception as e:
            print(f"Error fetching {r} RSS for {company_name}: {e}")

    # Close session after all regions for this company are done
    session.close()

    # Final Status Update (use sync_time for consistency if provided)
    ref_time = sync_time if sync_time else datetime.now(timezone.utc)
    ist_now = ref_time + timedelta(hours=5, minutes=30)
    now_str = ist_now.strftime("%H:%M:%S")
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
    
    # Capture single session start time for consistency across all brand status updates
    session_start_utc = datetime.now(timezone.utc)
    from database import set_last_fetch_time
    set_last_fetch_time(session_start_utc.isoformat())

    # Process companies in parallel (max 2 at once) to avoid memory spikes and 503s
    def fetch_comp(comp):
        return fetch_rss_for_company(comp['name'], comp['id'], comp.get('region', 'Global'), sync_time=session_start_utc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(fetch_comp, companies))
        
    for res in results:
        all_new_articles.extend(res)
        
    return all_new_articles

if __name__ == "__main__":
    # Test fetch
    from database import init_db, add_company
    init_db()
    
    comp_added = add_company("Boston Consulting Group")
    new_docs = fetch_all_companies()
    print(f"Fetched {len(new_docs)} new articles.")
