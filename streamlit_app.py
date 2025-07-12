import streamlit as st
import paho.mqtt.client as mqtt
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
from collections import deque
import threading
import os

# Page configuration
st.set_page_config(
    page_title="Energy Monitor - LoRaWAN",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for mobile-friendly design
st.markdown("""
<style>
    .stApp {
        background-color: #0a0e27;
    }
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 15px;
        padding: 20px;
        backdrop-filter: blur(10px);
    }
    div[data-testid="metric-container"] {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }
    .stButton > button {
        background-color: #4facfe;
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 5px;
        font-weight: bold;
    }
    .stButton > button:hover {
        background-color: #00f2fe;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'mqtt_connected' not in st.session_state:
    st.session_state.mqtt_connected = False
    st.session_state.latest_data = {
        'voltage': 0,
        'current': 0,
        'power': 0,
        'frequency': 0,
        'powerFactor': 0,
        'energy': 0,
        'dailyKwh': 0,
        'dailyCost': 0,
        'timestamp': datetime.now(),
        'rssi': 0,
        'snr': 0,
        'devEUI': '--',
        'gateway': '--'
    }
    st.session_state.history = deque(maxlen=100)
    st.session_state.mqtt_client = None
    st.session_state.data_received = False

# MQTT Configuration from secrets or environment
try:
    # Try Streamlit secrets first (for deployment)
    MQTT_BROKER = st.secrets["mqtt"]["broker"]
    MQTT_PORT = st.secrets["mqtt"]["port"]
    MQTT_USERNAME = st.secrets["mqtt"].get("username", "")
    MQTT_PASSWORD = st.secrets["mqtt"].get("password", "")
except:
    # Fall back to environment variables or defaults
    MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
    MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
    MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
    MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

MQTT_TOPIC = "application/1/device/9fb27692fb0c2381/event/up"

# MQTT Callbacks
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        st.session_state.mqtt_connected = True
        client.subscribe(MQTT_TOPIC)
        print(f"Connected to MQTT broker and subscribed to {MQTT_TOPIC}")
    else:
        st.session_state.mqtt_connected = False
        print(f"Failed to connect, return code {rc}")

def on_disconnect(client, userdata, rc):
    st.session_state.mqtt_connected = False
    print("Disconnected from MQTT broker")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        
        # Extract device info
        if 'devEUI' in payload:
            st.session_state.latest_data['devEUI'] = payload['devEUI']
        
        # Extract signal info
        if 'rxInfo' in payload and len(payload['rxInfo']) > 0:
            rxInfo = payload['rxInfo'][0]
            st.session_state.latest_data['rssi'] = rxInfo.get('rssi', 0)
            st.session_state.latest_data['snr'] = rxInfo.get('loRaSNR', 0)
            st.session_state.latest_data['gateway'] = rxInfo.get('name', rxInfo.get('gatewayID', '--'))
        
        # Extract object data
        if 'object' in payload:
            obj = payload['object']
            st.session_state.latest_data.update({
                'voltage': obj.get('voltage', 0),
                'current': obj.get('current', 0),
                'power': obj.get('power', 0),
                'frequency': obj.get('frequency', 0),
                'powerFactor': obj.get('powerFactor', 0),
                'energy': obj.get('energy', 0),
                'dailyKwh': obj.get('dailyKwh', 0),
                'dailyCost': obj.get('dailyCost', 0),
                'timestamp': datetime.now()
            })
            
            # Add to history
            st.session_state.history.append({
                'timestamp': datetime.now(),
                'power': obj.get('power', 0),
                'voltage': obj.get('voltage', 0),
                'current': obj.get('current', 0)
            })
            
            st.session_state.data_received = True
            
    except Exception as e:
        print(f"Error processing message: {e}")

# Connect to MQTT
def init_mqtt():
    if st.session_state.mqtt_client is None:
        client = mqtt.Client()
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        client.on_message = on_message
        
        # Set credentials if provided
        if MQTT_USERNAME and MQTT_PASSWORD:
            client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            client.loop_start()
            st.session_state.mqtt_client = client
            return True
        except Exception as e:
            st.error(f"Failed to connect to MQTT broker: {e}")
            return False
    return True

# Sidebar for configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Show current configuration
    st.info(f"""
    **MQTT Configuration:**
    - Broker: `{MQTT_BROKER}:{MQTT_PORT}`
    - Topic: `{MQTT_TOPIC}`
    - Status: {'🟢 Connected' if st.session_state.mqtt_connected else '🔴 Disconnected'}
    """)
    
    # Manual configuration option
    if st.button("🔄 Reconnect MQTT"):
        if st.session_state.mqtt_client:
            st.session_state.mqtt_client.loop_stop()
            st.session_state.mqtt_client.disconnect()
            st.session_state.mqtt_client = None
        init_mqtt()
    
    st.divider()
    
    # Instructions
    st.markdown("""
    ### 📱 Mobile App Install:
    1. Open this page in Chrome/Safari
    2. Tap menu (⋮ or Share button)
    3. Select "Add to Home Screen"
    
    ### 🔧 MQTT Setup:
    Configure your MQTT broker to be accessible from the internet using:
    - Port forwarding
    - ngrok
    - Cloud MQTT service
    """)

# Initialize MQTT connection
mqtt_connected = init_mqtt()

# Main Dashboard
st.markdown("# ⚡ Energy Monitoring System")

# Connection status bar
col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
with col1:
    st.markdown(f"**Device EUI:** `{st.session_state.latest_data['devEUI']}`")
with col2:
    st.markdown(f"**Gateway:** {st.session_state.latest_data['gateway']}")
with col3:
    status = "🟢 Connected" if st.session_state.mqtt_connected else "🔴 Disconnected"
    st.markdown(f"**MQTT:** {status}")
with col4:
    if st.button("🔄 Refresh"):
        st.rerun()

st.divider()

# Auto-refresh container
placeholder = st.empty()
chart_placeholder = st.empty()

# Main loop
refresh_rate = st.sidebar.slider("Refresh Rate (seconds)", 1, 10, 2)

while True:
    with placeholder.container():
        # Check if we have received any data
        if not st.session_state.data_received:
            st.warning("⏳ Waiting for data from device...")
            st.info(f"""
            **Troubleshooting:**
            - Ensure your LoRaWAN device is powered on and transmitting
            - Check if MQTT broker is accessible: `{MQTT_BROKER}:{MQTT_PORT}`
            - Verify the topic is correct: `{MQTT_TOPIC}`
            - Check device EUI: `9fb27692fb0c2381`
            """)
        else:
            # Main metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    label="⚡ Voltage",
                    value=f"{st.session_state.latest_data['voltage']:.1f} V",
                    delta=f"{st.session_state.latest_data['voltage'] - 220:.1f} V" if st.session_state.latest_data['voltage'] > 0 else None
                )
            
            with col2:
                st.metric(
                    label="🔌 Current",
                    value=f"{st.session_state.latest_data['current']:.2f} A",
                )
            
            with col3:
                st.metric(
                    label="💡 Power",
                    value=f"{st.session_state.latest_data['power']:.0f} W",
                )
            
            with col4:
                st.metric(
                    label="📊 Power Factor",
                    value=f"{st.session_state.latest_data['powerFactor']:.2f}",
                )
            
            # Second row of metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    label="〰️ Frequency",
                    value=f"{st.session_state.latest_data['frequency']:.1f} Hz",
                )
            
            with col2:
                st.metric(
                    label="⚡ Total Energy",
                    value=f"{st.session_state.latest_data['energy']:.3f} kWh",
                )
            
            with col3:
                st.metric(
                    label="📅 Daily Usage",
                    value=f"{st.session_state.latest_data['dailyKwh']:.3f} kWh",
                )
            
            with col4:
                st.metric(
                    label="💰 Daily Cost",
                    value=f"₱{st.session_state.latest_data['dailyCost']:.2f}",
                )
            
            # Signal quality
            st.divider()
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                rssi = st.session_state.latest_data['rssi']
                rssi_status = "🟢" if rssi > -85 else "🟡" if rssi > -100 else "🔴"
                st.metric(label=f"{rssi_status} RSSI", value=f"{rssi} dBm")
            
            with col2:
                snr = st.session_state.latest_data['snr']
                snr_status = "🟢" if snr > 0 else "🟡" if snr > -5 else "🔴"
                st.metric(label=f"{snr_status} SNR", value=f"{snr:.1f} dB")
            
            with col3:
                st.metric(label="🕐 Last Update", value=st.session_state.latest_data['timestamp'].strftime("%H:%M:%S"))
            
            with col4:
                rate = st.session_state.latest_data['dailyCost'] / st.session_state.latest_data['dailyKwh'] if st.session_state.latest_data['dailyKwh'] > 0 else 11.16
                st.metric(label="💵 Rate", value=f"₱{rate:.2f}/kWh")
    
    # Charts
    with chart_placeholder.container():
        if len(st.session_state.history) > 0:
            st.divider()
            
            # Convert history to DataFrame
            df = pd.DataFrame(list(st.session_state.history))
            
            # Power consumption chart
            fig_power = go.Figure()
            fig_power.add_trace(go.Scatter(
                x=df['timestamp'],
                y=df['power'],
                mode='lines',
                name='Power',
                line=dict(color='#00f2fe', width=2),
                fill='tozeroy',
                fillcolor='rgba(0, 242, 254, 0.1)'
            ))
            fig_power.update_layout(
                title="Power Consumption Over Time",
                xaxis_title="Time",
                yaxis_title="Power (W)",
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                height=300,
                margin=dict(l=0, r=0, t=40, b=0)
            )
            st.plotly_chart(fig_power, use_container_width=True)
            
            # Voltage and Current charts
            col1, col2 = st.columns(2)
            
            with col1:
                fig_voltage = go.Figure()
                fig_voltage.add_trace(go.Scatter(
                    x=df['timestamp'],
                    y=df['voltage'],
                    mode='lines',
                    name='Voltage',
                    line=dict(color='#4facfe', width=2)
                ))
                fig_voltage.update_layout(
                    title="Voltage",
                    xaxis_title="Time",
                    yaxis_title="Voltage (V)",
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='white'),
                    height=250,
                    margin=dict(l=0, r=0, t=40, b=0)
                )
                st.plotly_chart(fig_voltage, use_container_width=True)
            
            with col2:
                fig_current = go.Figure()
                fig_current.add_trace(go.Scatter(
                    x=df['timestamp'],
                    y=df['current'],
                    mode='lines',
                    name='Current',
                    line=dict(color='#f5af19', width=2)
                ))
                fig_current.update_layout(
                    title="Current",
                    xaxis_title="Time",
                    yaxis_title="Current (A)",
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='white'),
                    height=250,
                    margin=dict(l=0, r=0, t=40, b=0)
                )
                st.plotly_chart(fig_current, use_container_width=True)
    
    # Refresh
    time.sleep(refresh_rate)
