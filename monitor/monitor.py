import time
import json
import psutil
import socket
import wmi
import platform
import paho.mqtt.client as mqtt
from datetime import datetime
import win32api
import os
from dotenv import load_dotenv
import logging
import subprocess
import subprocess

# ===== LOGGER =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "server-monitor.log")


logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger()
# ======= Inicialización segura de LibreHardwareMonitor =======
try:
    import clr
    import sys
    import os

    dll_path = os.path.abspath(".")
    sys.path.append(dll_path)
    clr.AddReference("LibreHardwareMonitorLib")

    from LibreHardwareMonitor.Hardware import Computer

    computer = Computer()
    computer.IsCpuEnabled = True
    computer.Open()

    LIB_MONITOR_OK = True  # marca que LibreHardwareMonitor está listo
except Exception as e:
    computer = None
    LIB_MONITOR_OK = False


load_dotenv()

# ===== CONFIGURACIÓN =====
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

MQTT_STATE_TOPIC = os.getenv("MQTT_SERVER") + '/state'
MQTT_ACTION_TOPIC = os.getenv("MQTT_SERVER") + '/action'
MQTT_ACTION_RESULT_TOPIC = os.getenv("MQTT_SERVER") + '/action/result'

PUBLISH_INTERVAL = 30


def wait_for_network(timeout=300):
    logger.info("Esperando conectividad de red (monitor)...")

    start = time.time()

    while True:
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            logger.info("Red disponible (monitor)")
            return True
        except OSError:
            pass

        if time.time() - start > timeout:
            logger.warning("Timeout esperando red (monitor)")
            return False

        time.sleep(5)

wait_for_network()

# ===== MQTT =====
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
client.reconnect_delay_set(min_delay=1, max_delay=60)

def on_connect(client, userdata, flags, reason_code, properties):
    logger.info(f"MQTT monitor conectado. reason_code={reason_code}")
    client.subscribe(MQTT_ACTION_TOPIC)
    logger.info(f"Suscrito al topico MQTT: {MQTT_ACTION_TOPIC}")

    publish_action_result(
        'connection',
        "connected",
        f"Servidor MQTT Conectado"
    )

def publish_action_result(action, status, message):
    payload = {
        "hostname": platform.node(),
        "action": action,
        "status": status,
        "message": message,
        "timestamp": int(time.time())
    }
    client.publish(MQTT_ACTION_RESULT_TOPIC, json.dumps(payload), retain=False)



def start_vm(payload):
    print(payload)
    vm_name = payload.get("vm")

    if not vm_name:
        return False, "Falta parámetro 'vm'"

    command = f'powershell -ExecutionPolicy Bypass -Command "Start-VM -Name \'{vm_name}\'"'

    subprocess.run(command, shell=True, check=True)

    return True, f"VM iniciada: {vm_name}"


ACTION_MAP = {
    "shutdown": {
        "command": "shutdown /s /t 5",
        "message": "Apagado del servidor"
    },
    "reboot": {
        "command": "shutdown /r /t 5",
        "message": "Reinicio del servidor"
    },
    "cancel_shutdown": {
        "command": "shutdown /a",
        "message": "Apagado/reinicio cancelado"
    },
    "start_vm": {
        "handler": start_vm,
        "message": "Encendido de VM"
    }
}



def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        action = payload.get("action", "").lower()
        print(action)
    except Exception:
        publish_action_result(
            "unknown",
            "error",
            "Payload inválido (no es JSON)"
        )
        return

    logger.info(f"Acción recibida MQTT: {action}")

    action_data = ACTION_MAP.get(action)

    if not action_data:
        publish_action_result(
            action,
            "error",
            f"Acción no reconocida: {action}"
        )
        return

    publish_action_result(
        action,
        "accepted",
        f"Orden recibida: {action}"
    )

    try:
        # 🔹 Si tiene handler (ej: start_vm)
        if "handler" in action_data:
            success, message = action_data["handler"](payload)

            if success:
                publish_action_result(
                    action,
                    "executed",
                    message
                )
            else:
                publish_action_result(
                    action,
                    "failed",
                    message
                )

        # 🔹 Acciones simples (command)
        elif "command" in action_data:
            subprocess.run(action_data["command"], shell=True, check=True)

            publish_action_result(
                action,
                "executed",
                f"Orden ejecutada: {action}"
            )

        else:
            publish_action_result(
                action,
                "error",
                "Acción mal configurada (sin command ni handler)"
            )

    except Exception as e:
        publish_action_result(
            action,
            "failed",
            f"Error ejecutando acción: {str(e)}"
        )


client.on_connect = on_connect
client.on_message = on_message

def connect_mqtt():
    while True:
        try:
            logger.info("Intentando conectar a MQTT (monitor)...")
            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            logger.info("Conectado a MQTT (monitor)")
            return
        except Exception as e:
            logger.warning(f"MQTT monitor no disponible, reintentando en 10s: {e}")
            time.sleep(10)

