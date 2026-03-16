import streamlit as st
import pandas as pd
import warnings
warnings.filterwarnings("ignore", category=SyntaxWarning)
from database import init_db, add_company, remove_company, get_all_companies, get_recent_articles, get_last_fetch_time, set_last_fetch_time, get_articles_for_brand
from scheduler import init_scheduler
from fetcher import fetch_all_companies
from notifier import send_notification
import datetime
from bs4 import BeautifulSoup
import streamlit.components.v1 as components
import io

# Initialize database
init_db()

# Start background scheduler
@st.cache_resource
def start_scheduler():
    init_scheduler()
    return True

start_scheduler()

# App layout
st.set_page_config(page_title="Client News Tracker", layout="wide")
st.title("📰 Client News Tracker")
st.markdown("Automatically track Google News RSS feeds for specific companies. Updates every 5 minutes.")

# Sidebar for managing companies
with st.sidebar:
    st.header("Tracked Companies")
    
    # Add company form
    with st.form("add_company_form", clear_on_submit=True):
        new_company = st.text_input("Add a Company")
        region = st.selectbox("Region", ["Global", "India", "Both"])
        submit_btn = st.form_submit_button("Add")
        if submit_btn and new_company:
            if add_company(new_company.strip(), region):
                st.success(f"Added {new_company} ({region})")
            else:
                st.error(f"{new_company} is already tracked.")
    
    # List and remove companies
    companies = get_all_companies()
    if not companies:
        st.info("No companies tracked right now. Add some above.")
    else:
        for comp in companies:
            with st.expander(f"🏢 {comp['name']} ({comp.get('region', 'Global')})"):
                st.write(f"**Status:** {comp.get('last_status', 'N/A')}")
                if st.button("Remove", key=f"remove_{comp['id']}", type="secondary", use_container_width=True):
                    remove_company(comp['name'])
                    st.rerun()

    # Fetch Status Timer
    st.markdown("---")
    st.subheader("Fetch Status")
    last_fetch_str = get_last_fetch_time()
    
    if last_fetch_str:
        try:
            # Parse the stored UTC time
            last_fetch_dt = datetime.datetime.fromisoformat(last_fetch_str).replace(tzinfo=datetime.timezone.utc)
            
            # Convert to Indian Standard Time (UTC+5:30)
            ist_offset = datetime.timedelta(hours=5, minutes=30)
            last_fetch_ist = last_fetch_dt + ist_offset
            next_fetch_ist = last_fetch_ist + datetime.timedelta(minutes=5)
            
            # Next fetch for JS (ISO format for the Date constructor)
            # We need the absolute next fetch in UTC for the JS timer to work consistently
            next_fetch_utc = last_fetch_dt + datetime.timedelta(minutes=5)
            
            # Text based times in IST
            st.write(f"**Last Check (IST):** {last_fetch_ist.strftime('%H:%M:%S')}")
            st.write(f"**Next Check (IST):** {next_fetch_ist.strftime('%H:%M:%S')}")
            
            # Classy JS Countdown Widget
            timer_html = f"""
            <div style="font-family: 'Inter', sans-serif; background: #1E1E1E; color: #FFFFFF; padding: 15px; border-radius: 8px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <div style="font-size: 11px; font-weight: 500; color: #AAAAAA; margin-bottom: 5px; text-transform: uppercase; letter-spacing: 1px;">Time Until Next Fetch</div>
                <div id="countdown" style="font-size: 32px; font-weight: 700; font-variant-numeric: tabular-nums; color: #00E676; text-shadow: 0 0 10px rgba(0,230,118,0.3);">--:--</div>
            </div>
            <script>
                // We pass the UTC ISO string so JS correctly identifies it and converts to browser local time
                var nextFetch = new Date('{next_fetch_utc.isoformat()}').getTime();
                var countdownEl = document.getElementById("countdown");
                
                var x = setInterval(function() {{
                    var now = new Date().getTime();
                    var distance = nextFetch - now;
                    
                    if (distance < 0) {{
                        clearInterval(x);
                        countdownEl.innerHTML = "WAITING...";
                        countdownEl.style.color = "#FFCA28";
                        
                        // Prevent infinite loop by tracking the last automatically reloaded timestamp
                        // It will strictly reload the parent frame ONCE per expired timeframe.
                        if (sessionStorage.getItem('last_timer_reload') !== nextFetch.toString()) {{
                            sessionStorage.setItem('last_timer_reload', nextFetch.toString());
                            setTimeout(function() {{ 
                                try {{ window.location.reload(); }} catch(e) {{}}
                                try {{ window.parent.location.reload(); }} catch(e) {{}}
                            }}, 5000);
                        }}
                    }} else {{
                        var minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
                        var seconds = Math.floor((distance % (1000 * 60)) / 1000);
                        
                        var minStr = minutes < 10 ? "0" + minutes : minutes;
                        var secStr = seconds < 10 ? "0" + seconds : seconds;
                        
                        countdownEl.innerHTML = minStr + ":" + secStr;
                        if (minutes < 1) {{
                            countdownEl.style.color = "#FFCA28"; // Warning yellow when under 1 min
                            countdownEl.style.textShadow = "0 0 10px rgba(255,202,40,0.3)";
                        }}
                    }}
                }}, 1000);
            </script>
            """
            components.html(timer_html, height=130)
            
        except Exception:
            st.write("Wait for first fetch...")
    else:
        st.write("Fetching soon...")

    # Manual Fetch Action
    st.markdown("---")
    if st.button("Fetch Now! (Manual Override)"):
        with st.spinner("Fetching latest news..."):
            new_arts = fetch_all_companies()
            if new_arts:
                send_notification(new_arts)
                st.success(f"Found {len(new_arts)} new articles and sent notification.")
            else:
                st.info("No new articles found.")
            st.rerun()

    # Brand Report Download Section
    st.markdown("---")
    st.subheader("📊 Download Brand Report")
    
    brand_names = [comp['name'] for comp in companies]
    report_brand = st.selectbox("Select Brand for Report", [""] + brand_names, index=0, help="Select a brand to download its articles in Excel format")
    
    if report_brand:
        brand_articles = get_articles_for_brand(report_brand)
        if brand_articles:
            # Prepare data for Excel
            report_df = pd.DataFrame(brand_articles)
            
            # Format report as requested: url, title, agency, time of publishing
            export_df = report_df[['link', 'title', 'source', 'published_at']].copy()
            export_df.columns = ['URL', 'Title', 'Agency', 'Time of Publishing']
            
            # Create Excel file in memory
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                export_df.to_excel(writer, index=False, sheet_name='News Articles')
            processed_data = output.getvalue()
            
            st.download_button(
                label=f"📥 Download {report_brand} Report",
                data=processed_data,
                file_name=f"{report_brand}_news_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.warning(f"No articles found for {report_brand}.")

# Main area for displaying articles
st.header("Recent Articles")

# Brand Filter & Search Bar
filter_col1, filter_col2 = st.columns([0.3, 0.7])

with filter_col1:
    brands_list = ["All Brands"] + [comp['name'] for comp in get_all_companies()]
    selected_brand = st.selectbox("🔍 Filter by Brand", brands_list)

with filter_col2:
    search_query = st.text_input("Looking for something specific?", placeholder="Type to search within Titles or Sources...")

recent_articles = get_recent_articles(500)

if not recent_articles:
    st.info("No articles found yet. Please add a company and wait for the fetcher.")
else:
    # Convert to DataFrame to display cleanly
    df = pd.DataFrame(recent_articles)
    
    # 1) Correctly parse actual timestamps and sort purely by LATEST published time
    df['parsed_date'] = pd.to_datetime(df['published_at'], format='mixed', utc=True)
    df = df.sort_values(by='parsed_date', ascending=False)
    
    # 2) Filter by select box dropdown
    if selected_brand != "All Brands":
        df = df[df['company_name'] == selected_brand]
        
    # 3) Filter by raw text search bar query
    if search_query:
        mask = (
            df['title'].str.contains(search_query, case=False, na=False) |
            df['source'].str.contains(search_query, case=False, na=False)
        )
        df = df[mask]
    
    # Warning if filters wipe the view
    if df.empty:
        st.warning(f"No results found for your search criteria.")
    else:
        # 4) India Time (IST) Conversion & Relative Time
        def format_ist_and_relative(dt):
            # IST is UTC + 5:30
            ist_dt = dt + datetime.timedelta(hours=5, minutes=30)
            
            # Relative time
            now = datetime.datetime.now(datetime.timezone.utc)
            diff = now - dt
            seconds = diff.total_seconds()
            
            if seconds < 0: rel = "Just now"
            elif seconds < 60: rel = f"{int(seconds)}s ago"
            elif seconds < 3600: rel = f"{int(seconds // 60)}m ago"
            elif seconds < 86400: rel = f"{int(seconds // 3600)}h ago"
            else: rel = f"{int(seconds // 86400)}d ago"
            
            return ist_dt.strftime('%d %b, %H:%M'), rel

        df[['Time (IST)', 'Relative Time']] = df.apply(
            lambda row: format_ist_and_relative(row['parsed_date']), 
            axis=1, result_type='expand'
        )

        # Render cards with expanders instead of a static table
        for _, row in df.iterrows():
            sentiment = str(row.get('sentiment', 'Neutral') or 'Neutral')
            sent_color = "#00D166" if sentiment == "Positive" else "#FF4B4B" if sentiment == "Negative" else "#94A3B8"
            
            # Individual Article Card
            with st.expander(f"🏢 **{row['company_name']}**: {row['title']}", expanded=False):
                col_a, col_b, col_c = st.columns([0.2, 0.6, 0.2])
                
                with col_a:
                    st.markdown(f"**Sentiment**")
                    st.markdown(f"<span style='color: {sent_color}; font-weight: bold;'>{sentiment.upper()}</span>", unsafe_allow_html=True)
                
                with col_b:
                    st.markdown(f"**Full Article Content**")
                    # Content can be raw HTML from RSS or clean text from Newspaper3k
                    raw_content = str(row.get('summary') or 'No content available.')
                    
                    # If it looks like HTML, strip it for a cleaner look
                    if '<' in raw_content and '>' in raw_content:
                        clean_text = BeautifulSoup(raw_content, "html.parser").get_text()
                    else:
                        clean_text = raw_content

                    # Use a text area or a scrollable container if the text is very long
                    if len(clean_text) > 1000:
                        st.text_area("Original Text", value=clean_text, height=300, disabled=True, label_visibility="collapsed")
                    else:
                        st.markdown(f"{clean_text}")
                
                with col_c:
                    st.markdown(f"**Details**")
                    st.write(f"Source: {row['source']}")
                    st.write(f"IST: {row['Time (IST)']}")
                    st.write(f"Relative: {row['Relative Time']}")
                
                st.markdown(f"<a href='{row['link']}' target='_blank' style='text-decoration: none; color: #4DA8DA;'>View Full Article 🔗</a>", unsafe_allow_html=True)

