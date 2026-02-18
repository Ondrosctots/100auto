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
        """Triggers the transition to live state."""
        url = f"{self.base_url}/listings/{listing_id}"
        payload = {"publish": True}
        response = requests.put(url, headers=self.headers, json=payload)
        
        # FIX: Reverb often returns 200/202 but the 'state' remains 'draft' for a few seconds.
        # We check the HTTP status code instead of the body's 'state' field.
        if 200 <= response.status_code < 300:
            return True, "Success"
        else:
            try:
                msg = response.json().get("message", "API Error")
            except:
                msg = f"Status {response.status_code}"
            return False, msg

# --- UI Setup ---
st.set_page_config(page_title="Reverb Cloner", page_icon="🎸", layout="wide")

st.title("🎸")

# Always ask for inputs
with st.container():
    st.subheader("📋 Step 1: Setup & Source")
    col_a, col_b = st.columns(2)
    
    with col_a:
        api_token = st.text_input("code", type="password")
        ship_id = st.text_input("ID", placeholder="e.g. 123456")
    
    with col_b:
        url_input = st.text_area("URL", placeholder=",...")

# Step 2: Processing Logic
if st.button("🚀"):
    if not api_token or not ship_id or not url_input:
        st.warning("Please fill in all fields.")
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
                        st.success(f"Draft Created: {new_id}")
            
            progress.progress((idx + 1) / len(urls))
            time.sleep(1)

        if drafts_created:
            st.session_state['last_drafts'] = drafts_created
            st.info(f"Generated {len(drafts_created)} drafts. Ready to publish.")

# Step 3: Final Publish
if 'last_drafts' in st.session_state and st.session_state['last_drafts']:
    st.divider()
    st.subheader("📢 Step 2: Live")
    
    if st.button("✅ YES, GO"):
        app = ReverbListingCloner(api_token)
        
        with st.spinner("Waiting 10s for images to process..."):
            time.sleep(10)
        
        for d_id in st.session_state['last_drafts']:
            success, message = app.publish_listing(d_id)
            if success:
                st.success(f"✅ Listing {d_id} update sent! It will appear live in a moment.")
            else:
                st.error(f"❌ Failed to publish {d_id}: {message}")
        
        # Reset state after finish
        st.session_state['last_drafts'] = []
