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

load_dotenv()


# ===== CONFIGURACIÓN =====
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_STATE_TOPIC")
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")


PUBLISH_INTERVAL = int(os.getenv("PUBLISH_INTERVAL", 30))

# ===== MQTT =====
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

def on_connect(client, userdata, flags, reason_code, properties):
    print("MQTT state conectado (2):", reason_code)

client.on_connect = on_connect
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

w = wmi.WMI(namespace="root\\wmi")

def get_cpu_temperature():
    """
    Devuelve temperatura CPU en °C usando ACPI (WMI)
    """
    try:
        temps = w.MSAcpi_ThermalZoneTemperature()
        if not temps:
            return None

        # ACPI devuelve décimas de Kelvin
        temp_k = temps[0].CurrentTemperature
        temp_c = (temp_k / 10.0) - 273.15
        return round(temp_c, 1)

    except Exception as e:
        print("Error leyendo temperatura:", e)
        return None

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
        print("Error obteniendo VMs Hyper-V:", e)

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

    print("Publicado:", payload)
    client.publish(MQTT_TOPIC, json.dumps(payload), retain=True)
    time.sleep(PUBLISH_INTERVAL)


