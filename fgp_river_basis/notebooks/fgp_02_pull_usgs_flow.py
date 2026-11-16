"""FGP side project, step 02: pull USGS daily mean flow, Mississippi River at Memphis.

Site 07032000, parameter 00060 = discharge (cubic feet per second), statistic 00003 = daily mean.
USGS has no daily river stage (feet) at this site, so flow is used instead (user decision 2026-11-11).

Output: fgp_river_basis/data/raw/usgs_07032000_flow_2021-08_2022-11.rdb, saved exactly as USGS sends it.
Never overwrites an existing raw file.
"""
import os

import requests

OUT = "fgp_river_basis/data/raw/usgs_07032000_flow_2021-08_2022-11.rdb"
URL = "https://waterservices.usgs.gov/nwis/dv/"
PARAMS = {"sites": "07032000", "parameterCd": "00060", "statCd": "00003",
          "startDT": "2021-08-01", "endDT": "2022-11-30", "format": "rdb"}

if os.path.exists(OUT):
    print(f"{OUT}: already exists, NOT pulled again")
else:
    r = requests.get(URL, params=PARAMS, timeout=120)
    r.raise_for_status()
    with open(OUT, "w") as f:
        f.write(r.text)
    n = sum(1 for line in r.text.splitlines() if line.startswith("USGS\t"))
    print(f"{OUT}: {n} daily rows")
