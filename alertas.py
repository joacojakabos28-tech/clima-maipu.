"""Envía alertas del clima de Maipú, Mendoza por Gmail a la familia.
Variables: GMAIL_USER, GMAIL_APP_PASSWORD, FAMILIA (mails separados por coma).
MODE=alertas (default, solo avisa si hay algo nuevo) | MODE=resumen (mail diario)."""
import json, os, smtplib, ssl, urllib.request
from email.message import EmailMessage
from datetime import date

Q = "latitude=-32.9786&longitude=-68.7886&timezone=America/Argentina/Mendoza&wind_speed_unit=kmh"
URL = f"https://api.open-meteo.com/v1/forecast?{Q}&forecast_days=3&current=temperature_2m,apparent_temperature,weather_code&hourly=temperature_2m,relative_humidity_2m,weather_code,wind_gusts_10m&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,uv_index_max"
AQ = f"https://air-quality-api.open-meteo.com/v1/air-quality?{Q}&current=us_aqi,dust"
get = lambda u: json.load(urllib.request.urlopen(u, timeout=30))

def alertas(d, aq):
    h, D = d["hourly"], d["daily"]
    i0 = max(0, next((i for i, t in enumerate(h["time"]) if t >= d["current"]["time"]), 0))
    s = lambda k: h[k][i0:i0 + 24]
    A = []
    zonda = any(g >= 45 and r <= 30 and t >= 22 for g, r, t in zip(s("wind_gusts_10m"), s("relative_humidity_2m"), s("temperature_2m")))
    gust = max(s("wind_gusts_10m"))
    if zonda: A.append(("zonda", "Posible viento Zonda", "Ráfagas fuertes, aire seco y cálido. Cuidado con polvo, incendios y objetos sueltos."))
    elif gust >= 60: A.append(("viento", "Viento fuerte", f"Ráfagas de hasta {gust:.0f} km/h."))
    codes = s("weather_code")
    if any(c >= 96 for c in codes): A.append(("granizo", "Tormenta con granizo", "Protejan el auto y las plantas."))
    elif any(c >= 95 for c in codes): A.append(("tormenta", "Tormenta eléctrica", "Evitar espacios abiertos."))
    if max(D["temperature_2m_max"][:2]) >= 36: A.append(("calor", "Calor extremo", f"Máxima de {max(D['temperature_2m_max'][:2]):.0f}°. Hidratarse y evitar el sol de 11 a 17."))
    if min(D["temperature_2m_min"][:2]) <= 0: A.append(("helada", "Helada", f"Mínima de {min(D['temperature_2m_min'][:2]):.0f}°. Proteger plantas y cañerías."))
    if max(D["precipitation_sum"][:2]) >= 20: A.append(("lluvia", "Lluvia abundante", "Más de 20 mm previstos."))
    if D["uv_index_max"][0] >= 8: A.append(("uv", "Radiación UV muy alta", "Usar protector solar y gorra."))
    if aq and (aq.get("us_aqi", 0) >= 100 or aq.get("dust", 0) >= 100): A.append(("aire", "Aire con polvo o contaminación", "Personas con asma o alergias, mejor adentro."))
    return A

def enviar(asunto, cuerpo):
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = os.environ["GMAIL_USER"], os.environ["FAMILIA"], asunto
    m.set_content(cuerpo)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"])
        s.send_message(m)

d = get(URL)
try: aq = get(AQ)["current"]
except Exception: aq = None
A = alertas(d, aq)
c, D = d["current"], d["daily"]
resumen = f"Ahora en Maipú: {c['temperature_2m']:.0f}° (sensación {c['apparent_temperature']:.0f}°). Hoy entre {D['temperature_2m_min'][0]:.0f}° y {D['temperature_2m_max'][0]:.0f}°."
lista = "\n".join(f"• {t}: {x}" for _, t, x in A) or "Sin alertas por ahora."

if os.environ.get("MODE") == "resumen":
    enviar("Clima de hoy en Maipú", f"{resumen}\n\n{lista}")
else:
    estado = json.load(open("estado.json")) if os.path.exists("estado.json") else {}
    hoy = str(date.today())
    nuevas = [a for a in A if estado.get(a[0]) != hoy]
    if nuevas:
        enviar("⚠️ Alerta de clima en Maipú: " + ", ".join(a[1] for a in nuevas),
               resumen + "\n\n" + "\n".join(f"• {t}: {x}" for _, t, x in nuevas))
        estado.update({a[0]: hoy for a in nuevas})
    json.dump(estado, open("estado.json", "w"))
