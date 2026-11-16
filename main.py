import os
import json
import requests

from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

URL = "https://infovisa.ibz.be/ResultNl.aspx"

PARAMS = {
    "place": os.environ["PLACE"],
    "visumnr": os.environ["VISUMNR"],
}


def fetch_status():
    response = requests.get(URL, params=PARAMS, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    fields = {}

    for row in soup.select("table tr"):
        cells = row.find_all("td")

        if len(cells) == 2:
            key = cells[0].get_text(strip=True).rstrip(":")
            value = cells[1].get_text(" ", strip=True)
            fields[key] = value

    result = {
        "application_date": fields.get("Datum visumaanvraag"),
        "registration_date": fields.get(
            "Datum registratie visumaanvraag door Dienst Vreemdelingenzaken"
        ),
        "status": fields.get("Beslissing/Status Dossier"),
        "decision_date": fields.get("Datum beslissing/Status Dossier") or None,
    }

    if not result["status"]:
        raise ValueError("Visa status not found in response")

    return result


def notify(result):
    status = result["status"]
    is_pending = status.strip().casefold() == "in behandeling"

    response = requests.post(
        f"{os.environ['NTFY_URL'].rstrip('/')}/{os.environ['NTFY_TOPIC']}",
        data=json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {os.environ['NTFY_TOKEN']}",
            "Title": "Visa application status",
            "Priority": "default" if is_pending else "urgent",
            "Tags": "hourglass" if is_pending else "tada",
            "Markdown": "no",
        },
        timeout=15,
    )

    response.raise_for_status()


def main():
    result = fetch_status()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    notify(result)

if __name__ == "__main__":
    main()

