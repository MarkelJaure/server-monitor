# server-monitor
Server Monitor es una herramienta diseñada en python para funcionar en segundo plano en los servidores (principalmente fisicos) que se desean monitorear desde compulab. Permite acceder a informacion del hardware asi como ejecutar acciones simples de manera remota (prender, apagar y reiniciar). Funciona ejecutando un programa python en segundo plano que envia informacion por MQTT de manera periodica y escucha en un topico por si llega alguna orden a ejecutar.

| Parte | Ubicación | Función / Descripción |
|-------|-----------|--------------------|
| **Servidor** | Servidor físico/virtual a monitorear | Ejecuta **Server Monitor**, que recolecta información de hardware, publica datos y escucha comandos remotos (prender, apagar, reiniciar). |
| **Broker MQTT** | Raspberry Pi | Actúa como **centro de información**, recibe los datos del servidor y distribuye las órdenes entre el servidor y Home Assistant. |
| **Home Assistant** | Raspberry Pi | Interfaz para el usuario: muestra información de los servidores y permite enviar órdenes (acciones) a los servidores vía MQTT. |


## Funcionalidades

### 🧾 Logging
- Registro de acciones relevantes tanto del **Updater** como del **Monitor**.
- Los logs se almacenan en:
  - `server-monitor.log`
  - Carpeta `/monitor`
- Permite trazabilidad de eventos, errores y ejecuciones automáticas.

### Updater
Servicio encargado de mantener el sistema actualizado automáticamente.

1. Verifica conexión a internet y establece conexión con el broker **MQTT**.
2. Ejecuta `monitor.py`.
3. Consulta cada **60 minutos** la última versión publicada en GitHub y la compara con la instalada. La comparación acepta tags con prefijo `v`.
4. Si la versión publicada es superior, descarga los archivos de `monitor/` y reinicia el monitor.
5. Publica el estado en `/update/state`.

### Monitor:
Servicio principal encargado de la ejecución remota y monitoreo del servidor.

1. Verifica conexión a internet y establece conexión con el broker **MQTT**.
2. Se suscribe al topico `/action` del servidor correspondiente.
3. Manejo de acciones:
   - Escucha comandos en tiempo real.
   - Ejecuta acciones según la lógica definida en `monitor.py`.
   - Publica el resultado de la accion en `/action/result`
4. Inicia un buclue infinito que:
   1. Obtiene la informacion del hardware y la publica en el subtopico `/state`
   2. Espera **30 segundos** antes de repetir.

### Inventario de hardware

El monitor publica un JSON retenido con QoS 1 en `clients/<cliente>/<equipo>/inventory` al conectar o reconectar a MQTT y cada 24 horas mientras siga conectado. Un suscriptor nuevo recibe el último inventario disponible. Para descubrir equipos de un cliente, suscribite a `clients/<cliente>/+/inventory`.

El JSON incluye `schema_version` (actualmente `1`), `timestamp` (Unix en segundos), `client`, `machine_name` y `system.hostname` (el hostname real de Windows). Contiene modelo del equipo, sistema operativo, procesadores, RAM, discos físicos, GPU, placas base y BIOS. Las capacidades están en bytes. Una lista de hardware vale `null` si WMI no pudo leerla y `[]` si pudo leerla pero no encontró dispositivos. Las métricas de rendimiento se pueden asociar por el mismo prefijo MQTT en `/state`.

Cada módulo de RAM incluye `memory_type` (por ejemplo, `DDR4`, `DDR5` o `LPDDR5`). Cada disco incluye `disk_type` (`SSD` o `HDD`). El tipo vale `null` si Windows no proporciona datos suficientes para identificarlo.

Si el broker usa permisos por tópico, asegurate de que el monitor pueda publicar en `clients/<cliente>/<equipo>/inventory` y de que el consumidor de inventario tenga permiso de lectura.
  
## Servidores donde esta instalado el server-monitor:

