import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import hashlib
import pandas as pd
from datetime import datetime
import os

# --- CONFIG & AUTH SETUP ---
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if os.path.exists("secrets.json"):
        creds = Credentials.from_service_account_file("secrets.json", scopes=scope)
        return gspread.authorize(creds)
    elif "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    return None

client = get_gspread_client()
if client:
    sheet = client.open("Hungry_Games_DB")
    user_wks = sheet.worksheet("Users")
    log_wks = sheet.worksheet("Logs")

def hash_pass(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

st.set_page_config(page_title="Hungry Games OS", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# --- AUTH FLOW ---
if not st.session_state['logged_in']:
    st.title("🛡️ HUNGRY GAMES: ACCESS CONTROL")
    choice = st.selectbox("Action", ["Login", "Register New Player"])
    if choice == "Register New Player":
        with st.form("Onboarding"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            h = st.number_input("Height (cm)", value=170)
            w = st.number_input("Weight (kg)", value=70.0)
            tw = st.number_input("Target Weight (kg)", value=65.0)
            if st.form_submit_button("Initialize Profile"):
                bmi = w / ((h/100)**2)
                team = "Team Loss" if bmi > 23 else "Team Gain"
                user_wks.append_row([u, hash_pass(p), 21, h, w, tw, 90, team, 0, 0, "None", 0])
                st.success(f"Welcome to {team}! Login to enter.")
    else:
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Enter Arena"):
            users = pd.DataFrame(user_wks.get_all_records())
            if u in users['username'].values and users[users['username'] == u]['password'].values[0] == hash_pass(p):
                st.session_state['logged_in'], st.session_state['user'] = True, u
                st.rerun()
            st.error("Invalid Credentials.")

# --- THE GAME DASHBOARD ---
else:
    user = st.session_state['user']
    users_df = pd.DataFrame(user_wks.get_all_records())
    me = users_df[users_df['username'] == user].iloc[0]

    st.sidebar.title(f"👋 Welcome, {user}!")
    st.sidebar.metric("Points", me['points'])
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        st.rerun()

    tabs = st.tabs(["🏆 Leaderboard", "🍽️ Log Meal", "⚖️ Jury Box"])

    with tabs[0]:
        st.header("The Leaderboard")
        st.dataframe(users_df[['username', 'points', 'team', 'streak']].sort_values(by='points', ascending=False), width='stretch')

    with tabs[1]:
        st.header("Meal Submission")
        meal_type = st.selectbox("Type", ["Photo Sent (50 pts)", "Text Only (10 pts)"])
        meal_desc = st.text_input("What did you eat?")
        if st.button("Submit"):
            pts = 50 if "Photo" in meal_type else 10
            log_wks.append_row([str(datetime.now()), user, meal_desc, pts, "Verified", 0])
            cell = user_wks.find(user)
            user_wks.update_cell(cell.row, 9, int(me['points']) + pts)
            st.success("Points Added!")
            st.rerun()

    with tabs[2]:
        st.header("⚖️ The Jury Box")
        st.write("Click a button to flag a suspicious entry. 3 flags = Penalty.")
        logs_df = pd.DataFrame(log_wks.get_all_records()).tail(10)
        
        for i, row in logs_df.iterrows():
            # Don't let users vote on their own meals
            if row['username'] != user:
                with st.expander(f"Audit: {row['username']} - {row['meal_type']}"):
                    col1, col2, col3 = st.columns(3)
                    if col1.button(f"🚨 JUNK!", key=f"j_{i}"):
                        st.error(f"Voted JUNK for {row['username']}")
                    if col2.button(f"📷 NO PHOTO!", key=f"p_{i}"):
                        st.warning("Flagged: Missing Photo")
                    if col3.button(f"👻 NO UPDATE!", key=f"u_{i}"):
                        st.info("Flagged: Ghost Log")
