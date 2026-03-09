"""
Songkick Events Data Integration via BrightData

Data Source: Songkick Event Listings
URL: https://www.songkick.com/metro-areas/[city]
Access Method: BrightData Browser API (heavy JS handling + IP rotation)
Update Frequency: Dynamic (events change constantly)
Data Type: Time-dependent city properties

Metrics: events_score (int, 0-100), cultural_alignment (list of event types)
Description: Cultural scene quality score based on event density and user genre preferences.
Extracts artist names, venues, dates, and URLs from Songkick event listings.

Integration Status: ✅ READY - BrightData handles heavy JS and IP blocks
Implementation: Use BrightData Browser API to scrape Songkick event listings
"""

import json
import os
import asyncio
import random
import re
import time
import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging
from urllib.parse import urlencode
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# Load .env from repo root (override=True so .env wins over stale shell vars)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'), override=True)

logger = logging.getLogger(__name__)

# Module-level flags: set via CLI args
DEBUG_HTML = False  # --debug: save raw HTML for debugging
USE_LOCAL = False   # --local: use local Playwright browser instead of BrightData

# BrightData configuration (same pattern as Airbnb script)
AUTH = os.getenv("BRIGHTDATA_AUTH")
BR_ENDPOINT = os.getenv("BRIGHTDATA_ENDPOINT")

# Try to extract auth from endpoint if not provided directly
if not AUTH and BR_ENDPOINT and "@brd.superproxy.io" in BR_ENDPOINT:
    try:
        auth_part = BR_ENDPOINT.split("@")[0].replace("wss://", "")
        if auth_part.startswith("brd-customer-"):
            AUTH = auth_part
            logger.info(f"Extracted auth from endpoint: {AUTH[:20]}...")
    except Exception as e:
        logger.warning(f"Could not extract auth from endpoint: {e}")

# If no endpoint provided, generate from auth
if not BR_ENDPOINT and AUTH:
    BR_ENDPOINT = f"wss://{AUTH}@brd.superproxy.io:9222"

# Data directory - works whether called from API or directly
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

# Path to the JSON file storing metro area IDs
METRO_AREAS_FILE = os.path.join(DATA_DIR, 'sources', 'songkick_metro_areas.json')

def load_metro_areas() -> dict:
    """Load metro area IDs from JSON file"""
    try:
        if os.path.exists(METRO_AREAS_FILE):
            with open(METRO_AREAS_FILE, 'r') as f:
                data = json.load(f)
                return data.get('metro_areas', {})
        else:
            logger.info(f"Metro areas file not found, creating with initial data: {METRO_AREAS_FILE}")
    except Exception as e:
        logger.warning(f"Could not load metro areas file: {e}")
    
    # Return initial hardcoded data if file doesn't exist or can't be loaded
    initial_metro_areas = {
        "Berlin": "28443-germany-berlin",
        "London": "24426-uk-london", 
        "New York": "7644-us-new-york",
        "Paris": "28909-france-paris",
        "Amsterdam": "31366-netherlands-amsterdam",
        "Barcelona": "28714-spain-barcelona",
        "Rome": "28748-italy-rome",
        "Madrid": "28768-spain-madrid",
        "Vienna": "32252-austria-vienna",
        "Prague": "32627-czech-republic-prague",
        "Stockholm": "30379-sweden-stockholm",
        "Copenhagen": "30104-denmark-copenhagen",
        "Munich": "28755-germany-munich",
        "Brussels": "30276-belgium-brussels",
        "Dublin": "33377-ireland-dublin",
        "Lisbon": "31978-portugal-lisbon",
        "Zurich": "31841-switzerland-zurich",
        "Budapest": "32244-hungary-budapest",
        "Warsaw": "32446-poland-warsaw",
        "Athens": "30828-greece-athens",
        "Helsinki": "30820-finland-helsinki",
        "Oslo": "30604-norway-oslo"
    }
    
    # Save the initial data
    save_metro_areas(initial_metro_areas)
    return initial_metro_areas

