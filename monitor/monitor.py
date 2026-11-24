import time
import json
import psutil
import socket
import wmi
import platform
import paho.mqtt.client as mqtt
from datetime import datetime
from threading import Event, Thread
import win32api
import os
import subprocess
import subprocess

if __package__:
    from .inventory import collect_inventory
    from .logging_config import configure_logging
    from .mqtt_config import ENV_PATH, load_mqtt_config
else:
    from inventory import collect_inventory
    from logging_config import configure_logging
    from mqtt_config import ENV_PATH, load_mqtt_config

# ===== LOGGER =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "monitor.log")
logger, log_handler = configure_logging(ENV_PATH, LOG_FILE, console=True)

try:
    config = load_mqtt_config()
except ValueError as exc:
    logger.error("Configuración MQTT inválida: %s", exc)
    raise SystemExit(1) from exc

MQTT_STATE_TOPIC = f"{config.topic_prefix}/state"
MQTT_ACTION_TOPIC = f"{config.topic_prefix}/action"
MQTT_ACTION_RESULT_TOPIC = f"{config.topic_prefix}/action/result"
MQTT_INVENTORY_TOPIC = f"{config.topic_prefix}/inventory"

PUBLISH_INTERVAL = 30
INVENTORY_INTERVAL = 24 * 60 * 60
inventory_requested = Event()


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
client.username_pw_set(config.user, config.password)
client.reconnect_delay_set(min_delay=1, max_delay=60)

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        logger.warning("Conexión MQTT rechazada (monitor): %s", reason_code)
        return

    logger.info(f"MQTT monitor conectado. reason_code={reason_code}")
    if config.allow_actions:
        client.subscribe(MQTT_ACTION_TOPIC)
        logger.info(f"Suscrito al topico MQTT: {MQTT_ACTION_TOPIC}")
    else:
        logger.info("Acciones remotas por MQTT deshabilitadas")

    inventory_requested.set()

    publish_action_result(
        'connection',
        "connected",
        f"Servidor MQTT Conectado"
    )


def publish_inventory():
    while True:
        inventory_requested.wait(timeout=INVENTORY_INTERVAL)
        inventory_requested.clear()
        if not client.is_connected():
            continue

        try:
            payload = collect_inventory(config.client_name, config.machine_name)
            result = client.publish(
                MQTT_INVENTORY_TOPIC, json.dumps(payload), qos=1, retain=True
            )
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                logger.warning("No se pudo enviar el inventario MQTT: %s", result.rc)
                continue

            result.wait_for_publish(timeout=10)
            if result.is_published():
                logger.info("Inventario publicado en %s", MQTT_INVENTORY_TOPIC)
            else:
                logger.warning("Sin confirmación MQTT para %s", MQTT_INVENTORY_TOPIC)
        except Exception:
            logger.exception("Error publicando inventario")


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
    vm_name = payload.get("vm")

    if not vm_name:
        return False, "Falta parámetro 'vm'"

    logger.debug("Solicitud de inicio de VM: %s", vm_name)
    command = f'powershell -ExecutionPolicy Bypass -Command "Start-VM -Name \'{vm_name}\'"'

    subprocess.run(command, shell=True, check=True)

    return True, f"VM iniciada: {vm_name}"

DEFAULT_KEEP_LAST_LINES = 100
def clear_logs(payload):
    try:
        # Obtener cantidad de líneas a conservar desde el payload
        keep = payload.get("keep", DEFAULT_KEEP_LAST_LINES)

        # Validación básica
        if not isinstance(keep, int) or keep <= 0:
            keep = DEFAULT_KEEP_LAST_LINES

        with log_handler.lock:
            with open(LOG_FILE, "r+", encoding="utf-8", errors="replace") as f:
                lines_to_keep = f.readlines()[-keep:]
                f.seek(0)
                f.writelines(lines_to_keep)
                f.truncate()

        return True, f"Logs limpiados. Se conservaron las últimas {keep} líneas"

    except FileNotFoundError:
        return False, "El archivo de logs no existe"
    except Exception as e:
        return False, f"Error al limpiar logs: {str(e)}"


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
    },
    "clear_logs": {
        "handler": clear_logs,
        "message": "Limpieza de logs"
    }
}

def on_message(client, userdata, msg):
    if not config.allow_actions:
        return

    try:
        payload = json.loads(msg.payload.decode())
        action = payload.get("action", "").lower()

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
        logger.info( f"Acción no reconocida: {action}")
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
                logger.info(message)

            else:
                publish_action_result(
                    action,
                    "failed",
                    message
                )
                logger.error(message)

        # 🔹 Acciones simples (command)
        elif "command" in action_data:
            subprocess.run(action_data["command"], shell=True, check=True)

            publish_action_result(
                action,
                "executed",
                f"Orden ejecutada: {action}"
            )
            logger.info(f"Orden ejecutada: {action}")


        else:
            publish_action_result(
                action,
                "error",
                "Acción mal configurada (sin command ni handler)"
            )
            logger.error("Acción mal configurada (sin command ni handler)")

    except Exception as e:
        publish_action_result(
            action,
            "failed",
            f"Error ejecutando acción: {str(e)}"
        )
        logger.error(f"Error ejecutando acción: {str(e)}")


client.on_connect = on_connect
client.on_message = on_message

def connect_mqtt():
    while True:
        try:
            logger.debug("Intentando conectar a MQTT (monitor)...")
            client.connect(config.broker, config.port, 60)
            return
        except Exception as e:
            logger.warning(f"MQTT monitor no disponible, reintentando en 10s: {e}")
            time.sleep(10)

connect_mqtt()
client.loop_start()
Thread(target=publish_inventory, name="mqtt-inventory", daemon=True).start()


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

    if config.skip_vms:
        return vms_info

    try:
        c = wmi.WMI(namespace=r"root\virtualization\v2")

        vms = c.Msvm_ComputerSystem()

        for vm in vms:

            if vm.Caption not in ["Virtual Machine", "Máquina virtual"]:
                continue

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

        result = client.publish(MQTT_STATE_TOPIC, json.dumps(payload), retain=True)
        logger.debug("Publicación de estado en %s: %s", MQTT_STATE_TOPIC, mqtt.error_string(result.rc))
    except Exception as e:
        logger.exception("Error en ciclo principal")
    time.sleep(PUBLISH_INTERVAL)


