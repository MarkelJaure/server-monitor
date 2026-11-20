import logging
import platform
import time
from collections import Counter
from threading import current_thread, main_thread

import psutil
import pythoncom
import wmi


logger = logging.getLogger(__name__)

SMBIOS_DDR_TYPES = {
    0x12: "DDR",
    0x13: "DDR2",
    0x14: "DDR2 FB-DIMM",
    0x18: "DDR3",
    0x1A: "DDR4",
    0x1B: "LPDDR",
    0x1C: "LPDDR2",
    0x1D: "LPDDR3",
    0x1E: "LPDDR4",
    0x22: "DDR5",
    0x23: "LPDDR5",
}
CIM_DDR_TYPES = {
    20: "DDR",
    21: "DDR2",
    22: "DDR2 FB-DIMM",
    24: "DDR3",
    26: "DDR4",
}
DISK_TYPES = {3: "HDD", 4: "SSD"}


def connect_wmi(namespace=r"root\cimv2"):
    try:
        return wmi.WMI(namespace=namespace)
    except (wmi.x_wmi, pythoncom.com_error) as exc:
        logger.warning("WMI no disponible en %s para el inventario: %s", namespace, exc)
        return None


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


def read_memory_modules(connection):
    modules = read_wmi(connection, "Win32_PhysicalMemory", {
        "slot": "DeviceLocator",
        "manufacturer": "Manufacturer",
        "part_number": "PartNumber",
        "capacity_bytes": "Capacity",
        "configured_clock_mhz": "ConfiguredClockSpeed",
        "smbios_type": "SMBIOSMemoryType",
        "cim_type": "MemoryType",
    }, integer_fields=("capacity_bytes", "smbios_type", "cim_type"))

    for module in modules or []:
        smbios_type = module.pop("smbios_type")
        cim_type = module.pop("cim_type")
        if smbios_type in (None, 0, 1, 2):
            module["memory_type"] = CIM_DDR_TYPES.get(cim_type)
        else:
            module["memory_type"] = SMBIOS_DDR_TYPES.get(smbios_type)
    return modules


def read_disks(connection):
    disks = read_wmi(connection, "Win32_DiskDrive", {
        "index": "Index",
        "model": "Model",
        "size_bytes": "Size",
        "interface": "InterfaceType",
        "media_type": "MediaType",
        "serial_number": "SerialNumber",
    }, integer_fields=("size_bytes",))
    if not disks:
        return disks

    storage = connect_wmi(r"root\Microsoft\Windows\Storage")
    physical_disks = read_wmi(storage, "MSFT_PhysicalDisk", {
        "serial_number": "SerialNumber",
        "media_type": "MediaType",
    }, integer_fields=("media_type",)) or []

    # Vincular solo números de serie únicos en ambos proveedores.
    disk_serials = [(disk.pop("serial_number") or "").casefold() for disk in disks]
    physical_serials = [
        (disk["serial_number"] or "").casefold() for disk in physical_disks
    ]
    disk_counts = Counter(disk_serials)
    physical_counts = Counter(physical_serials)
    types_by_serial = {
        serial: DISK_TYPES.get(disk["media_type"])
        for serial, disk in zip(physical_serials, physical_disks)
        if serial and physical_counts[serial] == 1
    }
    for serial, disk in zip(disk_serials, disks):
        disk["disk_type"] = types_by_serial.get(serial) if disk_counts[serial] == 1 else None
    return disks


def read_windows_inventory():
    connection = connect_wmi()

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
    memory_modules = read_memory_modules(connection)
    disks = read_disks(connection)
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
