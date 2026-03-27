# server-monitor
Server Monitor es una herramienta diseñada para funcionar en segundo plano en los servidores (principalmente fisicos) que se desean monitorear desde compulab. Permite acceder a informacion del hardware asi como ejecutar acciones simples de manera remota (prender, apagar y reiniciar). Funciona ejecutando un programa python en segundo plano que envia informacion por MQTT de manera periodica y escucha en un topico por si llega alguna orden a ejecutar.

| Parte | Ubicación | Función / Descripción |
|-------|-----------|--------------------|
| **Servidor** | Servidor físico/virtual a monitorear | Ejecuta **Server Monitor**, que recolecta información de hardware, publica datos y escucha comandos remotos (prender, apagar, reiniciar). |
| **Broker MQTT** | Raspberry Pi | Actúa como **centro de información**, recibe los datos del servidor y distribuye las órdenes entre el servidor y Home Assistant. |
| **Home Assistant** | Raspberry Pi | Interfaz para el usuario: muestra información de los servidores y permite enviar órdenes (acciones) a los servidores vía MQTT. |


## Funcionalidades

### 🧾 Logging
- Registro de acciones relevantes tanto del **Updater** como del **Monitor**.
- Los logs se almacenan en:
  - `server-monitor.py`
  - Carpeta `/monitor`
- Permite trazabilidad de eventos, errores y ejecuciones automáticas.

### Updater
Servicio encargado de mantener el sistema actualizado automáticamente.

1. Verifica conexión a internet y establece conexión con el broker **MQTT**.
3. Inicia un bucle infinito que:
   1. Ejecuta `monitor.py`.
   2. Consulta la versión local del `server-monitor`.
   3. Compara contra la última versión disponible en el repositorio.
   4. Si la versión remota es superior:
      - Descarga y actualiza los archivos locales.
      - Reinicia el `monitor.py`.
   5. Se publica el estado de la version en `/update/state` 
   6. Espera **10 minutos** antes de repetir el ciclo.

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
  
## Servidores donde esta instalado el server-monitor:

1. Compulab
   - Server-1
   - Server-2
   - Server-3
   - Server-5
   - Server-6
   - Server-7
   - Mark-PC
   - Martin-PC
2. Buques
   - Huyu 908
   - Huyu 961
   - Huyu 962
   - Hu Shun Yu 06
   - Hu Shun Yu 07
   - Hu Shun Yu 08
   - Puente Valdes
3. Clientes
   1. San Isidro
      - Server-1
      - Server-2
      - Server-3
      - Server-4
   2. Bricel
      - Server-1
   4. Cigalfer
      - Server-1
   6. RV Racing
      - Server-1
   8. Hydra
      - Server-1
   10. Holas
       - Server-1
   12. Greciamar
       - Server-1
   14. Santhor
       - Server-1
       - Server-2
   16. La Escalerona
       - Server-1
   18. Altamare
       - Server-1
   20. Ecoprom
       - Server-1
   22. Seafresh
       - Server-1
   24. Colorshop
       - Server-1
   26. Fabri
       - Server-1
       - Server-2

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
pip install wmi psutil python-dotenv paho-mqtt requests && pip install --pre pythonnet==3.1.0-rc0

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
2. Abrir el archivo `.env` y modificar `MQTT_SERVER` agregando el nombre del servidor
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

