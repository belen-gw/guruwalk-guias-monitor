# Agente de Monitorización – Regulación Guías Turísticos España

Detecta cambios semanales en las fuentes oficiales de regulación de guías de turismo
en España (BOE, Ministerio de Turismo y 15 Comunidades Autónomas) y envía un email
de alerta a `belen@guruwalk.com`.

---

## Fuentes monitorizadas

| Región | Fuente |
|---|---|
| Nacional | BOE (2 búsquedas por término) |
| Nacional | Ministerio de Turismo – Regulación |
| Andalucía | Junta de Andalucía – Procedimiento guías |
| Madrid | Comunidad de Madrid – Guías turísticos |
| Cataluña | Gencat – Guies de turisme |
| Valencia | GVA – Guías de turismo |
| Canarias | Gobierno de Canarias – Guías |
| Galicia | Xunta de Galicia |
| Baleares | Govern Illes Balears |
| País Vasco | Euskadi – Guías de turismo |
| Aragón | Gobierno de Aragón |
| Castilla y León | JCyL |
| Castilla-La Mancha | Junta CLM |
| Murcia | CARM |
| Navarra | Gobierno de Navarra |
| Extremadura | Junta de Extremadura |
| Asturias | Principado de Asturias |
| GuruWalk | support.guruwalk.com (referencia) |

---

## Setup (hacer UNA sola vez)

### 1. Crear el repositorio en GitHub

1. Ve a [github.com](https://github.com) y haz clic en **New repository**
2. Nombre sugerido: `guruwalk-guias-monitor`
3. Visibilidad: **Private**
4. Sube todos los archivos de esta carpeta al repositorio

```bash
cd regulacion-guias-monitor
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/TU_USUARIO/guruwalk-guias-monitor.git
git push -u origin main
```

---

### 2. Crear App Password de Google

> Necesario para que el script pueda enviar emails desde belen@guruwalk.com

1. Accede a [myaccount.google.com/security](https://myaccount.google.com/security)
2. Asegúrate de tener **Verificación en 2 pasos** activada
3. Busca **Contraseñas de aplicación** (App passwords)
4. Crea una nueva con nombre: `GuruWalk Monitor`
5. Copia la contraseña de 16 caracteres generada

> **Nota para Google Workspace**: Si el botón de App Passwords no aparece, el administrador
> del Workspace debe activar "Allow users to manage their own app-specific passwords"
> en la consola de administración (admin.google.com > Security > Authentication).

---

### 3. Configurar los Secrets en GitHub

En tu repositorio de GitHub:

1. Ve a **Settings** > **Secrets and variables** > **Actions**
2. Haz clic en **New repository secret** y añade los tres siguientes:

| Nombre del secret | Valor |
|---|---|
| `GMAIL_USER` | `belen@guruwalk.com` |
| `GMAIL_APP_PASSWORD` | La contraseña de 16 caracteres del paso anterior |
| `EMAIL_DEST` | `belen@guruwalk.com` |

---

### 4. Primera ejecución manual (recomendado)

Antes de esperar al lunes, lanza el agente manualmente para crear los snapshots iniciales:

1. Ve a tu repositorio en GitHub
2. Haz clic en la pestaña **Actions**
3. Selecciona el workflow **Monitorizacion Regulacion Guias Turisticos**
4. Haz clic en **Run workflow** > **Run workflow**

La primera ejecución guardará los snapshots actuales como referencia.
A partir de la segunda ejecución (el próximo lunes), empezará a detectar cambios reales.

---

## Comportamiento del agente

| Situación | Acción |
|---|---|
| Primera ejecución | Guarda snapshots. No envía email. |
| Sin cambios | Envía email verde "Todo OK" confirmando la revisión |
| Cambios detectados | Envía email rojo con la lista de fuentes modificadas |
| URL inaccesible | Mantiene el snapshot anterior y continúa |

---

## Añadir o modificar fuentes

Edita la lista `SOURCES` en `monitor.py`. Cada fuente tiene:

```python
{
    "name": "Nombre descriptivo",
    "region": "Región",
    "url": "https://...",
    "css_selector": "div.selector",  # selector CSS del contenido relevante
}
```

Si el selector no funciona (la web no tiene ese elemento), el script hace fallback
y usa todo el contenido del `<body>`.