def save_metro_areas(metro_areas: dict):
    """Save metro area IDs to JSON file"""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(METRO_AREAS_FILE), exist_ok=True)
        
        data = {
            "data_source": "Songkick Metro Areas",
            "description": "Metro area IDs discovered via web search and hardcoded initial values",
            "last_updated": datetime.now().isoformat(),
            "total_metro_areas": len(metro_areas),
            "metro_areas": metro_areas
        }
        
        with open(METRO_AREAS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
            
        logger.info(f"Saved {len(metro_areas)} metro areas to {METRO_AREAS_FILE}")
        
    except Exception as e:
        logger.error(f"Error saving metro areas: {e}")

def add_metro_area(city: str, metro_area_id: str):
    """Add a newly discovered metro area ID and save to file"""
    try:
        metro_areas = load_metro_areas()
        metro_areas[city] = metro_area_id
        save_metro_areas(metro_areas)
        logger.info(f"✅ Added new metro area: {city} -> {metro_area_id}")
    except Exception as e:
        logger.error(f"Error adding metro area for {city}: {e}")

async def find_songkick_metro_area(city: str) -> Optional[str]:
    """
    Find Songkick metro area ID for a city by searching the web for "songkick {city}"
    
    Args:
        city: City name to search for
        
    Returns:
        str: Metro area ID (e.g., "28443-germany-berlin") or None if not found
    """
    try:
        # Use Google search to find Songkick metro area pages
        search_query = f"songkick {city}"
        search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
        
        logger.info(f"Searching web for metro area ID for {city}: '{search_query}'")
        
        if not BR_ENDPOINT:
            raise ValueError("BrightData configuration missing. Set BRIGHTDATA_AUTH or BRIGHTDATA_ENDPOINT")
        
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(BR_ENDPOINT)
            try:
                page = await browser.new_page()
                
                # Block unnecessary resources for faster loading
                await page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,eot}", lambda route: route.abort())
                await page.route("**/analytics/**", lambda route: route.abort())
                await page.route("**/tracking/**", lambda route: route.abort())
                await page.route("**/ads/**", lambda route: route.abort())
                
                # Navigate to Google search
                await page.goto(search_url, timeout=20_000, wait_until='domcontentloaded')
                
                # Wait for search results
                await asyncio.sleep(3)
                
                # Get page content
                page_html = await page.content()
                
                # Parse with BeautifulSoup to find Songkick metro area links
                soup = BeautifulSoup(page_html, 'html.parser')
                
                # Look for links to Songkick metro areas in search results
                # Pattern: songkick.com/metro-areas/{ID}
                metro_area_pattern = r'songkick\.com/metro-areas/([\w-]+)'
                
                # Search in all links and text content
                all_links = soup.find_all('a', href=True)
                for link in all_links:
                    href = link.get('href', '')
                    match = re.search(metro_area_pattern, href)
                    if match:
                        metro_area_id = match.group(1)
                        logger.info(f"✅ Found metro area ID for {city}: {metro_area_id}")
                        return metro_area_id
                
                # Also search in page text content for any metro area URLs
                page_text = soup.get_text()
                match = re.search(metro_area_pattern, page_text)
                if match:
                    metro_area_id = match.group(1)
                    logger.info(f"✅ Found metro area ID for {city} in page text: {metro_area_id}")
                    return metro_area_id
                
                # If no metro area links found, log some debug info
                logger.warning(f"No Songkick metro area links found for {city}")
                songkick_links = [link.get('href') for link in all_links if 'songkick' in link.get('href', '')]
                logger.info(f"Found {len(songkick_links)} Songkick links: {songkick_links[:5]}")
                
                return None
                
            finally:
                await browser.close()
                
    except Exception as e:
        logger.error(f"Error finding metro area for {city}: {e}")
        return None