## 🌐 Servidores con `server-monitor` instalado

| Categoría | Grupo / Ubicación | Servidores |
|----------|------------------|------------|
| Compulab | - | Server-1, Server-2, Server-3, Server-5, Server-6, Server-7, Mark-PC, Martin-PC |
| Buques   | - | Huyu 908, Huyu 961, Huyu 962, Hu Shun Yu 06, Hu Shun Yu 07, Hu Shun Yu 08, Puente Valdes |
| Clientes | San Isidro | Server-1, Server-2, Server-3, Server-4 |
| Clientes | Bricel | Server-1 |
| Clientes | Cigalfer | Server-1 |
| Clientes | RV Racing | Server-1 |
| Clientes | Hydra | Server-1 |
| Clientes | Holas | Server-1 |
| Clientes | Greciamar | Server-1 |
| Clientes | Santhor | Server-1, Server-2 |
| Clientes | La Escalerona | Server-1 |
| Clientes | Altamare | Server-1 |
| Clientes | Ecoprom | Server-1 |
| Clientes | Seafresh | Server-1 |
| Clientes | Colorshop | Server-1 |
| Clientes | Fabri | Server-1, Server-2 |

# Guia de Instalacion - Sistema de Monitoreo de Servidor

## 1. Preparacion del Servidor

1. Ingresar al servidor con credenciales de administrador
2. Copiar el instalador de Python a la carpeta `Descargas`
3. En caso de estar agregando un nuevo cliente/buque
   1. En Mosquitto hay que agregar los permisos del nuevo usuario MQTT al nuevo topico `mosquitto/config/aclfile`
   2. Hay que crear el usuario `docker exec -it mosquitto mosquitto_passwd /mosquitto/config/passwords {NOMBRE}`
   3. Reiniciar el Contenedor de Mosquitto con Portainer

---

## 2. Instalacion de Python

### 2.1 Ejecutar el Instalador

1. Abrir el instalador de Python
2. Marcar **ambas casillas** en la pantalla inicial:
   - [ ] Use admin privileges when installing py.exe
   - [ ] Add python.exe to PATH
3. Hacer clic en **"Customize Installation"**

### 2.2 Configuracion Personalizada

1. En "Optional Features", hacer clic en **Next**
2. En "Advanced Options":
   - [ ] Marcar **"Install Python 3.14 for all users"**
3. Hacer clic en **Install**
4. Esperar a que finalice la instalacion
5. Hacer clic en **Close**

### 2.3 Verificacion e Instalacion de Dependencias

Abrir **CMD como administrador** y ejecutar:

```bash
python --version
```

> Debe mostrar: `Python 3.14.x`

Instalar las dependencias requeridas:

```bash
python -m pip install -r requirements.txt
```

---

## 3. Configuracion del Sistema de Monitoreo

### 3.1 Preparar Directorios

1. Crear la carpeta `Programs` en:
   ```
   C:\Program Files\Python314\
   ```

### 3.2 Configurar Archivos

1. Copiar la carpeta `server-monitor` al **Escritorio**
2. Configurar `monitor/.env` con los datos de conexión al broker y el prefijo `MQTT_SERVER`. La variable `IS_FINAL_DEVICE` indica si el prefijo ya identifica al equipo.

   | `MQTT_SERVER` | `IS_FINAL_DEVICE` | Prefijo MQTT con hostname `SERVER-01` |
   | --- | --- | --- |
   | `clients/san-isidro` | `false` | `clients/san-isidro/SERVER-01` |
   | `clients/san-isidro/server-1` | `true` | `clients/san-isidro/server-1` |
   | `clients/san-isidro/server-1` | Omitida | `clients/san-isidro/server-1` |

   Para una instalación masiva, copiá el mismo `.env` con `MQTT_SERVER=clients/<cliente>` e `IS_FINAL_DEVICE=false` a todos los equipos del cliente. El monitor y el updater agregan el hostname de Windows tal como está escrito. Si se omite la variable, el valor predeterminado es `true` y ambos usan `MQTT_SERVER` tal cual.

   Para usar `IS_FINAL_DEVICE=false` en una instalación existente, actualizá también `updater.py` una vez. La actualización automática copia los archivos de `monitor/` y puede dejar archivos de versiones previas en disco.

