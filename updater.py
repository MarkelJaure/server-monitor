import requests
import zipfile
import shutil
import subprocess
import sys
import time
import os
import tempfile
from dotenv import load_dotenv
from pathlib import Path
import os
import paho.mqtt.client as mqtt
import json


ENV_PATH = Path(__file__).parent / "monitor" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_UPDATE_TOPIC")
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

def on_connect(client, userdata, flags, reason_code, properties):
    print("MQTT updater conectado:", reason_code)

client.on_connect = on_connect
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

def publish_updater_status(
    status,
    message="",
    current_version=None,
    new_version=None
):
    payload = {
        "status": status,
        "message": message,
        "current_version": current_version,
        "new_version": new_version,
        "timestamp": int(time.time())
    }

    client.publish(
        MQTT_TOPIC,
        json.dumps(payload),
        retain=True
    )


REPO_API = "https://api.github.com/repos/MarkelJaure/server-monitor/releases/latest"
CHECK_INTERVAL = 600  # segundos

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MONITOR_DIR = os.path.join(BASE_DIR, "monitor")

VERSION_FILE = os.path.join(MONITOR_DIR, "version.txt")
MONITOR_SCRIPT = os.path.join(MONITOR_DIR, "monitor.py")




def get_local_version():
    if not os.path.exists(VERSION_FILE):
        return "0.0.0"
    with open(VERSION_FILE) as f:
        return f.read().strip()


def get_remote_release():
    r = requests.get(REPO_API, timeout=10)
    r.raise_for_status()
    data = r.json()
    return data["tag_name"], data["zipball_url"]


def download_and_update(zip_url, new_version):
    print("Descargando actualización...")

    tmp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(tmp_dir, "update.zip")

    with requests.get(zip_url, stream=True) as r:
        with open(zip_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(tmp_dir)

    extracted_root = next(
        os.path.join(tmp_dir, d)
        for d in os.listdir(tmp_dir)
        if os.path.isdir(os.path.join(tmp_dir, d))
    )

    extracted_monitor = os.path.join(extracted_root, "monitor")

    if not os.path.isdir(extracted_monitor):
        raise RuntimeError("El release no contiene la carpeta monitor/")

    for item in os.listdir(extracted_monitor):
        if item in [".env", "version.txt"]:
            continue

        src = os.path.join(extracted_monitor, item)
        dst = os.path.join(MONITOR_DIR, item)

        if os.path.isdir(src):
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    with open(VERSION_FILE, "w") as f:
        f.write(new_version)

    shutil.rmtree(tmp_dir)
    print("Actualización aplicada correctamente")


def start_monitor():
    print("Iniciando monitor...")
    return subprocess.Popen(
        [sys.executable, MONITOR_SCRIPT],
        cwd=MONITOR_DIR
    )


if __name__ == "__main__":
    print("Updater iniciado")
    monitor = start_monitor()

    while True:
        time.sleep(CHECK_INTERVAL)
        local = get_local_version()

        try:
            remote, zip_url = get_remote_release()
            if remote != local:

                publish_updater_status(
                    status="update_available",
                    message="Nueva versión detectada",
                    current_version=local,
                    new_version=remote
                )

                print(f"Nueva versión detectada: {remote}")
                monitor.terminate()
                monitor.wait()

                publish_updater_status(
                    status="updating",
                    message="Actualizando archivos",
                    current_version=local,
                    new_version=remote
                )

                download_and_update(zip_url, remote)
                monitor = start_monitor()

                publish_updater_status(
                    status="success",
                    message="Actualización completa",
                    current_version=remote
                )
            else:
                publish_updater_status(
                    status="success",
                    message="Ultima versions",
                    current_version=remote
                )

        except Exception as e:
            print("Error en updater:", e)

            publish_updater_status(
                status="error",
                message=str(e),
                current_version=local
            )
