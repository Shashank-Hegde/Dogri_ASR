import streamlit as st
import paramiko
from scp import SCPClient
import json

# ------------------------------------------------------
# CONFIG (read from Streamlit secrets)
# ------------------------------------------------------
REMOTE_USER = st.secrets["ssh"]["REMOTE_USER"]
REMOTE_HOST = st.secrets["ssh"]["REMOTE_HOST"]
REMOTE_SSH_PORT = int(st.secrets["ssh"]["REMOTE_SSH_PORT"])
REMOTE_DIR = st.secrets["ssh"]["REMOTE_DIR"]
ASR_SERVER_INTERNAL_IP = st.secrets["ssh"]["ASR_SERVER_INTERNAL_IP"]
SSH_PASSWORD = st.secrets["ssh"]["SSH_PASSWORD"]
DEFAULT_PORT = int(st.secrets["ssh"]["DEFAULT_PORT"])
# ------------------------------------------------------


st.set_page_config(page_title="Dogri ASR (M4 Server)", page_icon="🎧")

st.title("🎧 ASR Transcription & Translation (M4 Server)")
st.write(
    "Upload a `.wav` file. It will be sent to the M4 Max server over SSH, "
    "then processed by your ASR API running inside the M4 network."
)

uploaded_file = st.file_uploader("Upload WAV file", type=["wav"])

port = st.number_input("ASR Model Port", value=DEFAULT_PORT, step=1)

def run_remote_asr(file_obj, filename: str, port: int):
    # Ensure file pointer is at the beginning
    file_obj.seek(0)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    ssh.connect(
        hostname=REMOTE_HOST,
        port=REMOTE_SSH_PORT,
        username=REMOTE_USER,
        password=SSH_PASSWORD,
        timeout=30
    )

    try:
        # Upload file via SCP
        with SCPClient(ssh.get_transport()) as scp:
            remote_path = f"{REMOTE_DIR}/{filename}"
            scp.putfo(file_obj, remote_path)

        # Build curl command to call ASR API from inside M4
        curl_command = (
            f"cd {REMOTE_DIR} && "
            f"curl -s -X POST http://{ASR_SERVER_INTERNAL_IP}:{port}/convertSpeechToText "
            f"-H 'Content-Type: application/json' "
            f"-d '{{\"audioFileName\":\"{filename}\"}}'"
        )

        stdin, stdout, stderr = ssh.exec_command(curl_command)
        result = stdout.read().decode().strip()
        error_output = stderr.read().decode().strip()

        return result, error_output
    finally:
        ssh.close()


if uploaded_file is not None:
    filename = uploaded_file.name
    st.write(f"**File selected:** `{filename}`")

    if st.button("Run Transcription"):
        with st.spinner("Uploading to M4 Max server and running ASR..."):
            try:
                result, err = run_remote_asr(uploaded_file, filename, int(port))

                if err:
                    st.warning("Remote stderr output:")
                    st.code(err)

                # Try to parse JSON
                try:
                    parsed = json.loads(result)
                    st.success("ASR result received:")
                    st.json(parsed)
                except json.JSONDecodeError:
                    st.error("Failed to parse JSON. Raw output:")
                    st.code(result or "(empty response)")

            except Exception as e:
                st.error(f"Error communicating with remote server: {e}")
