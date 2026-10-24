# Laboratorio de Ticketing con Jira y Python

Script en Python diseñado para automatizar el triaje de Nivel 1 en mesas de ayuda. Consume la API REST de Jira, clasifica incidentes por palabras clave (Redes, Accesos, Hardware) y notifica al equipo vía Slack.

---

## 🚀 Características
- **Integración con Jira Cloud REST API v3**: Consulta tickets abiertos por proyecto mediante JQL (`statusCategory != Done`).
- **Clasificación Automática**: Categoriza incidencias en áreas clave (*Gestión de Accesos*, *Conectividad y Redes*, *Soporte de Hardware/OS*, *Soporte General*).
- **Notificaciones Enriquecidas en Slack**: Envía mensajes con ID, resumen, estado, categoría y enlace directo al ticket en Jira.
- **Control de Duplicados**: Guarda localmente los tickets notificados en `tickets_procesados.json` para evitar spam de alertas repetidas.
- **Seguridad**: Configurable vía variables de entorno o archivo `.env` para evitar exponer credenciales en repositorios públicos.
- **Manejo Seguro de Errores**: Control de timeouts, validación previa de configuración y escape de caracteres para Slack.

---

## 📋 Requisitos Previos
1. **Python 3.8 o superior**.
2. Una instancia de **Jira Cloud** con:
   - Permiso de lectura en el proyecto deseado.
   - [API Token de Atlassian](https://id.atlassian.com/manage-profile/security/api-tokens).
3. Un canal de **Slack** con un [Incoming Webhook](https://api.slack.com/messaging/webhooks) configurado.

---

## 🛠️ Instalación

1. **Clonar el repositorio**:
   ```bash
   git clone https://github.com/Anncor/Laboratorio-de-Ticketing-con-Jira-y-Python.git
   cd Laboratorio-de-Ticketing-con-Jira-y-Python
   ```

2. **Crear y activar un entorno virtual** (recomendado):
   ```bash
   # En Windows
   python -m venv .venv
   .venv\Scripts\activate

   # En Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Instalar dependencias**:
   ```bash
   pip install -r requirements.txt
   ```

---

## ⚙️ Configuración

Puedes configurar tus credenciales de dos formas:

### Opción 1: Mediante archivo `.env` (Recomendado)
Copia la plantilla `.env.example` a `.env`:
```bash
cp .env.example .env
```
Abre `.env` y rellena tus datos:
```env
JIRA_DOMAIN=tu-dominio.atlassian.net
JIRA_EMAIL=tu-correo@ejemplo.com
JIRA_TOKEN=tu_api_token_de_jira
PROJECT_KEY=TU_PROYECTO
SLACK_WEBHOOK=https://hooks.slack.com/services/tu/webhook/url
```

### Opción 2: Editando directamente `it_triaje_bot.py`
Abre `it_triaje_bot.py` y sustituye los valores de prueba por tus credenciales:
```python
JIRA_DOMAIN = "tu-dominio.atlassian.net"
JIRA_EMAIL = "tu-correo@ejemplo.com"
JIRA_TOKEN = "tu_api_token_de_jira"
PROJECT_KEY = "TU_PROYECTO"
SLACK_WEBHOOK = "https://hooks.slack.com/services/tu/webhook/url"
```

---

## ▶️ Ejecución

Ejecuta el bot con:
```bash
python it_triaje_bot.py
```

### Flujo de Ejecución:
1. Valida que los parámetros y credenciales no tengan los valores por defecto ni estén vacíos.
2. Consulta Jira mediante JQL para listar las incidencias no resueltas.
3. Evalúa si el ticket ya fue alertado previamente.
4. Si es nuevo, analiza el texto del asunto, determina la categoría y envía la alerta a Slack.
5. Registra el ID del ticket procesado en `tickets_procesados.json`.
6. Muestra un resumen detallado en consola.
