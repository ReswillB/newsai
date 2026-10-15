"""Lee noticias por RSS, las resume con Gemini y te las manda por correo."""
import os
import smtplib
import time
from email.mime.text import MIMEText

import feedparser
import requests

# Si un periódico cambia su dirección RSS, solo hay que cambiarla aquí.
FEEDS = {
    "El País": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada",
    "El Mundo": "https://e00-elmundo.uecdn.es/elmundo/rss/portada.xml",
    "RTVE": "https://www.rtve.es/api/noticias.rss",
}
NOTICIAS_POR_PERIODICO = 6

# Si Google retira este modelo, solo hay que cambiar este nombre.
MODELO = os.environ.get("MODELO", "gemini-2.5-flash-lite")

INSTRUCCIONES = (
    "Eres un editor de noticias. Te paso titulares y entradillas de varios periódicos españoles. "
    "Escribe en español un resumen agrupado por tema (política, economía, internacional, sociedad, otros). "
    "Máximo 3 frases por tema. No inventes ningún dato que no esté en el texto. "
    "Indica entre paréntesis el periódico de cada noticia. Si una noticia es ambigua, dilo."
)


def leer_noticias():
    texto, avisos = [], []
    for nombre, url in FEEDS.items():
        feed = feedparser.parse(url)
        if not feed.entries:
            avisos.append(f"No se pudo leer {nombre} ({url})")
            continue
        for e in feed.entries[:NOTICIAS_POR_PERIODICO]:
            texto.append(f"[{nombre}] {e.get('title', '')}. {e.get('summary', '')}")
    return "\n".join(texto), avisos


def resumir(noticias):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:generateContent"
    cabeceras = {"x-goog-api-key": os.environ["GEMINI_API_KEY"]}
    cuerpo = {"contents": [{"parts": [{"text": INSTRUCCIONES + "\n\n" + noticias}]}]}
    for intento in range(4):
        r = requests.post(url, headers=cabeceras, json=cuerpo, timeout=60)
        if r.status_code == 429 or r.status_code >= 500:
            espera = 10 * (intento + 1)
            print(f"La API respondió {r.status_code}, reintento en {espera}s")
            time.sleep(espera)
            continue
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    raise RuntimeError("La API no respondió tras varios intentos")


def enviar_correo(texto):
    usuario = os.environ["GMAIL_USER"]
    msg = MIMEText(texto, "plain", "utf-8")
    msg["Subject"] = "Tu resumen de noticias de hoy"
    msg["From"] = usuario
    msg["To"] = usuario
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(usuario, os.environ["GMAIL_APP_PASSWORD"])
        s.send_message(msg)


if __name__ == "__main__":
    noticias, avisos = leer_noticias()
    print(f"Leídas {len(noticias.splitlines())} noticias. Avisos: {avisos}")
    if not noticias:
        raise SystemExit("No se pudo leer ningún periódico")
    resumen = resumir(noticias)
    if avisos:
        resumen += "\n\n---\nAvisos:\n" + "\n".join(avisos)
    enviar_correo(resumen)
    print("Correo enviado")
