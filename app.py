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
    
    # Check for local file first (for your PC)
    if os.path.exists("secrets.json"):
        try:
            creds = Credentials.from_service_account_file("secrets.json", scopes=scope)
            return gspread.authorize(creds)
        except Exception as e:
            st.error(f"Local JSON File Error: {e}")
            return None
    
    # If no local file, try Streamlit Cloud secrets
    try:
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
            return gspread.authorize(creds)
    except Exception as e:
        st.error("Authentication Error: Could not find secrets.json locally or Cloud secrets.")
        return None

client = get_gspread_client()

# Only proceed if we connected successfully
if client:
    try:
        sheet = client.open("Hungry_Games_DB")
        user_wks = sheet.worksheet("Users")
        log_wks = sheet.worksheet("Logs")
    except Exception as e:
        st.error(f"Spreadsheet Error: Ensure the sheet name is 'Hungry_Games_DB' and you shared it with the bot email. Error: {e}")

def hash_pass(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# --- APP UI ---
st.set_page_config(page_title="Hungry Games OS", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# --- AUTHENTICATION FLOW ---
if not st.session_state['logged_in']:
    st.title("🛡️ HUNGRY GAMES: ACCESS CONTROL")
    choice = st.selectbox("Action", ["Login", "Register New Player"])

    if choice == "Register New Player":
        with st.form("Onboarding"):
            u = st.text_input("Choose Username")
            p = st.text_input("Set Password", type="password")
            h = st.number_input("Height (cm)", value=170)
            w = st.number_input("Weight (kg)", value=70.0)
            tw = st.number_input("Target Weight (kg)", value=65.0)
            days = st.number_input("Target Timeline (Days)", value=90)
            
            if st.form_submit_button("Initialize Profile"):
                bmi = w / ((h/100)**2)
                # Assignment logic: BMI > 23 is Team Loss (Toning), < 18.5 is Team Gain
                team = "Team Loss" if bmi > 23 else "Team Gain"
                
                try:
                    user_wks.append_row([u, hash_pass(p), 21, h, w, tw, days, team, 0, 0, "None", 0])
                    st.success(f"Profile Created! You are assigned to **{team}**. Now please select 'Login' above.")
                except Exception as e:
                    st.error(f"Registry Error: {e}")

    else:
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Enter Arena"):
            try:
                users = pd.DataFrame(user_wks.get_all_records())
                if not users.empty and u in users['username'].values:
                    db_p = users[users['username'] == u]['password'].values[0]
                    if db_p == hash_pass(p):
                        st.session_state['logged_in'] = True
                        st.session_state['user'] = u
                        st.rerun()
                st.error("Invalid Credentials.")
            except Exception as e:
                st.error(f"Login System Error: {e}")

# --- THE GAME DASHBOARD ---
else:
    user = st.session_state['user']
    users_df = pd.DataFrame(user_wks.get_all_records())
    me = users_df[users_df['username'] == user].iloc[0]

    st.sidebar.title(f"👋 Welcome, {user}!")
    st.sidebar.metric("Your Points", me['points'])
    st.sidebar.metric("Team", me['team'])
    
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        st.rerun()

    tabs = st.tabs(["🏆 Leaderboard", "🍽️ Log Meal", "⚖️ Jury Box"])

    with tabs[0]:
        st.header("The Leaderboard")
        leaderboard = users_df[['username', 'points', 'team', 'streak']].sort_values(by='points', ascending=False)
        st.dataframe(leaderboard, use_container_width=True)

    with tabs[1]:
        st.header("Meal Submission")
        meal_type = st.selectbox("What are you logging?", ["Photo Sent to WhatsApp (50 pts)", "Text Description Only (10 pts)"])
        meal_desc = st.text_input("Describe your meal (e.g., 'Dal Chawal + 2 Eggs')")
        
        if st.button("Submit to Registry"):
            pts = 50 if "Photo" in meal_type else 10
            log_wks.append_row([str(datetime.now()), user, meal_desc, pts, "Verified", 0])
            
            # Update user points in the main sheet
            cell = user_wks.find(user)
            new_pts = int(me['points']) + pts
            user_wks.update_cell(cell.row, 9, new_pts) # Col 9 is Points
            
            st.balloons()
            st.success(f"Success! {pts} points added to your score.")

    with tabs[2]:
        st.header("The Jury Box")
        st.write("Recent activity for auditing:")
        logs_df = pd.DataFrame(log_wks.get_all_records()).tail(10)
        st.table(logs_df)