3. Mover la carpeta `server-monitor` a:
   ```
   C:\Program Files\Python314\Programs\
   ```

---

## 4. Configuracion del Programador de Tareas

### 4.1 Crear Nueva Tarea

1. Abrir **Programador de tareas** (`taskschd.msc`)
2. Navegar a **Biblioteca del Programador de tareas**
3. Clic derecho -> **Crear tarea...**

### 4.2 Pestana "General"

| Campo | Valor |
|-------|-------|
| Nombre | `Server Monitor MQTT` |
| Opciones de seguridad | Ejecutar tanto si el usuario inicio sesion como si no |

### 4.3 Pestana "Desencadenadores"

1. Clic en **Nuevo...**
2. Iniciar la tarea: **Al iniciar el sistema**
3. Clic en **Aceptar**

### 4.4 Pestana "Acciones"

1. Clic en **Nueva...**
2. Accion: **Iniciar un programa**
3. Configurar:

| Campo | Valor |
|-------|-------|
| Programa o script | `"C:\Program Files\Python314\python.exe"` |
| Agregar argumentos | `"C:\Program Files\Python314\Programs\server-monitor\updater.py"` |

4. Clic en **Aceptar**

### 4.5 Pestana "Condiciones"

- **Desmarcar** "Iniciar solo si el equipo esta conectado a corriente alterna"

### 4.6 Pestana "Configuracion"

- **Desmarcar** "Detener la tarea si se ejecuta durante mas de"
- **Marcar** "Si se produce un error, reiniciar cada"

### 4.7 Finalizar

1. Clic en **Aceptar**
2. Ingresar credenciales de administrador si se solicita

---

## 5. Verificacion

1. En la Biblioteca del Programador de tareas, localizar **"Server Monitor MQTT"**
2. Clic derecho -> **Ejecutar**
3. Verificar que el estado cambie a **"En ejecucion"**

---


# Activación de Wake on LAN (WOL) en un Servidor


---

## 1. Configuración del Servidor (Beelink Mini-PC)

1. Abrir **Administrador de Dispositivos** en Windows.
2. Buscar la **placa de red** conectada (Ethernet o Wi-Fi).
3. Hacer clic derecho → **Propiedades** → pestaña **Administración de energía**.
4. Marcar las siguientes opciones:
   - [x] Permitir que este dispositivo reactive el equipo
   - [x] Permitir solo un paquete mágico para reactivar el equipo
5. Guardar los cambios.

---

## 2. Configuración del Router Mikrotik del Servidor

1. Acceder al **Mikrotik** donde está conectado el servidor.
2. Navegar a **IP → Services**.
3. Habilitar **www** para poder recibir solicitudes REST desde Home Assistant.

---

En el home assistant:
Abrir el configuration.yaml
Agregar un rest_command con:
- La ip del MK
- credenciales del winbox
- MAC del servidor a prender
Abrir el scripts.yaml
Crear un script que ejecute el rest command y agregue un mensaje MQTT en el topico del servidor

---

## 4. Configuración del Mikrotik en el Barco

Para permitir que las solicitudes WOL lleguen al servidor desde el exterior:

1. Navegar a **IP → Firewall → Filter Rules.**
2. Crear una nueva regla:
   - **Chain**: Input
   - **Src. Address List**: IPs autorizadas (ej. Compulab)
   - **In. Interface List**: WAN
   - **Action**: Accept
3. Guardar

> ⚠️ Nota: Esto asegura que solo las IPs autorizadas puedan enviar paquetes WOL al servidor.