connect_mqtt()
client.loop_start()

w = wmi.WMI(namespace="root\\wmi")

def update_hardware(hw):
    try:
        hw.Update()
        for sub in hw.SubHardware:
            update_hardware(sub)
    except:
        pass  # ignorar errores de hardware

def get_cpu_temperature():
    if not LIB_MONITOR_OK or computer is None:
        return None  # si pythonnet o DLL no funcionan

    try:
        for hardware in computer.Hardware:
            update_hardware(hardware)

            if hardware.HardwareType.ToString() == "Cpu":
                for sensor in hardware.Sensors:
                    if (
                        sensor.SensorType.ToString() == "Temperature"
                        and "Package" in sensor.Name
                        and sensor.Value is not None
                    ):
                        return sensor.Value
    except Exception as e:
        return None

    return None  # si no encuentra sensor



def get_ip():
    try:
        return socket.gethostbyname(socket.gethostname())
    except:
        return "unknown"

STATE_MAP = {
    2: "running",
    3: "off",
    32768: "paused",
    32769: "saved"
}

def get_hyperv_vms():
    vms_info = []

    SKIP_VMS = os.getenv("SKIP_VMS", "false").lower() == "true"

    if SKIP_VMS:
        return vms_info

    try:
        c = wmi.WMI(namespace=r"root\virtualization\v2")

        # SOLO máquinas virtuales (excluye el host)
        vms = c.Msvm_ComputerSystem(Caption="Máquina virtual")

        for vm in vms:
            # Obtener settings del sistema virtual
            settings = vm.associators(
                wmi_result_class="Msvm_VirtualSystemSettingData"
            )

            if not settings:
                continue

            settings = settings[0]

            # CPU
            cpu_settings = settings.associators(
                wmi_result_class="Msvm_ProcessorSettingData"
            )
            cpu_count = cpu_settings[0].VirtualQuantity if cpu_settings else None

            # Memoria
            mem_settings = settings.associators(
                wmi_result_class="Msvm_MemorySettingData"
            )
            memory_mb = mem_settings[0].VirtualQuantity if mem_settings else None

            vm_data = {
                "name": vm.ElementName,
                "state": STATE_MAP.get(vm.EnabledState, "unknown"),
                "cpu_assigned": cpu_count,
                "memory_gb": int(memory_mb) / 1024 ,
                "uptime_s": int(vm.OnTimeInMilliseconds) / 1000 if vm.OnTimeInMilliseconds else 0,
                "process_id": vm.ProcessID,
                "health_state": vm.HealthState
            }

            vms_info.append(vm_data)

    except Exception as e:
        logger.error(f"Error obteniendo VMs Hyper-V: {e}")

    return vms_info

def get_disks_info():
    disks = []

    for part in psutil.disk_partitions(all=False):
        # En Windows los discos reales suelen ser tipo fixed
        if "cdrom" in part.opts or part.fstype == "":
            continue

        try:
            usage = psutil.disk_usage(part.mountpoint)

            volume_info = win32api.GetVolumeInformation(part.mountpoint)
            label = volume_info[0] if volume_info[0] else "Sin nombre"

            disks.append({
                "device": part.device,            # C:\
                "mountpoint": part.mountpoint,    # C:\
                "label": label,                            # Sistema / Datos / etc
                "fstype": part.fstype,
                "used_percent": usage.percent,
                "used_gb": round(usage.used / 1024**3, 2),
                "free_gb": round(usage.free / 1024**3, 2),
                "total_gb": round(usage.total / 1024**3, 2),
            })

        except PermissionError:
            continue

    return disks


while True:
    try:
        cpu_temp = get_cpu_temperature()

        mem = psutil.virtual_memory()
        net = psutil.net_io_counters()

        payload = {
            "system": {
                "hostname": platform.node(),
                "ip": get_ip(),
                "uptime_sec": int(time.time() - psutil.boot_time()),
                "os": platform.system(),
                "arch": platform.machine(),
            },
            "cpu": {
                "usage_percent": psutil.cpu_percent(),
                "freq_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else None,
                "cores": psutil.cpu_count(),
                "temperature": cpu_temp,
            },
            "memory": {
                "used_percent": mem.percent,
                "used_gb": round(mem.used / 1024 / 1024 / 1024, 1),
                "total_gb": round(mem.total / 1024 / 1024 / 1024, 1),
            },
            "timestamp": int(time.time()),
            "interval_sec": PUBLISH_INTERVAL,
            "vms": get_hyperv_vms(),
            "disks": get_disks_info()
        }

        logger.info(f"Estado publicado en {MQTT_STATE_TOPIC}")
        client.publish(MQTT_STATE_TOPIC, json.dumps(payload), retain=True)
    except Exception as e:
        logger.exception("Error en ciclo principal")
    time.sleep(PUBLISH_INTERVAL)


