import json
import os
from pathlib import Path
import requests
from requests.auth import HTTPBasicAuth

def load_env_file(filepath: Path = Path(__file__).resolve().parent / ".env"):
    """Carga variables desde un archivo .env si existe, sin sobreescribir variables del sistema."""
    if not filepath.exists():
        return
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
    except Exception:
        pass

# Cargar variables locales desde .env si existe
load_env_file()

# ================= CREDENCIALES Y CONFIGURACIÓN =================
# Rellena estos campos con tus datos de Jira y Slack
# (o configúralos mediante variables de entorno o archivo .env):
JIRA_DOMAIN = os.getenv("JIRA_DOMAIN", "tu-dominio.atlassian.net")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "tu-correo@ejemplo.com")
JIRA_TOKEN = os.getenv("JIRA_TOKEN", "tu_api_token_de_jira")
PROJECT_KEY = os.getenv("PROJECT_KEY", "TU_PROYECTO")
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK", "https://hooks.slack.com/services/tu/webhook/url")

# PARAMETROS OPERATIVOS
TIMEOUT_SECONDS = 15
SKIP_DUPLICATES = True
DB_FILE = Path(__file__).resolve().parent / "tickets_procesados.json"

def configuration_validate() -> bool:
    """Valida que los parámetros de configuración y credenciales sean válidos."""
    errors = []
    if not JIRA_DOMAIN or "tu-dominio" in JIRA_DOMAIN or "ejemplo" in JIRA_DOMAIN:
        errors.append("JIRA_DOMAIN no está configurado (debes reemplazar 'tu-dominio.atlassian.net').")
    if not JIRA_EMAIL or "tu-correo" in JIRA_EMAIL or "@" not in JIRA_EMAIL or "ejemplo" in JIRA_EMAIL:
        errors.append("JIRA_EMAIL no es un correo electrónico válido.")
    if not JIRA_TOKEN or "tu_api_token" in JIRA_TOKEN:
        errors.append("JIRA_TOKEN no está configurado (debes generar tu API Token en Atlassian).")
    if not PROJECT_KEY or "TU_PROYECTO" in PROJECT_KEY:
        errors.append("PROJECT_KEY no está definido (debes indicar la clave de tu proyecto Jira).")
    if not SLACK_WEBHOOK or not SLACK_WEBHOOK.startswith("http") or "tu/webhook" in SLACK_WEBHOOK:
        errors.append("SLACK_WEBHOOK no tiene una URL válida (debes colocar la URL de Incoming Webhook de Slack).")

    if errors:
        print("[ERROR] Errores en la configuración:")
        for err in errors:
            print(f"- {err}")
        return False
    return True

def load_processed_tickets() -> set:
    """Lee el registro local de tickets ya alertados."""
    if not DB_FILE.exists():
        return set()
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return set(data)
    except Exception as e:
        print(f"[AVISO] No se pudo leer {DB_FILE.name} ({e}). Se creará un registro nuevo.")
    return set()


def save_processed_tickets(ticket_key: str, processed: set):
    """Registra en disco un ticket que ha sido alertado con éxito."""
    processed.add(ticket_key)
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(list(processed)), f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[AVISO] Error al guardar el ticket {ticket_key} en el registro local: {e}")

def obtain_tickets(domain: str, email: str, token: str, project_key: str) -> list:
    """Consulta los tickets abiertos en Jira con manejo seguro de errores de red y parseo."""
    url = f"https://{domain}/rest/api/3/search/jql"
    auth = HTTPBasicAuth(email, token)
    headers = {"Accept": "application/json"}
    query = {
        "jql": f"project = {project_key} AND statusCategory != Done",
        "fields": "summary,status",
        "maxResults": 50
    }

    print(f"[INFO] Buscando tickets en Jira ({domain})...")
    try:
        response = requests.get(url, headers=headers, auth=auth, params=query, timeout=TIMEOUT_SECONDS)
    except requests.exceptions.Timeout:
        print(f"[ERROR] Se agotó el tiempo de espera ({TIMEOUT_SECONDS}s) al contactar a Jira.")
        return []
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Error de red al consultar Jira: {e}")
        return []

    if response.status_code != 200:
        print(f"[ERROR] Error al consultar Jira (Código HTTP {response.status_code}):")
        try:
            print(json.dumps(response.json(), indent=2))
        except Exception:
            print(response.text)
        return []

    try:
        data = response.json()
    except json.JSONDecodeError:
        print("[ERROR] La respuesta recibida de Jira no es un JSON válido.")
        return []

    if not isinstance(data, dict):
        print("[ERROR] La respuesta de Jira no tiene la estructura esperada.")
        return []

    tickets = data.get("issues")
    if not isinstance(tickets, list):
        print("[AVISO] No se encontró la lista 'issues' en la respuesta de Jira.")
        return []

    return tickets

