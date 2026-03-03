import time
import clr
import os
import sys

# Agregar path actual para que encuentre las DLL
dll_path = os.path.abspath(".")
sys.path.append(dll_path)

clr.AddReference("LibreHardwareMonitorLib")

from LibreHardwareMonitor.Hardware import Computer

# Crear objeto Computer
computer = Computer()
computer.IsCpuEnabled = True
computer.Open()


def update_hardware(hw):
    hw.Update()
    for sub in hw.SubHardware:
        update_hardware(sub)


def get_cpu_temperature():
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

    return None


print("Leyendo temperatura CPU...\n")

while True:
    temp = get_cpu_temperature()

    if temp is not None:
        print(f"CPU Package: {temp:.1f} °C")
    else:
        print("No se pudo leer temperatura")

    time.sleep(2)
