import re
from datetime import datetime

MESES = {
"janeiro":"01",
"fevereiro":"02",
"março":"03",
"abril":"04",
"maio":"05",
"junho":"06",
"julho":"07",
"agosto":"08",
"setembro":"09",
"outubro":"10",
"novembro":"11",
"dezembro":"12"
}

DATE_REGEX = re.compile(
r'(\d{1,2})\s+de\s+(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+de\s+(\d{4})',
re.IGNORECASE
)

def extract_dates(text):

    dates = []

    for match in DATE_REGEX.finditer(text):

        day = match.group(1).zfill(2)
        month = MESES[match.group(2).lower()]
        year = match.group(3)

        iso = f"{year}-{month}-{day}"

        dates.append({
            "raw": match.group(0),
            "iso": iso
        })

    return dates