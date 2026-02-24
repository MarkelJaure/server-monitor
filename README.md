# server-monitor
Herramienta de monitoreo de servidores integrada a home assistant


requiere instalacion de
pip install wmi psutil python-dotenv paho-mqtt requests

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
pip install wmi psutil python-dotenv paho-mqtt requests
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


Como activar Wake on LAN en un servidor

Si la maquina es Beelink Mini-pc
Administrador de Dispositivos
Buscar la placa de red por al que esta conectada (Ethernet o wifi)
Administración de energía
Check en 
Permitir que este dispositivo reactive el equipo
Permitirsolo un magic packer para reactivar el equipo

Ingresar al Mikrotik del router que en el que esta conectado el servidor
IP -> Services
Habilitar www

En el home assistant:
Abrir el configuration.yaml
Agregar un rest_command con:
- La ip del MK
- credenciales del winbox
- MAC del servidor a prender
Abrir el scripts.yaml
Crear un script que ejecute el rest command y agregue un mensaje MQTT en el topico del servidor

En el mikrotik del barco:
IP -> Firewall -> Filter Rules
Agregar una rule
Chain: Input
Src. Address List IPs: Compulab
In. Interface List: WAN
Action: Accept

