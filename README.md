# 🚀 Damaju Status Monitor

Sistema de monitoreo de servicios en tiempo real con alertas automáticas vía Telegram y dashboard web interactivo.

## 📋 Características

- ✅ **Monitoreo automático** cada 5 minutos
- 🔔 **Alertas inteligentes** vía Telegram (caídas y recuperaciones)
- 📊 **Dashboard web** con métricas en tiempo real
- 📈 **Historial completo** de uptime y response times
- 🎯 **Validación robusta** con doble confirmación
- 🌐 **Deployment automático** con GitHub Pages

## 🏗️ Arquitectura

```
🔄 Cron Externo (cada 5 min)
    ↓
📞 GitHub Actions API (dispatch)
    ↓
🚀 Workflow ejecuta check_status.py
    ↓
📊 Actualiza status.json
    ↓
💬 Envía alertas a Telegram (si hay cambios)
    ↓
🌐 GitHub Pages sirve dashboard
```

## 🚀 Setup Rápido

### 1. Clonar Repositorio

```bash
git clone https://github.com/danielserna0/damaju-status.git
cd damaju-status
```

### 2. Instalar Dependencias

```bash
pip install -r requirements.txt
```

### 3. Configurar Secrets en GitHub

Ve a **Settings** → **Secrets and variables** → **Actions** y agrega:

- `TELEGRAM_TOKEN`: Token del bot de Telegram
- `TELEGRAM_CHAT_ID`: ID del chat donde enviar alertas

### 4. Ejecutar Manualmente

```bash
python check_status.py
```

## 🔧 Configuración

### Servicios Monitoreados

Edita `check_status.py` línea 8-17:

```python
SITES = [
    "https://app-marko.damaju.com.co",
    "https://damaju.com.co",
    # ... agregar más servicios
]
```

### Parámetros de Monitoreo

```python
TIMEOUT_SECONDS = 60      # Timeout por petición
MAX_HISTORY = 2016        # Máximo de registros históricos
```

## 📱 Telegram Bot Setup

### 1. Crear Bot

1. Habla con [@BotFather](https://t.me/botfather)
2. Envía `/newbot`
3. Sigue las instrucciones
4. Guarda el **token** que te da

### 2. Obtener Chat ID

1. Envía un mensaje a tu bot
2. Visita: `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Busca `"chat":{"id":...}` en la respuesta
4. Guarda ese **chat_id**

## 🎯 Lógica de Alertas

### Confirmación de Caídas

```
Ejecución 1: Fallo → pending_down = true (sin alerta)
Ejecución 2: Fallo → DOWN confirmado (alerta enviada)
```

### Alertas de Recuperación

```
Servicio DOWN → Servicio UP → Alerta de recuperación
```

### Formato de Mensajes

**Caída:**
```
🔴 Damaju Status
CAÍDO: damaju, marko, ops
13/03 21:40
[🔍 Revisar]
```

**Recuperación:**
```
🟢 Damaju Status
RECUPERADO: damaju, marko
13/03 21:45
[🔍 Revisar]
```

## 📊 Dashboard

Accede al dashboard en: **https://status.damaju.com.co/**

### Métricas Disponibles

- **Servicios activos/caídos**
- **Uptime 24h promedio**
- **Response time promedio**
- **Historial de incidentes (7 días)**
- **Sparklines de disponibilidad**

## 🔄 Ejecución Automática

El sistema usa un **cron externo** que ejecuta:

```bash
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/danielserna0/damaju-status/actions/workflows/check-status.yml/dispatches \
  -d '{"ref":"main"}'
```

**Frecuencia:** Cada 5 minutos

## 🧪 Testing

```bash
# Ejecutar checks manualmente
python check_status.py

# Ver logs en GitHub Actions
# Repository → Actions → Check Status
```

## 📁 Estructura del Proyecto

```
damaju-status/
├── .github/
│   └── workflows/
│       └── check-status.yml    # GitHub Actions workflow
├── check_status.py             # Script principal de monitoreo
├── index.html                  # Dashboard web
├── status.json                 # Datos de estado (auto-generado)
├── requirements.txt            # Dependencias Python
├── CNAME                       # Dominio personalizado
└── README.md                   # Esta documentación
```

## 🛠️ Troubleshooting

### No llegan alertas de Telegram

1. Verifica que los secrets estén configurados
2. Revisa logs en GitHub Actions
3. Verifica que el bot tenga permisos para enviar mensajes

### Dashboard no actualiza

1. Verifica que GitHub Pages esté habilitado
2. Espera 2-3 minutos para propagación de CDN
3. Haz hard refresh: `Ctrl+F5` o `Cmd+Shift+R`

### Falsos positivos

El sistema requiere **2 fallos consecutivos** antes de alertar. Si persisten:

1. Aumenta `TIMEOUT_SECONDS` en `check_status.py`
2. Revisa logs para ver errores específicos

## 📈 Roadmap

- [ ] Configuración externalizada (config.json)
- [ ] Métricas avanzadas (MTTR, frecuencia de incidentes)
- [ ] Health check del monitor
- [ ] Tests automatizados
- [ ] Concurrent checks con asyncio
- [ ] Gráficos históricos interactivos

## 📄 Licencia

Proyecto privado de Damaju.

## 👥 Contribuidores

- **Daniel Serna** - Desarrollo inicial

## 📞 Soporte

Para problemas o preguntas, contacta al equipo de DevOps de Damaju.