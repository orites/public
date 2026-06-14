import json
import re
from datetime import datetime, timedelta, timezone
import requests
from bs4 import BeautifulSoup


def scrape_pinnacle_road():
    url = "https://hccapps.hobartcity.com.au/PinnacleRoad/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching page: {e}")
        return None, None

    soup = BeautifulSoup(response.text, "html.parser")

    # Extract the main status message (e.g., 'Open to summit', 'Closed at The Springs')
    report_header = soup.find("h1", text=re.compile(r"Current Road Report", re.I))
    status_text = ""
    if report_header:
        status_text = report_header.get_text()
    else:
        # Fallback text lookup
        status_text = soup.get_text()

    # Extract additional comments if they contain details
    comment_div = soup.find(text=re.compile(r"Comment:", re.I))
    comment_text = ""
    if comment_div:
        comment_text = comment_div.parent.get_text()

    full_context = f"{status_text} {comment_text}".lower()
    return full_context, soup.get_text()


def generate_waze_json():
    full_context, raw_html_text = scrape_pinnacle_road()

    # Default structure matching Waze CIFS specification schema
    waze_data = {"incidents": []}

    if not full_context:
        return waze_data

    # Generate standard ISO 8601 timestamps
    now = datetime.now(timezone.utc)
    starttime = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    # Waze requires an end time; set a rolling 3-hour window for active reports
    endtime = (now + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Precise coordinates representing Pinnacle Road segments
    # Format required by Waze: "lon1 lat1 lon2 lat2 lon3 lat3..."
    geometries = {
        "bracken_lane": "147.24131 -42.90994 147.24355 -42.91030 147.23550 -42.90321 147.21382 -42.89613",
        "the_springs": "147.21382 -42.89613 147.22150 -42.89501 147.20721 -42.89534",
    }

    is_closed = False
    chosen_polyline = ""
    description = ""
    location_id = ""

    # Check for specific closure parameters in the text strings
    if "bracken lane" in full_context or "closed at bracken lane" in full_context:
        is_closed = True
        chosen_polyline = geometries["bracken_lane"]
        description = "Pinnacle Road closed at Bracken Lane"
        location_id = "pinnacle_rd_closed_bracken"
    elif "the springs" in full_context or "closed at the springs" in full_context:
        is_closed = True
        chosen_polyline = geometries["the_springs"]
        description = "Pinnacle Road closed at The Springs"
        location_id = "pinnacle_rd_closed_springs"

    # Override if explicit 'open to summit' is declared without a closing comment
    if "open to summit" in full_context and "pre-emptive closure" not in full_context:
        is_closed = False

    if is_closed:
        # Wrap incident details cleanly within Waze specified object arrays
        incident_item = {
            "incident": {
                "id": location_id,
                "type": "ROAD_CLOSED",
                "subtype": "ROAD_CLOSED_HAZARD",
                "polyline": chosen_polyline,
                "street": "Pinnacle Road",
                "starttime": starttime,
                "endtime": endtime,
                "description": description,
                "direction": "BOTH_DIRECTIONS",
            }
        }
        waze_data["incidents"].append(incident_item)

    return waze_data


if __name__ == "__main__":
    feed_output = generate_waze_json()
    with open("waze_closures.json", "w") as f:
        json.dump(feed_output, f, indent=2)
    print("Waze JSON closure feed generated successfully.")