async def build_songkick_url(city: str, start_date: datetime, end_date: datetime, genre: Optional[str] = None) -> str:
    """
    Build Songkick search URL with proper parameters
    
    Args:
        city: City name to search events for
        start_date: Start date for event search  
        end_date: End date for event search
        genre: Optional genre filter (e.g., 'hip-hop', 'electronic')
        
    Returns:
        str: Formatted Songkick search URL
    """
    try:
        # Load metro areas from JSON file
        metro_areas = load_metro_areas()
        metro_area = metro_areas.get(city)
        
        # If not found, try to discover it dynamically
        if not metro_area:
            logger.info(f"City '{city}' not in cached metro areas, searching dynamically...")
            metro_area = await find_songkick_metro_area(city)
            
            if metro_area:
                # Save the newly discovered metro area
                add_metro_area(city, metro_area)
            else:
                raise ValueError(f"Could not find Songkick metro area for city '{city}'")
        
        # Base URL
        base_url = f"https://www.songkick.com/metro-areas/{metro_area}"
        
        # Add genre to URL path if specified
        if genre:
            genre_slug = genre.lower().replace(' ', '-')
            base_url = f"{base_url}/genre/{genre_slug}"
        
        # Format dates for Songkick (MM/DD/YYYY)
        start_str = start_date.strftime("%m/%d/%Y")
        end_str = end_date.strftime("%m/%d/%Y")
        
        # Build query parameters
        params = {
            'utf8': '✓',
            'filters[minDate]': start_str,
            'filters[maxDate]': end_str
        }
        
        # Build final URL
        search_url = f"{base_url}?{urlencode(params)}"
        
        return search_url
        
    except Exception as e:
        logger.error(f"Error building Songkick search URL: {e}")
        raise

