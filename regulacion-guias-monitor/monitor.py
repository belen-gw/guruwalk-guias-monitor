#!/usr/bin/env python3
"""
Agente de monitorización de regulación de guías de turismo en España, Italia y Austria.

Modos de uso:
  python monitor.py --detect-only   → detecta cambios, guarda pending_changes.json, NO envía email
  python monitor.py --send-pending  → lee pending_changes.json y envía el email de alerta
  python monitor.py                 → modo completo sin confirmación (ejecución local)
"""

import argparse
import difflib
import hashlib
import json
import os
import smtplib
import sys
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup

# ──────────────────────────────────────────
# Configuración
# ──────────────────────────────────────────
GMAIL_USER         = os.environ.get("GMAIL_USER", "belen@guruwalk.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
EMAIL_DEST         = os.environ.get("EMAIL_DEST", "belen@guruwalk.com")
SNAPSHOTS_FILE     = "snapshots.json"
PENDING_FILE       = "pending_changes.json"

# ──────────────────────────────────────────
# Fuentes a monitorizar
# ──────────────────────────────────────────
SOURCES = [
    # ── Nacional (España) ──
    {
        "name": "BOE – Legislación 'guía turístico'",
        "region": "Nacional",
        "url": "https://www.boe.es/buscar/legislacion.php?campo%5B0%5D=TIT&dato%5B0%5D=gu%C3%ADa+tur%C3%ADstico&operador%5B0%5D=Y&lang=es&orden=pub&accion=Buscar",
        "css_selector": "ul.resultado-busqueda",
    },
    {
        "name": "BOE – Legislación 'guía de turismo'",
        "region": "Nacional",
        "url": "https://www.boe.es/buscar/legislacion.php?campo%5B0%5D=TIT&dato%5B0%5D=gu%C3%ADa+de+turismo&operador%5B0%5D=Y&lang=es&orden=pub&accion=Buscar",
        "css_selector": "ul.resultado-busqueda",
    },
    {
        "name": "Ministerio de Turismo – Regulación",
        "region": "Nacional",
        "url": "https://www.mtes.gob.es/es/turismo/politica-turistica-estatal/regulacion/",
        "css_selector": "div.rte",
    },
    # ── Comunidades Autónomas (España) ──
    {
        "name": "Andalucía – Guías turísticos",
        "region": "Andalucía",
        "url": "https://www.juntadeandalucia.es/organismos/turismoculturaydepor/servicios/procedimientos/detalle/13398.html",
        "css_selector": "div#procedimiento",
    },
    {
        "name": "Comunidad de Madrid – Guías turísticos",
        "region": "Madrid",
        "url": "https://www.comunidad.madrid/servicios/turismo/guias-turisticos",
        "css_selector": "div.layout-container",
    },
    {
        "name": "Cataluña – Guies de turisme",
        "region": "Cataluña",
        "url": "https://empresa.gencat.cat/ca/treb_empreses/tur/formacioturistica/guiesdeturisme/",
        "css_selector": "div#contingut",
    },
    {
        "name": "Comunitat Valenciana – Guías de turismo",
        "region": "Valencia",
        "url": "https://www.gva.es/es/inicio/procedimientos?id_proc=20261",
        "css_selector": "div#procedimiento",
    },
    {
        "name": "Canarias – Guías turísticos",
        "region": "Canarias",
        "url": "https://www.gobiernodecanarias.org/turismo/temas/empresas_y_actividades/guias_de_turismo/",
        "css_selector": "div#content",
    },
    {
        "name": "Galicia – Guías de turismo",
        "region": "Galicia",
        "url": "https://www.xunta.gal/dog/Publicados/2011/20110202/AnuncioC3B0-250111-3095_gl.html",
        "css_selector": "div#content",
    },
    {
        "name": "Illes Balears – Guies de turisme",
        "region": "Baleares",
        "url": "https://www.caib.es/sites/turisme/es/guies_de_turisme/",
        "css_selector": "div.portlet-body",
    },
    {
        "name": "País Vasco – Guías de turismo",
        "region": "País Vasco",
        "url": "https://www.euskadi.eus/informacion/guias-de-turismo/web01-a2turism/es/",
        "css_selector": "div.contenidos",
    },
    {
        "name": "Aragón – Autorización guía de turismo",
        "region": "Aragón",
        "url": "https://www.aragon.es/tramitador/-/tramite/autorizacion-ejercer-actividad-guia-turismo",
        "css_selector": "div.tramite-content",
    },
    {
        "name": "Castilla y León – Guías de turismo",
        "region": "Castilla y León",
        "url": "https://tramitacastillayleon.jcyl.es/web/jcyl/AdministracionElectronica/es/Formularios/1284227483898/1/1/es/",
        "css_selector": "div.contenido",
    },
    {
        "name": "Castilla-La Mancha – Guías de turismo",
        "region": "Castilla-La Mancha",
        "url": "https://industria.castillalamancha.es/turismo/guias-turismo",
        "css_selector": "div.content",
    },
    {
        "name": "Región de Murcia – Guías turísticos",
        "region": "Murcia",
        "url": "https://www.carm.es/web/pagina?IDCONTENIDO=23494&IDTIPO=100&RASTRO=c108$m",
        "css_selector": ".fichaSeccion:not(#seccion-solicitudes)",
    },
    {
        "name": "Navarra – Guías de turismo",
        "region": "Navarra",
        "url": "https://www.navarra.es/es/tramites/on/detalle-tramite/?id=21978",
        "css_selector": "div.tramite",
    },
    {
        "name": "Extremadura – Guías de turismo",
        "region": "Extremadura",
        "url": "https://www.juntaex.es/w/procedimiento/autorizacion-profesional-de-guia-de-turismo",
        "css_selector": "#tramite_finalidad, #tramite_requisitos, #tramite_documentacion, #tramite_normativa, #tramite_resolucion, #tramite_gestor",
    },
    {
        "name": "Asturias – Guías de turismo",
        "region": "Asturias",
        "url": "https://sede.asturias.es/tramite/guia-de-turismo",
        "css_selector": "div.tramite-body",
    },
    # ── Italia ──
    {
        "name": "Ministero del Turismo – Guide turistiche (normativa)",
        "region": "Italia",
        "url": "https://www.ministeroturismo.gov.it/guide-turistiche/",
        "css_selector": "div.entry-content",
    },
    {
        "name": "Ministero del Turismo – Riforma guide turistiche",
        "region": "Italia",
        "url": "https://www.ministeroturismo.gov.it/riforma-delle-guide-turistiche/",
        "css_selector": "div.entry-content",
    },
    {
        "name": "Lazio – Guide turistiche",
        "region": "Lazio",
        "url": "https://www.regione.lazio.it/cittadini/turismo-cultura-sport/turismo/guide-turistiche",
        "css_selector": "div.field-items",
    },
    {
        "name": "Toscana – Guide turistiche",
        "region": "Toscana",
        "url": "https://www.regione.toscana.it/-/guide-turistiche",
        "css_selector": "div.portlet-body",
    },
    {
        "name": "Veneto – Guide turistiche",
        "region": "Veneto",
        "url": "https://www.regione.veneto.it/web/turismo/guide-turistiche",
        "css_selector": "div#mainContent",
    },
    {
        "name": "Lombardia – Guide turistiche",
        "region": "Lombardia",
        "url": "https://www.regione.lombardia.it/wps/portal/istituzionale/HP/temi-e-focus/turismo/guide-turistiche",
        "css_selector": "div.it-page-sections-container",
    },
    {
        "name": "Campania – Guide turistiche",
        "region": "Campania",
        "url": "https://www.regione.campania.it/regione/it/tematiche/scheda-tema?id=77",
        "css_selector": "div.container",
    },
    # ── Austria ──
    {
        "name": "WKO Federal – Fremdenführer (Bundesebene)",
        "region": "Austria",
        "url": "https://www.wko.at/branchen/tourismus-freizeitwirtschaft/reisebuerossowie-reiseveranstalter/fremdenverkehr",
        "css_selector": "div.content-main",
    },
    {
        "name": "WKO Wien – Fremdenführer Wien",
        "region": "Wien",
        "url": "https://www.wkw.at/de/branchen/tourismus-freizeitwirtschaft/reisebueros-reiseveranstalter/fremdenverkehr/",
        "css_selector": "div.content",
    },
    {
        "name": "WKO Salzburg – Fremdenführer Salzburg",
        "region": "Salzburg",
        "url": "https://www.wks.at/branchenvertretungen/sparte-tourismus-und-freizeitwirtschaft/fachgruppe-reisebueros-reiseveranstalter/fremdenverkehr.html",
        "css_selector": "div.content",
    },
    {
        "name": "WKO Tirol – Fremdenführer Tirol",
        "region": "Tirol",
        "url": "https://www.wktirol.at/branchen/tourismus-freizeitwirtschaft/reisebuerossowie-reiseveranstalter/fremdenverkehr",
        "css_selector": "div.content-main",
    },
    # ── Artículo propio GuruWalk ──
    {
        "name": "GuruWalk Support – Obtener carnet de guía",
        "region": "GuruWalk",
        "url": "https://support.guruwalk.com/portal/es/kb/soporte-para-gurus/trámites/obtener-el-carnet-de-guía",
        "css_selector": "div.article-body",
    },
]


# ──────────────────────────────────────────
# Utilidades
# ──────────────────────────────────────────

def fetch_content(source: dict) -> str | None:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(source["url"], headers=headers, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        if source.get("css_selector"):
            # select() soporta selectores múltiples separados por comas
            elements = soup.select(source["css_selector"])
            if elements:
                return " ".join(el.get_text(separator=" ", strip=True) for el in elements)
        body = soup.find("body")
        return body.get_text(separator=" ", strip=True) if body else ""
    except requests.RequestException as e:
        print(f"  !! Error al acceder a {source['name']}: {e}")
        return None


def compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_diff_html(old_text: str, new_text: str) -> str:
    """Genera un bloque HTML con las diferencias entre dos textos."""
    old_words = old_text.split()
    new_words = new_text.split()
    diff = list(difflib.ndiff(old_words, new_words))

    removed = [t[2:] for t in diff if t.startswith("- ")]
    added   = [t[2:] for t in diff if t.startswith("+ ")]

    lines = []
    if removed:
        lines.append(
            '<div style="background:#fff0f0;padding:8px;margin:4px 0;border-left:3px solid #c0392b;">'
            '<span style="color:#c0392b;font-weight:bold;">➖ Eliminado:</span> '
            + " ".join(f'<span style="background:#ffd7d7">{w}</span>' for w in removed[:50])
            + ("..." if len(removed) > 50 else "")
            + "</div>"
        )
    if added:
        lines.append(
            '<div style="background:#f0fff0;padding:8px;margin:4px 0;border-left:3px solid #27ae60;">'
            '<span style="color:#27ae60;font-weight:bold;">➕ Añadido:</span> '
            + " ".join(f'<span style="background:#d4f7d4">{w}</span>' for w in added[:50])
            + ("..." if len(added) > 50 else "")
            + "</div>"
        )

    return "\n".join(lines) if lines else "<p style='color:#888'>Sin detalles de diff disponibles.</p>"


def load_json(path: str) -> dict | list:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ──────────────────────────────────────────
# Email
# ──────────────────────────────────────────

def build_alert_html(changes: list) -> str:
    date_str = datetime.today().strftime("%d/%m/%Y")
    rows = ""
    for ch in changes:
        diff_section = ""
        if ch.get("diff_html"):
            diff_section = f"""
          <tr>
            <td colspan="3" style="padding:8px 10px 16px 10px;">
              <div style="font-size:12px;color:#555;margin-bottom:4px;">
                <strong>Cambios detectados:</strong>
              </div>
              {ch['diff_html']}
            </td>
          </tr>"""
        rows += f"""
        <tr>
          <td style="padding:10px; border-bottom:1px solid #eee; font-weight:bold; color:#c0392b;">
            {ch['region']}
          </td>
          <td style="padding:10px; border-bottom:1px solid #eee;">{ch['name']}</td>
          <td style="padding:10px; border-bottom:1px solid #eee;">
            <a href="{ch['url']}" style="color:#2980b9;">Ver fuente</a>
          </td>
        </tr>
        {diff_section}"""

    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;max-width:700px;margin:auto;">
      <div style="background:#c0392b;color:white;padding:20px;border-radius:6px 6px 0 0;">
        <h2 style="margin:0;">Alerta: Cambios en regulación de guías turísticos</h2>
        <p style="margin:4px 0 0 0;opacity:.85;">{date_str} · Confirmado por Belén</p>
      </div>
      <div style="background:#fff5f5;padding:16px;border:1px solid #f5c6c6;border-top:none;">
        <p>Se han detectado <strong>{len(changes)} cambio(s)</strong> en las fuentes
        oficiales. Revisa cada enlace y actualiza el artículo de soporte si procede.</p>
      </div>
      <table style="width:100%;border-collapse:collapse;border:1px solid #eee;border-top:none;">
        <thead style="background:#f8f8f8;">
          <tr>
            <th style="padding:10px;text-align:left;">Región</th>
            <th style="padding:10px;text-align:left;">Fuente</th>
            <th style="padding:10px;text-align:left;">Enlace</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      <div style="margin-top:16px;padding:12px;background:#f0f7ff;
                  border-left:4px solid #2980b9;border-radius:4px;">
        <strong>Artículo de soporte a revisar:</strong><br>
        <a href="https://support.guruwalk.com/portal/es/kb/soporte-para-gurus/tr%C3%A1mites/obtener-el-carnet-de-gu%C3%ADa">
          support.guruwalk.com – Obtener el carnet de guía
        </a>
      </div>
      <p style="color:#aaa;font-size:11px;margin-top:20px;">
        Generado automáticamente por el agente de monitorización de GuruWalk.
      </p>
    </body></html>"""


def build_ok_html() -> str:
    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;max-width:600px;margin:auto;">
      <div style="background:#27ae60;color:white;padding:20px;border-radius:6px;">
        <h2 style="margin:0;">Todo OK – Sin cambios detectados esta semana</h2>
        <p style="margin:4px 0 0 0;opacity:.85;">{datetime.today().strftime('%d/%m/%Y')}</p>
      </div>
      <p style="margin-top:16px;">La revisión de las <strong>{len(SOURCES)} fuentes</strong>
      no ha detectado ningún cambio en la regulación de guías de turismo
      en España, Italia y Austria.</p>
      <p style="color:#aaa;font-size:11px;">
        Generado automáticamente por el agente de monitorización de GuruWalk.
      </p>
    </body></html>"""


def send_email(subject: str, html_body: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = EMAIL_DEST
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, EMAIL_DEST, msg.as_string())
    print(f"  -> Email enviado a {EMAIL_DEST}")


# ──────────────────────────────────────────
# Modos de ejecución
# ──────────────────────────────────────────

def run_detect_only():
    """
    Detecta cambios y guarda el resultado en pending_changes.json.
    NO envía ningún email. El workflow pausará aquí para que apruebes.
    """
    print(f"\n{'='*60}")
    print(f"  MODO: Solo detección (sin envío)")
    print(f"  Fecha: {datetime.today().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    snapshots     = load_json(SNAPSHOTS_FILE)
    changes       = []
    new_snapshots = {}
    is_first_run  = len(snapshots) == 0

    for source in SOURCES:
        print(f"Revisando: [{source['region']}] {source['name']}")
        content = fetch_content(source)

        if content is None:
            print("  -> Sin contenido. Saltando.\n")
            if source["url"] in snapshots:
                new_snapshots[source["url"]] = snapshots[source["url"]]
            continue

        current_hash     = compute_hash(content)
        prev_data        = snapshots.get(source["url"], {})
        previous_hash    = prev_data.get("hash")
        previous_content = prev_data.get("content", "")

        if previous_hash is None:
            print("  -> Primera vez registrada.\n")
        elif current_hash != previous_hash:
            print(f"  -> *** CAMBIO DETECTADO ***\n")
            diff_html    = compute_diff_html(previous_content, content[:5000])
            change_entry = dict(source)
            change_entry["diff_html"] = diff_html
            changes.append(change_entry)
        else:
            print("  -> Sin cambios.\n")

        new_snapshots[source["url"]] = {
            "hash":         current_hash,
            "name":         source["name"],
            "region":       source["region"],
            "last_checked": datetime.today().isoformat(),
            "content":      content[:5000],
        }
        time.sleep(1)

    save_json(SNAPSHOTS_FILE, new_snapshots)

    # ── Resumen legible en los logs de GitHub Actions ──
    print("\n" + "="*60)
    print("  RESUMEN DE LA DETECCIÓN")
    print("="*60)
    if is_first_run:
        print("  Primera ejecución: snapshots iniciales guardados.")
        print("  No hay cambios que revisar todavía.")
    elif changes:
        print(f"\n  Se han detectado CAMBIOS en {len(changes)} fuente(s):\n")
        for ch in changes:
            print(f"  [{ch['region']}] {ch['name']}")
            print(f"   -> {ch['url']}\n")
        print("  Si apruebas este workflow, se enviará el email de alerta.")
    else:
        print("  Sin cambios detectados en ninguna fuente.")
        print("  Si apruebas este workflow, se enviará el email semanal de 'Todo OK'.")
    print("="*60 + "\n")

    # Guarda los cambios pendientes para el paso de envío
    save_json(PENDING_FILE, {
        "date":         datetime.today().isoformat(),
        "is_first_run": is_first_run,
        "changes":      changes,
    })

    if changes:
        print("::notice title=Cambios detectados::"
              f"{len(changes)} fuente(s) han cambiado. Revisa el resumen de arriba.")
    elif is_first_run:
        print("::notice title=Primera ejecucion::Snapshots iniciales guardados.")
    else:
        print("::notice title=Sin cambios::Todas las fuentes están igual que la semana pasada.")


def run_send_pending():
    """
    Lee pending_changes.json (generado por --detect-only) y envía el email.
    Solo se ejecuta si Belén ha aprobado en GitHub Actions.
    """
    print(f"\n{'='*60}")
    print(f"  MODO: Envío de email (aprobado por Belén)")
    print(f"  Fecha: {datetime.today().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    if not GMAIL_APP_PASSWORD:
        print("ERROR: GMAIL_APP_PASSWORD no configurada. Saliendo.")
        sys.exit(1)

    pending = load_json(PENDING_FILE)
    if not pending:
        print("No se encontró pending_changes.json. Nada que enviar.")
        return

    changes      = pending.get("changes", [])
    is_first_run = pending.get("is_first_run", False)

    if is_first_run:
        print("Primera ejecución: no se envía email.")
        return

    date_str = datetime.today().strftime("%d/%m/%Y")

    if changes:
        subject = f"[GuruWalk] ⚠️ Cambios regulacion guias turisticos – {date_str}"
        html    = build_alert_html(changes)
        print(f"Enviando email de alerta con {len(changes)} cambio(s)...")
    else:
        subject = f"[GuruWalk] ✅ Sin cambios en regulacion guias – {date_str}"
        html    = build_ok_html()
        print("Enviando email de confirmación semanal 'Todo OK'...")

    send_email(subject, html)


def run_full():
    """Modo completo sin confirmación (útil para pruebas locales)."""
    print(f"\n{'='*60}")
    print(f"  MODO: Completo (sin confirmación)")
    print(f"  Fecha: {datetime.today().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    run_detect_only()
    run_send_pending()


# ──────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitor regulación guías turísticos")
    parser.add_argument("--detect-only",  action="store_true",
                        help="Solo detectar cambios, no enviar email")
    parser.add_argument("--send-pending", action="store_true",
                        help="Enviar email con los cambios ya detectados")
    args = parser.parse_args()

    if args.detect_only:
        run_detect_only()
    elif args.send_pending:
        run_send_pending()
    else:
        run_full()
