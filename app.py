import streamlit as st
import requests
import re
import time
import pandas as pd

class ReverbListingCloner:
    def __init__(self, api_token):
        self.api_token = api_token
        self.base_url = "https://api.reverb.com/api"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/hal+json",
            "Accept": "application/hal+json",
            "Accept-Version": "3.0"
        }

    def get_slug_from_url(self, url):
        match = re.search(r'item/(\d+)', url)
        if match: return match.group(1)
        return None

    def fetch_listing(self, listing_id):
        try:
            response = requests.get(f"{self.base_url}/listings/{listing_id}", headers=self.headers)
            return response.json() if response.status_code == 200 else None
        except:
            return None

    def build_draft_payload(self, src, ship_id):
        try:
            amount_str = str(src.get("price", {}).get("amount", "0")).replace(",", "")
            new_price = float(amount_str) * 0.5
        except:
            new_price = 0.0
        
        payload = {
            "make": src.get("make"),
            "model": src.get("model"),
            "title": src.get("title"),
            "description": src.get("description"),
            "finish": src.get("finish"),
            "year": src.get("year"),
            "handmade": src.get("handmade", False),
            "offers_enabled": False, 
            "shipping_profile_id": int(ship_id),
            "price": {
                "amount": f"{new_price:.2f}",
                "currency": src.get("price", {}).get("currency", "USD")
            }
        }

        if src.get("categories"):
            payload["categories"] = [{"uuid": src["categories"][0].get("uuid")}]
        if src.get("condition"):
            payload["condition"] = {"uuid": src["condition"].get("uuid")}

        photo_urls = []
        if src.get("photos"):
            for p in src["photos"]:
                url = p.get("_links", {}).get("large_crop", {}).get("href") or \
                      p.get("_links", {}).get("full", {}).get("href")
                if url: photo_urls.append(url)
        payload["photos"] = photo_urls
        return payload

    def create_draft(self, payload):
        return requests.post(f"{self.base_url}/listings", headers=self.headers, json=payload)

    def publish_listing(self, listing_id):
        url = f"{self.base_url}/listings/{listing_id}"
        return requests.put(url, headers=self.headers, json={"publish": True})

# --- UI Setup ---
st.set_page_config(page_title="Reverb Cloner", layout="wide")

st.title("🎸")

# Step 1: Manual Input Form (Always asks for these)
with st.container():
    st.subheader("📋 Step 1: Setup & Source")
    col_a, col_b = st.columns(2)
    
    with col_a:
        api_token = st.text_input("🔑", type="password", help="🔑")
        ship_id = st.text_input("ID", placeholder="e.g. 123456")
    
    with col_b:
        url_input = st.text_area("URL", placeholder="URL 1, URL 2, URL 3...", help=",")

# Step 2: Processing Logic
if st.button("🚀"):
    if not api_token or not ship_id or not url_input:
        st.warning("F.")
    else:
        app = ReverbListingCloner(api_token)
        urls = [u.strip() for u in url_input.replace("\n", ",").split(",") if u.strip()]
        
        drafts_created = []
        progress = st.progress(0)
        
        for idx, url in enumerate(urls):
            listing_id = app.get_slug_from_url(url)
            if listing_id:
                data = app.fetch_listing(listing_id)
                if data:
                    payload = app.build_draft_payload(data, ship_id)
                    res = app.create_draft(payload)
                    if res.status_code in [200, 201, 202]:
                        new_id = res.json().get("id") or res.json().get("listing", {}).get("id")
                        drafts_created.append(new_id)
                        st.success(f"Draft Created: {new_id} (from {url})")
            
            progress.progress((idx + 1) / len(urls))
            time.sleep(1)

        if drafts_created:
            st.session_state['last_drafts'] = drafts_created
            st.info(f"Generated {len(drafts_created)} drafts. You can now publish them below.")

# Step 3: Final Publish
if 'last_drafts' in st.session_state and st.session_state['last_drafts']:
    st.divider()
    st.subheader("📢 Step 2: Publish to Live")
    
    if st.button("✅ YES, Publish All to LIVE"):
        app = ReverbListingCloner(api_token)
        st.write("Waiting 10s for image processing...")
        time.sleep(10)
        
        for d_id in st.session_state['last_drafts']:
            pub_res = app.publish_listing(d_id)
            if pub_res.status_code == 200:
                st.success(f"Listing {d_id} is now LIVE!")
            else:
                st.error(f"Failed to publish {d_id}")
        
        # Clear state so you don't accidentally double-publish
        st.session_state['last_drafts'] = []
