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
        if submitted and server_endpoint != "":
            # Validate against Supabase leads table
            lead_check = (
                supabase.table("leads")
                .select("id")
                .eq("id", lead_id_input)
                .execute()
            )
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
# 2️⃣ Load conversation for this lead (first time only)
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

st.subheader(f"Conversation for Lead ID: `{lead_id}`")

# ----------------------------------------------------------
# 3️⃣ Display conversation using chat bubbles
# ----------------------------------------------------------
for msg in st.session_state.messages:
    # Map DB roles to Streamlit roles
    role = "user" if msg["role"] == "user" else "assistant"
    avatar = "🧑" if msg["role"] == "user" else "🤖"

    with st.chat_message(role, avatar=avatar):
        st.markdown(msg["content"])

# ----------------------------------------------------------
# 4️⃣ Input field (chat-style)
# ----------------------------------------------------------
user_input = st.chat_input("Type your message...")

if user_input:
    # --- 4.1 Save & show user message immediately ---
    new_msg = {"lead_id": lead_id, "role": "user", "content": user_input}
    supabase.table("messages").insert(new_msg).execute()
    st.session_state.messages.append(new_msg)

    # Show the user bubble (right side)
    with st.chat_message("user", avatar="🧑"):
        st.markdown(user_input)

    # --- 4.2 Show "loading" bubble for the bot ---
    with st.chat_message("assistant", avatar="🤖"):
        # --- 4.2 "Loading" enquanto o bot pensa ---
        status_placeholder = st.empty()
        status_placeholder.markdown("⌛ Pensando...")

        # --- 4.3 Call Flask API ---
        try:
            payload = {"message": user_input, "lead_id": lead_id}
            response = requests.post(server_endpoint, json=payload, timeout=50)

            if response.status_code == 200:
                data = response.json()
                reply = data.get("reply", "✅ Flask API processed message.")
            else:
                reply = f"❌ API error: {response.status_code}"
        except Exception as e:
            reply = f"⚠️ Error contacting Flask API: {e}"

        # Some o "Pensando..."
        status_placeholder.empty()

        # --- 4.4 Tratar múltiplos balões (novo formato) ---
        if isinstance(reply, list):
            # reply esperado: [{"text": "...", "delay": 1.8}, ...]
            for chunk in reply:
                text = chunk.get("text", "")
                delay = float(chunk.get("delay", 1.5))

                # espera antes do próximo balão (efeito humano)
                time.sleep(delay)

                # mostra um novo balão do bot
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(text)

                # salva cada balão como uma mensagem separada no histórico
                bot_msg = {"lead_id": lead_id, "role": "bot", "content": text}
                supabase.table("messages").insert(bot_msg).execute()
                st.session_state.messages.append(bot_msg)

        else:
            # fallback: resposta antiga em string única
            text = str(reply)
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(text)

            bot_msg = {"lead_id": lead_id, "role": "bot", "content": text}
            supabase.table("messages").insert(bot_msg).execute()
            st.session_state.messages.append(bot_msg)

        # Rerun so the full history is redrawn nicely
        st.rerun()

