import streamlit as st
import requests
import pandas as pd
import subprocess
import time
import threading
import os
from datetime import datetime

# Log file path
LOG_FILE = 'psx_alert_log.csv'

# Load or initialize log DataFrame
if 'log_df' not in st.session_state:
    if os.path.exists(LOG_FILE):
        st.session_state.log_df = pd.read_csv(LOG_FILE)
    else:
        st.session_state.log_df = pd.DataFrame(columns=['timestamp', 'symbol', 'price', 'status'])

# Session state for monitoring
if 'monitoring' not in st.session_state:
    st.session_state.monitoring = False
if 'initial_sent' not in st.session_state:
    st.session_state.initial_sent = False

# Function to fetch current price
def get_price(symbol):
    try:
        url = "https://psxterminal.com/api/market-data?market=REG"
        response = requests.get(url)
        data = response.json()
        if data.get('success'):
            reg_data = data['data'].get('REG', {})
            if symbol in reg_data:
                return float(reg_data[symbol]['price'])
    except Exception as e:
        st.error(f"Error fetching price: {e}")
    return None

# Function to send message via Signal
def send_signal(from_num, to_num, message):
    cli_path = r"D:\signal-cli-0.13.18\bin\signal-cli.bat"
    cmd = f'"{cli_path}" -u {from_num} send {to_num} -m "{message}"'
    try:
        subprocess.run(cmd, shell=True, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        st.error(f"Failed to send Signal message: {e.stderr.decode()}")
        return False
    except Exception as e:
        st.error(f"Failed to send Signal message: {e}")
        return False

# Function to check condition and send alert if met
def check_condition_and_alert(symbol, condition, threshold, price, from_num, to_num):
    if price is not None:
        if (condition == ">=" and price >= threshold) or (condition == "<=" and price <= threshold):
            message = f"PSX Alert Triggered: {symbol} = {price:.2f} PKR ({condition} {threshold:.2f})"
            send_signal(from_num, to_num, message)
            return "Alert Triggered"
    return "No alert"

# Function to log the check
def log_check(symbol, price, status):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_row = pd.DataFrame([{'timestamp': timestamp, 'symbol': symbol, 'price': price, 'status': status}])
    st.session_state.log_df = pd.concat([st.session_state.log_df, new_row], ignore_index=True)
    st.session_state.log_df.to_csv(LOG_FILE, index=False)

# Background checker function
def background_checker(symbol, condition, threshold, from_num, to_num, interval_sec):
    while st.session_state.monitoring:
        price = get_price(symbol)
        if price is None:
            log_check(symbol, None, "Failed to fetch price")
        else:
            status = check_condition_and_alert(symbol, condition, threshold, price, from_num, to_num)
            log_check(symbol, price, status)
        time.sleep(interval_sec)

# Streamlit UI
st.title("PSX Stock Price Alert App")

symbol = st.text_input("Symbol")
condition = st.selectbox("Condition", [">=", "<="])
threshold = st.number_input("Threshold Price", min_value=0.0, format="%.2f")
from_num = st.text_input("Signal From number", help="e.g., +92300XXXXXXX")
to_num = st.text_input("Signal To number", help="e.g., +9665XXXXXXXX")
interval_options = {"1 hour": 3600, "3 hours": 10800, "6 hours": 21600}
interval = st.selectbox("Check Interval", list(interval_options.keys()), index=1)

all_inputs_filled = symbol and condition and threshold > 0 and from_num and to_num

if all_inputs_filled:
    if not st.session_state.initial_sent:
        price = get_price(symbol)
        if price is not None:
            message = f"PSX Initial Price: {symbol} = {price:.2f} PKR"
            if send_signal(from_num, to_num, message):
                st.session_state.initial_sent = True
                alert_status = check_condition_and_alert(symbol, condition, threshold, price, from_num, to_num)
                log_check(symbol, price, f"Initial check - {alert_status}")
                st.success("Initial message sent successfully.")
            else:
                st.error("Failed to send initial message.")
        else:
            st.error("Failed to fetch initial price.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Start Monitoring"):
            if not st.session_state.monitoring:
                st.session_state.monitoring = True
                interval_sec = interval_options[interval]
                thread = threading.Thread(target=background_checker, args=(symbol, condition, threshold, from_num, to_num, interval_sec))
                thread.daemon = True
                thread.start()
                st.success("Monitoring started.")
    with col2:
        if st.button("Stop Monitoring"):
            st.session_state.monitoring = False
            st.success("Monitoring stopped.")

    if st.button("Check Now"):
        price = get_price(symbol)
        if price is not None:
            message = f"PSX Current Price: {symbol} = {price:.2f} PKR"
            send_signal(from_num, to_num, message)
            alert_status = check_condition_and_alert(symbol, condition, threshold, price, from_num, to_num)
            log_check(symbol, price, f"Manual check - {alert_status}")
            st.success("Current price sent.")
        else:
            log_check(symbol, None, "Manual check - Failed to fetch price")
            st.error("Failed to fetch price.")

# Display logs
st.subheader("Logs")
st.dataframe(st.session_state.log_df)

# Download button
csv_data = st.session_state.log_df.to_csv(index=False).encode('utf-8')
st.download_button("Download Log CSV", data=csv_data, file_name="psx_alert_log.csv", mime='text/csv')