async def fetch_songkick_events_brightdata(city: str, start_date: datetime, end_date: datetime, genre: Optional[str] = None, max_retries: int = 1) -> Dict:
    """
    Fetch Songkick events for a specific city using BrightData or local browser.

    Args:
        city: City name to fetch events for
        start_date: Start date for event search
        end_date: End date for event search
        genre: Optional genre filter
        max_retries: Maximum number of retry attempts

    Returns:
        Dict: Events data for the city
    """
    if not USE_LOCAL:
        if not BR_ENDPOINT:
            raise ValueError("BrightData configuration missing. Set BRIGHTDATA_AUTH or BRIGHTDATA_ENDPOINT, or use --local")
        if "brd.superproxy.io" not in BR_ENDPOINT:
            raise ValueError("Invalid BrightData endpoint format")

    target_url = await build_songkick_url(city, start_date, end_date, genre)
    logger.info(f"Target URL: {target_url}")

    # Start timing
    start_time = time.time()

    last_error = None

    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1}/{max_retries} for {city} events ({'local' if USE_LOCAL else 'brightdata'})")

            # Add jitter delay between attempts
            if attempt > 0:
                wait_time = (2 ** (attempt - 1)) + random.uniform(0, 1)
                logger.info(f"Waiting {wait_time:.2f}s before retry...")
                await asyncio.sleep(wait_time)

            step_start = time.time()
            async with async_playwright() as pw:
                if USE_LOCAL:
                    browser = await pw.chromium.launch(headless=True)
                else:
                    browser = await pw.chromium.connect_over_cdp(BR_ENDPOINT)
                try:
                    # Configure page for faster loading
                    page = await browser.new_page()
                    
                    # Block unnecessary resources to speed up loading
                    await page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,eot}", lambda route: route.abort())
                    await page.route("**/analytics/**", lambda route: route.abort())
                    await page.route("**/tracking/**", lambda route: route.abort())
                    await page.route("**/ads/**", lambda route: route.abort())
                    await page.route("**/facebook.com/**", lambda route: route.abort())
                    await page.route("**/google-analytics.com/**", lambda route: route.abort())
                    await page.route("**/googletagmanager.com/**", lambda route: route.abort())
                    await page.route("**/doubleclick.net/**", lambda route: route.abort())
                    
                    # Navigate to Songkick events page with shorter timeout
                    nav_start = time.time()
                    await page.goto(target_url, timeout=25_000, wait_until='domcontentloaded')
                    nav_time = time.time() - nav_start
                    logger.info(f"⏱️ Page navigation took {nav_time:.2f}s")
                
                    logger.info(f"Page loaded for {city}, waiting for events...")
                    
                    # Wait for the specific content we need instead of fixed delays
                    js_start = time.time()
                    
                    # Get page title and URL to check if we're on the right page
                    page_title = await page.title()
                    current_url = page.url
                    logger.info(f"Page title: '{page_title}', Current URL: {current_url}")
                    
                    # Wait specifically for event wrapper elements to appear
                    try:
                        await page.wait_for_selector('.artists-venue-location-wrapper', timeout=10_000)
                        logger.info(f"✅ Event elements loaded")
                    except:
                        logger.warning(f"⚠️ Event elements not detected, proceeding anyway")
                    
                    # Small additional wait for any dynamic content
                    await asyncio.sleep(0.5)
                    js_time = time.time() - js_start
                    
                    # Extract all event data at once using HTML parsing
                    parse_start = time.time()
                    
                    # Get the raw HTML content once
                    page_html = await page.content()
                    
                    # Save HTML for debugging (only with --debug flag)
                    if DEBUG_HTML:
                        save_html_for_debugging(page_html, city, genre)
                    
                    # Fallback date range (only used when JSON-LD has no date)
                    if start_date == end_date:
                        fallback_date = start_date.strftime('%Y-%m-%d')
                    else:
                        fallback_date = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"

                    # Parse all events using BeautifulSoup (much more reliable than regex)
                    soup = BeautifulSoup(page_html, 'html.parser')

                    # Extract JSON-LD performer data for genre/ID enrichment
                    jsonld_performers = parse_jsonld_performers(soup)
                    logger.info(f"Extracted JSON-LD data for {len(jsonld_performers)} events")

                    # Extract JSON-LD event dates (specific per event)
                    jsonld_dates = parse_jsonld_dates(soup)
                    logger.info(f"Extracted JSON-LD dates for {len(jsonld_dates)} events")

                    event_wrappers = soup.find_all('div', class_='artists-venue-location-wrapper')
                    
                    logger.info(f"Found {len(event_wrappers)} events using BeautifulSoup parsing")
                    
                    if len(event_wrappers) == 0:
                        # Check if we got a real page (has the metro area title)
                        # vs a blocked/error page that should trigger a retry
                        if 'Concerts, Festivals' in (page_title or ''):
                            # Legitimate empty page — city just has no events for this date
                            logger.info(f"No events found for {city} on this date (valid empty page)")
                        else:
                            sample_html = page_html[:500] if page_html else "No HTML content"
                            logger.info(f"Sample HTML: {sample_html}")
                            raise ValueError(f"No events found on Songkick page for {city} (possibly blocked)")
                    
                    events = []
                    logger.info(f"Processing {len(event_wrappers)} events...")
                    parse_time = time.time() - parse_start
                    
                    extraction_start = time.time()
                    
                    for i, wrapper in enumerate(event_wrappers):
                        try:
                            # Extract artist name from .artists strong
                            artist_element = wrapper.find('p', class_='artists')
                            artist_name = ''
                            if artist_element:
                                strong_element = artist_element.find('strong')
                                if strong_element:
                                    artist_name = strong_element.get_text().strip()
                            
                            if not artist_name:
                                continue
                            
                            # Extract event URL from .artists .event-link
                            event_url = ''
                            if artist_element:
                                event_link = artist_element.find('a', class_='event-link')
                                if event_link and event_link.get('href'):
                                    href = event_link.get('href')
                                    if href.startswith('/'):
                                        event_url = f"https://www.songkick.com{href}"
                                    else:
                                        event_url = href
                            
                            # Extract venue name and URL from .location .venue-link
                            venue_name = ''
                            venue_url = ''
                            location_element = wrapper.find('p', class_='location')
                            if location_element:
                                venue_link = location_element.find('a', class_='venue-link')
                                if venue_link:
                                    venue_name = venue_link.get_text().strip()
                                    if venue_link.get('href'):
                                        venue_href = venue_link.get('href')
                                        if venue_href.startswith('/'):
                                            venue_url = f"https://www.songkick.com{venue_href}"
                                        else:
                                            venue_url = venue_href
                            
                            # Match against JSON-LD data for genre/ID enrichment
                            sk_id = None
                            sk_genres = []
                            if event_url:
                                url_path = event_url.replace('https://www.songkick.com', '')
                                ld_performers = jsonld_performers.get(url_path, [])
                                # Find matching performer by name (first performer is headline)
                                for perf in ld_performers:
                                    if perf['name'].lower() == artist_name.lower() or len(ld_performers) == 1:
                                        sk_id = perf.get('songkick_id')
                                        sk_genres = perf.get('genres', [])
                                        break
                                # Fallback: use first performer's data if no name match
                                if not sk_id and ld_performers:
                                    sk_id = ld_performers[0].get('songkick_id')
                                    sk_genres = ld_performers[0].get('genres', [])

                            # Debug: Log first few events
                            if i < 5:
                                genre_str = f" [{', '.join(sk_genres)}]" if sk_genres else ""
                                logger.info(f"Event {i}: {artist_name} @ {venue_name or 'TBD'}{genre_str}")

                            # Get actual event date from JSON-LD (specific per event)
                            actual_date = fallback_date
                            if event_url:
                                url_path = event_url.replace('https://www.songkick.com', '')
                                ld_date = jsonld_dates.get(url_path, '')
                                if ld_date:
                                    actual_date = ld_date

                            # Create event entry
                            event = {
                                'artist': artist_name,
                                'venue': venue_name or 'TBD',
                                'venue_url': venue_url,
                                'event_url': event_url,
                                'date': actual_date,
                                'genre': genre or 'mixed',
                                'source': 'songkick',
                                'songkick_artist_id': sk_id,
                                'songkick_genres': sk_genres,
                            }
                            
                            events.append(event)
                            
                        except Exception as e:
                            logger.warning(f"Error processing event {i}: {e}")
                            continue
                    
                    extraction_time = time.time() - extraction_start
                    
                    # Create final result
                    events_data = {
                        'city': city,
                        'start_date': start_date.strftime('%Y-%m-%d'),
                        'end_date': end_date.strftime('%Y-%m-%d'),
                        'genre_filter': genre,
                        'total_events': len(events),
                        'events': events,
                        'source_url': target_url,
                        'scraped_at': datetime.now().isoformat()
                    }
                    
                    total_time = time.time() - start_time
                    logger.info(f"✅ Extracted {len(events)} events for {city} ({genre or 'all genres'}) in {total_time:.1f}s")
                    
                    return events_data
                    
                finally:
                    await browser.close()
                
        except Exception as e:
            last_error = e
            logger.error(f"Attempt {attempt + 1} failed for {city}: {e}")
            
            if attempt == max_retries - 1:
                logger.error(f"All {max_retries} attempts failed for {city}")
                raise last_error
    
    raise last_error or Exception(f"Failed to fetch events for {city}")

