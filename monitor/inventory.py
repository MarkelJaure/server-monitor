import logging
import platform
import time
from threading import current_thread, main_thread

import psutil
import pythoncom
import wmi


logger = logging.getLogger(__name__)


def read_wmi(connection, class_name, fields, *, integer_fields=()):
    if connection is None:
        return None

    try:
        properties = ", ".join(fields.values())
        rows = connection.query(f"SELECT {properties} FROM {class_name}")
        devices = []
        for row in rows:
            device = {}
            for name, property_name in fields.items():
                value = getattr(row, property_name)
                if isinstance(value, str):
                    value = value.strip() or None
                if value is not None and name in integer_fields:
                    value = int(value)
                device[name] = value
            devices.append(device)
        return devices
    except (wmi.x_wmi, pythoncom.com_error, AttributeError, ValueError, TypeError) as exc:
        logger.warning("No se pudo leer %s para el inventario: %s", class_name, exc)
        return None


def read_windows_inventory():
    try:
        connection = wmi.WMI()
    except (wmi.x_wmi, pythoncom.com_error) as exc:
        logger.warning("WMI no disponible para el inventario: %s", exc)
        connection = None

    system = read_wmi(connection, "Win32_ComputerSystem", {
        "manufacturer": "Manufacturer",
        "model": "Model",
    })
    operating_systems = read_wmi(connection, "Win32_OperatingSystem", {
        "name": "Caption",
        "version": "Version",
        "build": "BuildNumber",
    })
    processors = read_wmi(connection, "Win32_Processor", {
        "model": "Name",
        "physical_cores": "NumberOfCores",
        "logical_cores": "NumberOfLogicalProcessors",
        "max_clock_mhz": "MaxClockSpeed",
    })
    memory_modules = read_wmi(connection, "Win32_PhysicalMemory", {
        "slot": "DeviceLocator",
        "manufacturer": "Manufacturer",
        "part_number": "PartNumber",
        "capacity_bytes": "Capacity",
        "configured_clock_mhz": "ConfiguredClockSpeed",
    }, integer_fields=("capacity_bytes",))
    disks = read_wmi(connection, "Win32_DiskDrive", {
        "index": "Index",
        "model": "Model",
        "size_bytes": "Size",
        "interface": "InterfaceType",
        "media_type": "MediaType",
    }, integer_fields=("size_bytes",))
    gpus = read_wmi(connection, "Win32_VideoController", {
        "model": "Name",
        "driver_version": "DriverVersion",
    })
    motherboards = read_wmi(connection, "Win32_BaseBoard", {
        "manufacturer": "Manufacturer",
        "model": "Product",
    })
    bios = read_wmi(connection, "Win32_BIOS", {
        "manufacturer": "Manufacturer",
        "version": "SMBIOSBIOSVersion",
    })

    system_info = system[0] if system else {}
    os_info = operating_systems[0] if operating_systems else {}
    return {
        "system": {
            "hostname": platform.node(),
            "manufacturer": system_info.get("manufacturer"),
            "model": system_info.get("model"),
            "arch": platform.machine(),
        },
        "os": {
            "name": os_info.get("name") or platform.system(),
            "version": os_info.get("version") or platform.version(),
            "build": os_info.get("build"),
        },
        "cpu": {
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(),
            "processors": processors,
        },
        "memory": {
            "total_bytes": psutil.virtual_memory().total,
            "modules": memory_modules,
        },
        "disks": disks,
        "gpus": gpus,
        "motherboards": motherboards,
        "bios": bios[0] if bios else None,
    }


def collect_inventory(client_name, machine_name):
    # pythoncom ya inicializa COM en el hilo principal.
    needs_com_init = current_thread() is not main_thread()
    if needs_com_init:
        pythoncom.CoInitialize()
    try:
        inventory = read_windows_inventory()
    finally:
        if needs_com_init:
            pythoncom.CoUninitialize()

    return {
        "schema_version": 1,
        "timestamp": int(time.time()),
        "client": client_name,
        "machine_name": machine_name,
        **inventory,
    }
