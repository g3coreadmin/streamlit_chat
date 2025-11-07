import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv
import os
import requests
import time

# --- Load environment ---
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Chat by Lead", layout="centered")
st.title("💬 Chatbot (Lead-based Conversation)")

# ----------------------------------------------------------
# 1️⃣ Ask for LEAD ID once
# ----------------------------------------------------------
if "lead_id" not in st.session_state:
    with st.form("lead_validation"):
        lead_id_input = st.text_input("Enter your Lead ID (UUID format):")
        server_endpoint = st.text_input("Enter the server to receive the messages:")
        submitted = st.form_submit_button("Validate Lead")
        if (submitted) and (server_endpoint != ''):
            # Validate against Supabase leads table
            lead_check = supabase.table("leads").select("id").eq("id", lead_id_input).execute()
            if lead_check.data:
                st.session_state.lead_id = lead_id_input
                st.session_state.server_endpoint = server_endpoint
                st.success("✅ Lead validated successfully!")
                st.rerun()
            else:
                st.error("❌ Invalid Lead ID. Please try again.")
    st.stop()  # Stop app until validated

lead_id = st.session_state.lead_id
server_endpoint = st.session_state.server_endpoint
server_endpoint = server_endpoint + "/receive_message"

# ----------------------------------------------------------
# 2️⃣ Load conversation for this lead
# ----------------------------------------------------------
if "messages" not in st.session_state:
    response = (
        supabase.table("messages")
        .select("*")
        .eq("lead_id", lead_id)
        .order("created_at", desc=False)
        .execute()
    )
    st.session_state.messages = response.data if response.data else []

# ----------------------------------------------------------
# 3️⃣ Display conversation
# ----------------------------------------------------------
st.subheader(f"Conversation for Lead ID: `{lead_id}`")

for msg in st.session_state.messages:
    prefix = "🧑" if msg["role"] == "user" else "🤖"
    st.markdown(f"**{prefix} {msg['role'].capitalize()}:** {msg['content']}")

# ----------------------------------------------------------
# 4️⃣ Input field
# ----------------------------------------------------------
user_input = st.chat_input("Type your message...")

if user_input:
    # Save user message with lead_id
    new_msg = {"lead_id": lead_id, "role": "user", "content": user_input}
    supabase.table("messages").insert(new_msg).execute()
    st.session_state.messages.append(new_msg)

    # Call Flask API
    try:
        payload = {"message": user_input, "lead_id": lead_id}
        response = requests.post(server_endpoint, json=payload, timeout=50)
        if response.status_code == 200:
            bot_reply = response.json().get("reply", "✅ Flask API processed message.")
        else:
            bot_reply = f"❌ API error: {response.status_code}"
    except Exception as e:
        bot_reply = f"⚠️ Error contacting Flask API: {e}"

    # Save bot response with lead_id
    bot_msg = {"lead_id": lead_id, "role": "bot", "content": bot_reply}
    supabase.table("messages").insert(bot_msg).execute()
    st.session_state.messages.append(bot_msg)

    while True:
        time.sleep(5)
        
        response = (
        supabase.table("messages")
        .select("*")
        .eq("lead_id", lead_id)
        .order("created_at", desc=False)
        .execute()
    )
        st.session_state.messages = response.data if response.data else []
        for msg in st.session_state.messages:
            prefix = "🧑" if msg["role"] == "user" else "🤖"
            st.markdown(f"**{prefix} {msg['role'].capitalize()}:** {msg['content']}")

        st.rerun()