def classify_ticket(summary: str) -> str:
    """Clasifica el ticket por palabras clave en su asunto/resumen."""
    summary_lower = (summary or "").lower()

    # Es posible reemplazarlo por un algoritmo de Machine Learning para mejorar la precisión en la clasificación de los tickets
    if any(word in summary_lower for word in ["acceso", "contraseña", "contrasena", "workspace", "mfa", "login", "password"]):
        return "Gestión de Accesos (Prioridad Media)"
    elif any(word in summary_lower for word in ["wi-fi", "wifi", "red", "internet", "dns", "conexion", "conexión"]):
        return "Conectividad y Redes (Prioridad Alta)"
    elif any(word in summary_lower for word in ["mac", "windows", "impresora", "hardware", "laptop", "pc"]):
        return "Soporte de Hardware/OS (Prioridad Media)"

    return "Soporte General / Indefinido"


def escape_slack(text: str) -> str:
    """Escapa caracteres reservados de Slack (<, >, &) para preservar el formato del mensaje."""
    if not text:
        return "Sin descripción"
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .strip()
    )

def send_slack_alert(webhook_url: str, domain: str, ticket_key: str, summary: str, status_name: str, category: str) -> bool:
    """Envía la alerta a Slack con validación de respuesta y timeouts."""
    summary_cleaned = escape_slack(summary)
    slack_message = {
        "text": (
            f"🚨 *Nuevo Ticket Clasificado por el Bot* 🚨\n"
            f"🎫 *ID:* {ticket_key}\n"
            f"📝 *Problema:* {summary_cleaned}\n"
            f"📊 *Estado:* {status_name}\n"
            f"🏷️ *Categoría Sugerida:* {category}\n"
            f"🔗 <https://{domain}/browse/{ticket_key}|Ver en Jira>"
        )
    }

    try:
        res = requests.post(webhook_url, json=slack_message, timeout=TIMEOUT_SECONDS)
        if res.status_code == 200:
            print(f"[OK] Alerta enviada con éxito para el ticket {ticket_key}")
            return True
        else:
            print(f"[ERROR] Error enviando {ticket_key} a Slack (HTTP {res.status_code}): {res.text}")
            return False
    except requests.exceptions.Timeout:
        print(f"[ERROR] Tiempo de espera agotado ({TIMEOUT_SECONDS}s) al enviar {ticket_key} a Slack.")
        return False
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Error de red al enviar {ticket_key} a Slack: {e}")
        return False

def main():
    if not configuration_validate():
        return

    tickets = obtain_tickets(JIRA_DOMAIN, JIRA_EMAIL, JIRA_TOKEN, PROJECT_KEY)
    print(f"[INFO] Tickets encontrados: {len(tickets)}")

    if not tickets:
        print("[INFO] No se encontraron tickets pendientes.")
        return

    processed = load_processed_tickets() if SKIP_DUPLICATES else set()
    sent_count = 0
    skipped_count = 0
    failed_count = 0

    for issue in tickets:
        if not isinstance(issue, dict):
            print("[AVISO] Registro de ticket con formato inválido, omitiendo...")
            continue

        ticket_key = issue.get("key")
        if not ticket_key:
            print("[AVISO] Se encontró un elemento sin campo 'key', omitiendo...")
            continue

        if SKIP_DUPLICATES and ticket_key in processed:
            print(f"[INFO] [{ticket_key}] Ya fue notificado previamente. Omitiendo.")
            skipped_count += 1
            continue
        fields = issue.get("fields")
        if not isinstance(fields, dict):
            fields = {}

        summary = fields.get("summary") or "Sin descripción"

        status_obj = fields.get("status")
        status_name = status_obj.get("name", "Desconocido") if isinstance(status_obj, dict) else "Desconocido"

        category = classify_ticket(summary)
        
        success = send_slack_alert(
            webhook_url=SLACK_WEBHOOK,
            domain=JIRA_DOMAIN,
            ticket_key=ticket_key,
            summary=summary,
            status_name=status_name,
            category=category
        )

        if success:
            if SKIP_DUPLICATES:
                save_processed_tickets(ticket_key, processed)
            sent_count += 1
        else:
            failed_count += 1

    print("\n--- Resumen de ejecucion ---")
    print(f"Alertas enviadas a Slack: {sent_count}")
    print(f"Omitidos (ya notificados): {skipped_count}")
    if failed_count > 0:
        print(f"Fallos al notificar: {failed_count}")


if __name__ == "__main__":
    main()
