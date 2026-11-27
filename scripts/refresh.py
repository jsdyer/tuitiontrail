"""Build one verified edition from two Statistics Canada full-table CSV downloads."""
import argparse
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from urllib.request import Request, urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
FEES = "37100003"
INCOME = "37100287"
TARGET = ROOT / "web/data/edition.json"
PERIODS = {
    "Median employment income two years after graduation": 2,
    "Median employment income five years after graduation": 5,
    "Median employment income ten years after graduation": 10,
}


def download(product, target):
    url = f"https://www150.statcan.gc.ca/n1/tbl/csv/{product}-eng.zip"
    req = Request(url, headers={"User-Agent": "TuitionTrail/1 (+https://coolcode.ca/tuitiontrail/)"})
    with urlopen(req, timeout=90) as response, target.open("wb") as out:
        count = 0
        while chunk := response.read(1024 * 1024):
            count += len(chunk)
            if count > 150_000_000:
                raise ValueError("Official archive exceeds download limit")
            out.write(chunk)


def source_meta(archive, product):
    name = f"{product}_MetaData.csv"
    with archive.open(name) as raw:
        rows = list(csv.reader(io.TextIOWrapper(raw, encoding="utf-8-sig")))
    if rows[1][1] != product:
        raise ValueError("Unexpected source table ID")
    return rows


def csv_rows(archive, product):
    member = archive.getinfo(product + ".csv")
    if member.file_size > 2_500_000_000:
        raise ValueError("Official table exceeds processing limit")
    with archive.open(member) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig", newline=""))


def cell(row):
    if row["SCALAR_FACTOR"] != "units":
        raise ValueError("Unexpected units")
    flag = row["STATUS"].strip() or row["SYMBOL"].strip()
    if not row["VALUE"]:
        return flag or ".."
    amount = int(row["VALUE"])
    return [amount, flag] if flag else amount


def insert(mapping, key, value):
    if key in mapping:
        raise ValueError(f"Duplicate eligible observation at {key}")
    mapping[key] = value


def has_number(c):
    return type(c) is int or isinstance(c, list)


def fees(path):
    data = {}
    with ZipFile(path) as archive:
        meta = source_meta(archive, FEES)
        notes = [r[1] for r in meta if len(r) > 1 and r[0].isdigit() and "are preliminary" in r[1]]
        preliminary = sorted(set(re.findall(r"\d{4}/\d{4}", " ".join(notes))))
        for r in csv_rows(archive, FEES):
            if r["UOM"] != "Current dollars" or not re.fullmatch(r"\d{4}/\d{4}", r["REF_DATE"]):
                raise ValueError("Unexpected tuition reference or unit")
            by_year = data.setdefault(r["Field of study"], {}).setdefault(r["GEO"], {})
            insert(by_year, r["REF_DATE"], cell(r))
    return data, preliminary


def earnings(path):
    data, units = {}, set()
    with ZipFile(path) as archive:
        meta = source_meta(archive, INCOME)
        # Third coordinate is field of study. Member labels can repeat at two
        # levels, so use the publisher's hierarchy to select the broad groups.
        groups = {r[3] for r in meta if len(r) >= 7 and r[0] == "3" and r[4] == "1"}
        if not groups:
            raise ValueError("No broad income fields in source metadata")
        for r in csv_rows(archive, INCOME):
            if r["Educational qualification"] != "Undergraduate degree" or r["Status of student in Canada"] != "Canadian students":
                continue
            period = PERIODS.get(r["Graduate statistics"])
            if (not period or r["Gender"] != "Total, gender" or r["Age group"] != "15 to 64 years"
                    or r["Characteristics after graduation"] != "Graduates reporting employment income"
                    or r["COORDINATE"].split(".")[2] not in groups):
                continue
            if not re.fullmatch(r"\d{4} constant dollars", r["UOM"]) or not re.fullmatch(r"\d{4}", r["REF_DATE"]):
                raise ValueError("Unexpected income reference or unit")
            units.add(r["UOM"])
            field = re.sub(r" \[[^]]+\]$", "", r["Field of study"])
            series = data.setdefault(field, {}).setdefault(r["GEO"], {}).setdefault(r["REF_DATE"], {})
            insert(series, str(period), cell(r))
    if len(units) != 1:
        raise ValueError("Expected a single constant dollar basis")
    return data, units.pop()


def validate(edition):
    tuition, outcomes = edition["tuition"], edition["earnings"]
    if not all(any(has_number(v) for v in tuition.get("Nursing", {}).get(g, {}).values())
               for g in ["Nova Scotia", "British Columbia"]):
        raise ValueError("Missing default nursing comparison")
    health = outcomes.get("Health and related fields", {}).get("Canada", {})
    if not any(all(has_number(series.get(str(n))) for n in [2, 5, 10]) for series in health.values()):
        raise ValueError("Missing broad health cohort comparison")
    for name, geo in tuition.items():
        if not name or not any(has_number(v) for years in geo.values() for v in years.values()):
            raise ValueError("Empty published tuition field")
    for geo in outcomes.values():
        if any(set(values) != {"2", "5", "10"} for years in geo.values() for values in years.values()):
            raise ValueError("Incomplete graduate follow-up measures")
        if not any(has_number(v) for years in geo.values() for p in years.values() for v in p.values()):
            raise ValueError("Empty published income field")
    return edition


def collect(files, when):
    tuition, preliminary = fees(files / (FEES + ".zip"))
    income, units = earnings(files / (INCOME + ".zip"))
    return validate({"checked_at": when, "tuition": tuition, "preliminary": preliminary,
                     "earnings": income, "income_units": units})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, help="Use the two official table ZIPs already downloaded")
    args = parser.parse_args()
    with TemporaryDirectory() as temp:
        directory = args.source_dir or Path(temp)
        if not args.source_dir:
            for product in [FEES, INCOME]:
                download(product, directory / (product + ".zip"))
        checked = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        edition = collect(directory, checked)
        # Truncated upstream releases must not silently roll back our coverage.
        if TARGET.exists():
            previous = json.loads(TARGET.read_text())
            for key in ("tuition", "earnings"):
                for field, geos in previous[key].items():
                    for geo, years in geos.items():
                        if not set(years) <= set(edition[key].get(field, {}).get(geo, {})):
                            raise ValueError(f"Source lost previous years for {field}, {geo}; review the revision")
        candidate = TARGET.with_suffix(".tmp")
        candidate.write_text(json.dumps(edition, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n")
        candidate.replace(TARGET)
    print(f"Verified {len(edition['tuition'])} tuition fields and {len(edition['earnings'])} graduate fields.")


if __name__ == "__main__":
    main()
