from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values


ENV_PATH = Path(__file__).with_name(".env")
CLIENTS_ROOT = "clients"


@dataclass(frozen=True)
class MQTTConfig:
    broker: str
    port: int
    user: str | None
    password: str | None
    client_name: str | None
    machine_name: str
    topic_prefix: str
    skip_vms: bool


def load_mqtt_config():
    file_values = dotenv_values(ENV_PATH, encoding="utf-8-sig")
    server = file_values.get("MQTT_SERVER") or ""
    if not server.strip():
        raise ValueError("Definí MQTT_SERVER en monitor/.env")

    is_final = (file_values.get("IS_FINAL_DEVICE", "true") or "").strip().lower()
    if is_final not in ("true", "false"):
        raise ValueError("IS_FINAL_DEVICE debe ser true o false")

    if is_final == "true":
        topic_prefix = server
        client_topic, _, machine_name = server.rpartition("/")
    else:
        client_topic = server
        machine_name = socket.gethostname()
        if not machine_name.strip() or "/" in machine_name:
            raise ValueError("El hostname debe ser un segmento MQTT válido")
        topic_prefix = f"{server}/{machine_name}"

    if any(char in topic_prefix for char in ("+", "#", "\0")):
        raise ValueError("El prefijo MQTT no puede contener comodines ni caracteres nulos")

    root, _, client_path = client_topic.partition("/")
    client_name = client_path.partition("/")[0] if root == CLIENTS_ROOT else client_topic

    # Para los parámetros de conexión, conservar la precedencia del entorno.
    settings = {key: value for key, value in file_values.items() if value is not None}
    settings.update(os.environ)
    broker = settings.get("MQTT_BROKER")
    if not broker:
        raise ValueError("Definí MQTT_BROKER con la dirección del broker")

    return MQTTConfig(
        broker=broker,
        port=int(settings.get("MQTT_PORT", 1883)),
        user=settings.get("MQTT_USER"),
        password=settings.get("MQTT_PASSWORD"),
        client_name=client_name or None,
        machine_name=machine_name,
        topic_prefix=topic_prefix,
        skip_vms=settings.get("SKIP_VMS", "false").lower() == "true",
    )
