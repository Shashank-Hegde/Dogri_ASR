import streamlit as st
import paramiko
from scp import SCPClient
import json
import requests

# ------------------------------------------------------
# CONFIG
# ------------------------------------------------------
REMOTE_USER = st.secrets.get("REMOTE_USER", "o-health")
REMOTE_HOST = st.secrets.get("REMOTE_HOST", "49.204.152.240")
REMOTE_SSH_PORT = int(st.secrets.get("REMOTE_SSH_PORT", 1234))
REMOTE_DIR = st.secrets.get("REMOTE_DIR", "~/Downloads/Debosmit/Audio/Dogri")
ASR_SERVER_INTERNAL_IP = st.secrets.get("ASR_SERVER_INTERNAL_IP", "192.168.0.101")
DEFAULT_PORT = int(st.secrets.get("DEFAULT_PORT", 5005))
SSH_PASSWORD = st.secrets.get("SSH_PASSWORD", "123456789")
# ------------------------------------------------------

st.title("🎧 ASR Transcription & Translation (M4 Server)")
st.write("Upload audio or record using your mic to transcribe & translate using your remote ASR server.")

# ------------------------------------------------------------------
#  INPUT MODE SELECTOR
# ------------------------------------------------------------------
mode = st.radio(
    "Choose Audio Input Method",
    ["Upload WAV File", "Record using Microphone"]
)

uploaded_file = None
recorded_audio = None

if mode == "Upload WAV File":
    uploaded_file = st.file_uploader("Upload WAV file", type=["wav"])

elif mode == "Record using Microphone":
    recorded_audio = st.audio_input("Record audio")

port = st.number_input("ASR Model Port", value=DEFAULT_PORT)

# ------------------------------------------------------------------
#  PROCESS FILE
# ------------------------------------------------------------------
if (uploaded_file or recorded_audio) and st.button("Run Transcription"):
    
    # Determine filename + file data
    if uploaded_file:
        file_obj = uploaded_file
        filename = uploaded_file.name

    elif recorded_audio:
        file_obj = recorded_audio
        filename = "mic_recording.wav"

    st.write(f"**File selected:** {filename}")

    # ------------------------------
    # Upload to remote server
    # ------------------------------
    with st.spinner("Uploading to M4 Max server..."):

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=REMOTE_HOST,
            port=REMOTE_SSH_PORT,
            username=REMOTE_USER,
            password=SSH_PASSWORD
        )

        # Upload using SCP
        with SCPClient(ssh.get_transport()) as scp:
            scp.putfo(file_obj, f"{REMOTE_DIR}/{filename}")

    st.success("File uploaded successfully!")

    # ------------------------------
    # Run ASR via SSH + CURL
    # ------------------------------
    st.info("Running ASR on the remote server...")

    curl_command = (
        f"cd {REMOTE_DIR} && "
        f"curl -s -X POST http://{ASR_SERVER_INTERNAL_IP}:{port}/convertSpeechToText "
        f"-H 'Content-Type: application/json' "
        f"-d '{{\"audioFileName\":\"Dogri/{filename}\"}}'"
    )

    stdin, stdout, stderr = ssh.exec_command(curl_command)
    result = stdout.read().decode().strip()
    ssh.close()

    # ------------------------------
    # Display JSON response
    # ------------------------------
    try:
        parsed = json.loads(result)
        st.json(parsed)
    except:
        st.error("Failed to parse JSON")
        st.text(result)