def load_existing_events_data(output_path: str = None) -> List[Dict]:
    """
    Load existing events data from JSON file
    
    Args:
        output_path: Path to the JSON file
        
    Returns:
        List[Dict]: Existing events data or empty list if file doesn't exist
    """
    if output_path is None:
        output_path = os.path.join(DATA_DIR, 'sources', 'songkick_bandsintown_events.json')
    try:
        if os.path.exists(output_path):
            with open(output_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                existing_events = data.get('events_data', [])
                if existing_events is None:
                    existing_events = []
                # Filter out any None entries
                existing_events = [event for event in existing_events if event is not None]
                logger.info(f"📂 Loaded {len(existing_events)} existing event searches from {output_path}")
                return existing_events
        else:
            logger.info(f"📂 No existing events file found at {output_path}")
            return []
    except Exception as e:
        logger.error(f"Error loading existing events data: {e}")
        return []

def save_events_data(data: List[Dict], output_path: str = None):
    """
    Save events data to JSON file
    
    Args:
        data: Events data
        output_path: Output file path
    """
    if output_path is None:
        output_path = os.path.join(DATA_DIR, 'sources', 'songkick_bandsintown_events.json')
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Create output structure
        output_data = {
            "data_source": "Songkick Events via BrightData",
            "url": "https://www.songkick.com/",
            "last_updated": datetime.now().isoformat(),
            "description": "Live music events and concerts data",
            "method": "BrightData Browser API with IP rotation",
            "total_searches": len(data),
            "events_data": data
        }
        
        # Save to file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
            
        logger.info(f"💾 Saved {len(data)} event searches to {output_path}")
        
    except Exception as e:
        logger.error(f"Error saving events data: {e}")
        raise

def append_events_data(new_data: Dict, output_path: str = None):
    """
    Append new events data to existing JSON file
    
    Args:
        new_data: New events data for a single city
        output_path: Output file path
    """
    if output_path is None:
        output_path = os.path.join(DATA_DIR, 'sources', 'songkick_bandsintown_events.json')
    try:
        logger.info(f"💾 Appending events data for {new_data['city']} to {output_path}")
        
        # Load existing data
        existing_events = load_existing_events_data(output_path)
        if existing_events is None:
            existing_events = []
        
        # Filter out any None entries
        existing_events = [event for event in existing_events if event is not None]
        
        logger.info(f"📂 Currently have {len(existing_events)} existing event searches")
        
        # Check if city already exists for this date
        city = new_data['city']
        start_date = new_data['start_date']
        genre = new_data.get('genre_filter')
        
        # Remove any existing entry for the same city, date, and genre
        original_count = len(existing_events)
        existing_events = [
            event for event in existing_events 
            if not (event.get('city') == city and 
                   event.get('start_date') == start_date and 
                   event.get('genre_filter') == genre)
        ]
        
        if len(existing_events) < original_count:
            logger.info(f"🔄 Removed {original_count - len(existing_events)} existing entries for {city}")
        
        # Add the new data
        existing_events.append(new_data)
        logger.info(f"➕ Added new entry for {city}, total entries: {len(existing_events)}")
        
        # Save all data
        save_events_data(existing_events, output_path)
        
        logger.info(f"✅ Successfully appended events for {city} ({new_data['total_events']} events)")
        
    except Exception as e:
        logger.error(f"Error appending events data: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise

def parse_jsonld_performers(soup) -> dict:
    """Parse JSON-LD from Songkick page and extract performer genre/ID info.

    Args:
        soup: BeautifulSoup object of the page

    Returns:
        dict keyed by event URL path → list of performer dicts
        {name, songkick_id, genres}
    """
    scripts = soup.find_all('script', type='application/ld+json')
    events_by_url: dict = {}

    for script in scripts:
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            continue

        items = data if isinstance(data, list) else [data]

        for item in items:
            if item.get('@type') != 'MusicEvent':
                continue

            event_url = (item.get('url') or '').split('?')[0]
            if not event_url:
                continue

            # Extract URL path for matching against HTML-parsed events
            url_path = event_url.replace('https://www.songkick.com', '')

            performers_data = item.get('performer', [])
            if not isinstance(performers_data, list):
                performers_data = [performers_data]

            performers = []
            for performer in performers_data:
                name = (performer.get('name') or '').strip()
                if not name:
                    continue

                genres = performer.get('genre', [])
                if isinstance(genres, str):
                    genres = [genres] if genres else []

                same_as = performer.get('sameAs') or ''
                sk_id = None
                if 'songkick.com/artists/' in same_as:
                    match = re.search(r'/artists/(\d+)', same_as)
                    if match:
                        sk_id = match.group(1)

                performers.append({
                    'name': name,
                    'songkick_id': sk_id,
                    'genres': genres,
                })

            if performers:
                events_by_url[url_path] = performers

    return events_by_url


def parse_jsonld_dates(soup) -> dict:
    """Extract startDate per event URL path from JSON-LD MusicEvent data.

    Returns:
        dict: {event_url_path: startDate_str}
              e.g. {"/concerts/123-foo": "2026-05-03T18:30:00"}
    """
    scripts = soup.find_all('script', type='application/ld+json')
    dates_by_url = {}

    for script in scripts:
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            continue

        items = data if isinstance(data, list) else [data]
        for item in items:
            if item.get('@type') != 'MusicEvent':
                continue
            event_url = (item.get('url') or '').split('?')[0]
            start_date = item.get('startDate', '')
            if event_url and start_date:
                url_path = event_url.replace('https://www.songkick.com', '')
                dates_by_url[url_path] = start_date

    return dates_by_url


def save_html_for_debugging(html_content: str, city: str, genre: str = None):
    """Save HTML content to file for debugging"""
    try:
        debug_dir = os.path.join(DATA_DIR, 'debug_html')
        os.makedirs(debug_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        genre_suffix = f"_{genre}" if genre else ""
        filename = f"songkick_{city.lower()}{genre_suffix}_{timestamp}.html"
        filepath = os.path.join(debug_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        logger.info(f"💾 Saved HTML for debugging: {filepath}")
        return filepath
        
    except Exception as e:
        logger.error(f"Failed to save HTML: {e}")
        return None

async def process_city_with_semaphore(semaphore: asyncio.Semaphore, city: str, start_date: datetime, end_date: datetime) -> bool:
    """
    Process a single city with semaphore control for concurrency limiting

    Args:
        semaphore: Asyncio semaphore for controlling concurrency
        city: City name to process
        start_date: Start date for event search
        end_date: End date for event search

    Returns:
        bool: True if successful, False if failed
    """
    async with semaphore:
        try:
            logger.info(f"🎵 Starting events fetch for {city}")

            # Double-check if city was already processed (safety check)
            if city_already_processed(city, start_date, end_date):
                logger.info(f"⏭️ Skipping {city} - already processed for {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
                return True

            # In local mode, add a polite delay to avoid rate limiting
            if USE_LOCAL:
                delay = random.uniform(2, 5)
                logger.info(f"⏳ Local mode: waiting {delay:.1f}s before fetching {city}")
                await asyncio.sleep(delay)

            # Fetch events for the city (3 attempts = 1 initial + 2 retries)
            events_data = await fetch_songkick_events_brightdata(city, start_date, end_date, max_retries=3)

            logger.info(f"📊 Fetched {events_data['total_events']} events for {city}, now saving...")

            # Append to existing data
            append_events_data(events_data)

            logger.info(f"✅ Completed and saved {city}: {events_data['total_events']} events")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to process {city}: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False

def city_already_processed(city: str, start_date: datetime, end_date: datetime, genre: Optional[str] = None) -> bool:
    """
    Check if a city has already been processed for a specific date range and genre

    Args:
        city: City name to check
        start_date: Start date to check
        end_date: End date to check
        genre: Genre filter to check (None for all genres)

    Returns:
        bool: True if already processed, False otherwise
    """
    try:
        existing_events = load_existing_events_data()
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')

        for event in existing_events:
            if (event and
                event.get('city') == city and
                event.get('start_date') == start_str and
                event.get('end_date') == end_str and
                event.get('genre_filter') == genre):
                return True

        return False

    except Exception as e:
        logger.error(f"Error checking if city already processed: {e}")
        return False

def load_cities() -> List[str]:
    """
    Load all cities from the production CSV file

    Returns:
        List[str]: List of unique city names
    """
    try:
        df = pd.read_csv(os.path.join(DATA_DIR, 'production', 'cities.csv'))

        # Get unique cities and clean up the names
        cities = df['city'].str.strip().unique().tolist()

        # Filter out problematic city names
        filtered_cities = []
        for city in cities:
            if city and len(city) > 2 and not any(char in city for char in ['/', '\\', '(', ')']):
                filtered_cities.append(city)

        # Skip cities with no metro area mapping (they'll always fail)
        metro_areas = load_metro_areas()
        mapped_cities = [c for c in filtered_cities if c in metro_areas]
        skipped = len(filtered_cities) - len(mapped_cities)
        if skipped:
            logger.info(f"📍 Skipping {skipped} cities with no Songkick metro mapping")

        logger.info(f"📍 Loaded {len(mapped_cities)} scrapeable cities from production CSV")
        return sorted(mapped_cities)

    except Exception as e:
        logger.error(f"Error loading cities: {e}")
        raise

async def main():
    """
    Fetch Songkick events for all cities in the production dataset.
    Supports --start / --end CLI args for the date range.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Fetch Songkick events for all cities")
    parser.add_argument("--start", default="2026-02-07", help="Start date YYYY-MM-DD (default: 2026-02-07)")
    parser.add_argument("--end", default="2026-02-28", help="End date YYYY-MM-DD (default: 2026-02-28)")
    parser.add_argument("--concurrent", type=int, default=5, help="Max concurrent requests (default: 5)")
    parser.add_argument("--debug", action="store_true", help="Save raw HTML to data/debug_html/ for debugging")
    parser.add_argument("--local", action="store_true", help="Use local Playwright browser instead of BrightData (free, slower)")
    parser.add_argument("--cities", help="Comma-separated list of cities to scrape (default: all mapped cities)")
    parser.add_argument("--exclude-cities", help="Comma-separated list of cities to exclude")
    args = parser.parse_args()

    # Set module-level flags
    global DEBUG_HTML, USE_LOCAL
    DEBUG_HTML = args.debug
    USE_LOCAL = args.local

    if USE_LOCAL:
        logger.info("🖥️ Using local browser (no BrightData)")


    start_date = datetime.strptime(args.start, "%Y-%m-%d")
    end_date = datetime.strptime(args.end, "%Y-%m-%d")
    max_concurrent = args.concurrent

    try:
        logger.info(f"🎵 Starting Songkick events fetching for {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        logger.info(f"⚡ Max concurrent requests: {max_concurrent}")

        # Load cities (optionally filtered by --cities / --exclude-cities)
        if args.cities:
            cities = [c.strip() for c in args.cities.split(',')]
            logger.info(f"📍 Using {len(cities)} cities from --cities flag")
        else:
            cities = load_cities()
            if args.exclude_cities:
                exclude = {c.strip() for c in args.exclude_cities.split(',')}
                cities = [c for c in cities if c not in exclude]
                logger.info(f"📍 Excluded {len(exclude)} cities, {len(cities)} remaining")
        logger.info(f"📍 Processing {len(cities)} cities")

        # Load existing data to check what we already have
        existing_events = load_existing_events_data()
        if existing_events is None:
            existing_events = []

        # Filter out any None entries
        existing_events = [event for event in existing_events if event is not None]

        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')

        existing_cities = set()
        for event in existing_events:
            if (event and
                event.get('start_date') == start_str and
                event.get('end_date') == end_str):
                existing_cities.add(event.get('city'))

        # Filter out cities we already have data for
        cities_to_process = [city for city in cities if city not in existing_cities]

        if existing_cities:
            logger.info(f"📂 Skipping {len(existing_cities)} cities with existing data for {start_str} to {end_str}:")
            skipped_cities = sorted(list(existing_cities))
            for city in skipped_cities[:10]:
                logger.info(f"   • {city}")
            if len(skipped_cities) > 10:
                logger.info(f"   ... and {len(skipped_cities) - 10} more cities")

        if not cities_to_process:
            logger.info("✅ All cities already have data for the target date range!")
            return existing_events

        logger.info(f"🚀 Processing {len(cities_to_process)} remaining cities:")
        cities_to_show = sorted(cities_to_process)
        for city in cities_to_show[:10]:
            logger.info(f"   • {city}")
        if len(cities_to_show) > 10:
            logger.info(f"   ... and {len(cities_to_show) - 10} more cities")

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)

        # Create tasks for all cities
        tasks = []
        for city in cities_to_process:
            task = process_city_with_semaphore(semaphore, city, start_date, end_date)
            tasks.append(task)

        # Process all cities with progress tracking
        run_start = time.time()
        completed_count = 0
        failed_count = 0

        logger.info(f"⏳ Starting parallel processing of {len(tasks)} cities...")

        # Process in batches to avoid overwhelming the system
        batch_size = 20
        for i in range(0, len(tasks), batch_size):
            batch_tasks = tasks[i:i + batch_size]
            batch_cities = cities_to_process[i:i + batch_size]

            logger.info(f"📦 Processing batch {i//batch_size + 1}/{(len(tasks) + batch_size - 1)//batch_size}: {batch_cities[0]} to {batch_cities[-1]}")

            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    failed_count += 1
                elif result:
                    completed_count += 1
                else:
                    failed_count += 1

            total_processed = completed_count + failed_count
            elapsed_time = time.time() - run_start
            avg_time_per_city = elapsed_time / total_processed if total_processed > 0 else 0
            estimated_remaining = avg_time_per_city * (len(tasks) - total_processed)

            logger.info(f"📊 Progress: {total_processed}/{len(tasks)} cities processed")
            logger.info(f"✅ Successful: {completed_count}, ❌ Failed: {failed_count}")
            logger.info(f"⏱️ Elapsed: {elapsed_time:.1f}s, Est. remaining: {estimated_remaining:.1f}s")

            if i + batch_size < len(tasks):
                await asyncio.sleep(2)

        total_time = time.time() - run_start

        logger.info(f"🎉 Completed processing all cities!")
        logger.info(f"✅ Successful: {completed_count}/{len(tasks)} cities")
        logger.info(f"❌ Failed: {failed_count}/{len(tasks)} cities")
        logger.info(f"⏱️ Total time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
        logger.info(f"📈 Average time per city: {total_time/len(tasks):.1f}s")

        final_events = load_existing_events_data()
        logger.info(f"💾 Final dataset contains {len(final_events)} event searches")

        return final_events

    except Exception as e:
        logger.error(f"Failed to fetch Songkick events: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
