import os
import time
import smtplib
from email.message import EmailMessage
from urllib.parse import urljoin

import requests
from dotenv import load_dotenv

load_dotenv("scripts/.env_job")

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
EMAIL_TO = os.getenv("EMAIL_TO", "")

# nastavenie date range (taktiez aj v env_job)
DAYS = int(os.getenv("DAYS", "2"))
CLOUD = float(os.getenv("CLOUD", "100"))
TIMEOUT = 120


def send_email(subject: str, body: str):
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS and EMAIL_TO):
        raise RuntimeError("Missing SMTP_* or EMAIL_TO in .env_job")

    msg = EmailMessage()
    msg["From"] = SMTP_USER
    msg["To"] = EMAIL_TO
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
            s.ehlo()
            s.starttls()
            s.ehlo()
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
    except smtplib.SMTPAuthenticationError as e:
        raise RuntimeError(
            "SMTP auth failed. If using Gmail, you likely need an App Password (with 2FA enabled)."
        ) from e


def get_with_retry(url: str, params: dict, timeout: int, tries: int = 4) -> requests.Response:
    last_exc = None
    last_resp = None

    for i in range(tries):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            last_resp = r
            if r.status_code in (502, 503, 504) and i < tries - 1:
                time.sleep(1.5 * (i + 1))
                continue
            return r
        except Exception as e:
            last_exc = e
            if i < tries - 1:
                time.sleep(1.5 * (i + 1))
                continue
            raise

    if last_exc:
        raise last_exc
    return last_resp  # type: ignore[return-value]


def main():
    # 1) load AOIs
    resp = requests.get(f"{BASE_URL}/aois", timeout=TIMEOUT)
    if resp.status_code != 200:
        raise RuntimeError(f"/aois failed: {resp.status_code}\n{resp.text[:500]}")
    aois = resp.json()

    hits = []
    errs = []

    for a in aois:
        aoi_id = a["id"]
        name = a.get("name", aoi_id)

        # (A) latest-scene
        scene_url = f"{BASE_URL}/aois/{aoi_id}/latest-scene"
        try:
            r = get_with_retry(scene_url, {"days": DAYS, "cloud": CLOUD}, TIMEOUT)
        except Exception as e:
            errs.append((name, aoi_id, "latest-scene", "EXC", str(e)))
            continue

        if r.status_code != 200:
            errs.append((name, aoi_id, "latest-scene", r.status_code, r.text[:300]))
            continue

        data = r.json()
        if not data.get("datetime"):
            # no scene
            continue

        dt = data.get("datetime")
        cloud = data.get("cloud_cover")
        scene_id = data.get("scene_id")

        # (B) latest-fc (generate & save PNG and get URL)
        fc_url = f"{BASE_URL}/aois/{aoi_id}/latest-fc"
        img_url_full = None
        try:
            r2 = get_with_retry(fc_url, {"days": DAYS, "cloud": CLOUD}, TIMEOUT)
            if r2.status_code == 200:
                d2 = r2.json()
                if d2.get("url"):
                    # make absolute URL for email
                    img_url_full = urljoin(BASE_URL + "/", d2["url"].lstrip("/"))
            else:
                errs.append((name, aoi_id, "latest-fc", r2.status_code, r2.text[:300]))
        except Exception as e:
            errs.append((name, aoi_id, "latest-fc", "EXC", str(e)))

        hits.append((name, aoi_id, dt, cloud, scene_id, img_url_full))

    # 2) compose email
    lines = []
    lines.append(f"Volcano monitoring Sentinel-2 false color report (last {DAYS} days, cloud cover <= {CLOUD}%)\n")
    lines.append(f"Available satellite imagery: {len(hits)} of {len(aois)}\n")
    lines.append(f"Localhost Url: {BASE_URL}\n\n")

    if hits:
        lines.append("Sentinel-2 latest acquisitions:\n")
        hits_sorted = sorted(hits, key=lambda x: x[2] or "", reverse=True)
        for name, aoi_id, dt, cloud, scene_id, img_url_full in hits_sorted:
            lines.append(f"- {name} ({aoi_id})\n")
            lines.append(f"  datetime: {dt}\n")
            lines.append(f"  cloud percentage: {cloud}\n")
            lines.append(f"  scene_id: {scene_id}\n")
            if img_url_full:
                lines.append(f"  false_color: {img_url_full}\n")
            lines.append("\n")
    else:
        lines.append("No scene has been founded within the date range.\n\n")

    if errs:
        lines.append("---\nChyby (info):\n")
        for name, aoi_id, step, code, msg in errs:
            lines.append(f"- {name} ({aoi_id}) | {step} | {code} | {msg}\n")

    subject = f"[Copernicus Browser] volcano monitoring Sentinel-2 false color (urban): {len(hits)} images"
    send_email(subject, "".join(lines))


if __name__ == "__main__":
    main()
