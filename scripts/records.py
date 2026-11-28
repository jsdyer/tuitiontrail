"""Render fee histories and graduate cohort records from the saved source edition."""
from html import escape
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

from refresh import has_number

FEE_URL = "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3710000301"
INCOME_URL = "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3710028701"
LICENCE = "https://www.statcan.gc.ca/en/reference/licence"


def slug(name):
    normalized = unicodedata.normalize("NFKD", name.casefold()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")


def link(href, text):
    return '<a href="'+escape(href,quote=True)+'">'+escape(text)+'</a>'


def number(value):
    return value[0] if isinstance(value, list) else value if type(value) is int else None


def show(value):
    n = number(value)
    if n is None:
        return {"x":"Suppressed", "...":"Not applicable", "F":"Too unreliable to publish"}.get(value,"Unavailable")
    return ("-$" if n < 0 else "$") + f"{abs(n):,}" + (f" ({escape(value[1])})" if isinstance(value,list) else "")


def table(caption, labels, rows):
    head="".join('<th scope="col">'+escape(label)+'</th>' for label in labels)
    out=[]
    for key, values in rows:
        out.append('<tr><th scope="row">'+escape(key)+'</th>'+''.join('<td>'+v+'</td>' for v in values)+'</tr>')
    return '<table><caption>'+escape(caption)+'</caption><thead><tr>'+head+'</tr></thead><tbody>'+''.join(out)+'</tbody></table>'


def listing(items):
    return '<ul class="records">'+''.join('<li>'+link(path,text)+'</li>' for path,text in items)+'</ul>'


def published(by_year):
    return any(has_number(v) for v in by_year.values())


def profile(name, region):
    return "records/"+slug(name)+"/"+slug(region)+"/"


def first_view(edition, settings):
    field = settings["field"]
    geos = edition["tuition"][field]
    left,right = settings["left"],settings["right"]
    years = sorted(set(geos[left])|set(geos[right]),reverse=True)
    year = years[0]
    places = (left,right)
    cards = "".join('<div class="card"><span>'+escape(g)+'</span><strong>'+show(geos[g].get(year))+'</strong></div>' for g in places)
    context = field+" · "+year+(" · preliminary" if year in edition["preliminary"] else "")+" · annual CAD"
    first,second = [number(geos[g].get(year)) for g in places]
    difference = "A comparison requires published figures for both places."
    if first is not None and second is not None:
        high = left if first>second else right
        difference = (high+" is "+show(abs(first-second))+" higher for the year.") if first!=second else "Both selections have the same published average."
    links = " · ".join(link("./"+profile(field,g),g+" tuition history") for g in places if published(geos[g]))
    fee_result='<p class="context">'+escape(context)+'</p><div class="cards">'+cards+'</div><p>'+escape(difference)+'</p><p class="result-links">'+links+'</p>'
    fee_history=table(field+" annual tuition in current CAD · (p) preliminary",["Academic year",left,right],[(y+(" (p)" if y in edition["preliminary"] else ""),[show(geos[g].get(y)) for g in places]) for y in years])
    group,place=settings["incomeField"],settings["incomePlace"]
    cohorts=edition["earnings"][group][place]
    cohort=max(cohorts)
    income=table(group+" · "+place+" · "+cohort+" cohort · "+edition["income_units"],["After graduation","Median income"],[(f"{n} years ({int(cohort)+n})",[show(cohorts[cohort].get(str(n)))]) for n in (2,5,10)])
    income+=link("./records/graduate-income/"+slug(group)+"/","Read the full "+group.lower()+" graduate record")
    return {"FEE_RESULT":fee_result,"FEE_HISTORY":fee_history,"INCOME_RESULT":income,"CHECKED":"Sources checked "+escape(edition["checked_at"][:10])}


def write_records(stage, tool, edition):
    paths = []
    base = "https://coolcode.ca"+tool["url"]
    checked=edition["checked_at"][:10]
    canonical_enabled=tool["source"]=="https://github.com/jsdyer/"+tool["id"] and tool["id"]!="coolcode-tool-template"

    def save(path, title, desc, body):
        if path in paths:
            raise ValueError("Duplicate result path: "+path)
        paths.append(path)
        prefix="../"*path.count("/")
        head='<link rel="canonical" href="'+base+path+'">' if canonical_enabled else ''
        stats='<script defer src="/assets/tool-metrics.js" referrerpolicy="no-referrer"></script>' if canonical_enabled else ''
        doc=('<!doctype html><html lang="en-CA"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
             '<title>'+escape(title)+' · Tuition Trail</title><meta name="description" content="'+escape(desc,quote=True)+'">'+head+
             '<meta property="og:title" content="'+escape(title,quote=True)+'"><meta property="og:description" content="'+escape(desc,quote=True)+'">'
             '<link rel="stylesheet" href="'+prefix+'style.css">'+stats+'</head><body data-tool-id="'+escape(tool["id"],quote=True)+'">'
             '<a class="skip" href="#main">Skip to record</a><header><nav class="wrap">'+link(prefix,"Tuition Trail")+' '+link(prefix+"records/","All records")+' '+link("https://coolcode.ca/","CoolCode.ca")+'</nav></header>'
             '<main class="wrap" id="main"><div class="hero"><h1>'+escape(title)+'</h1><p>'+escape(desc)+'</p></div>'+body+
             '<footer><p>Statistics Canada · Source files checked '+checked+' · '+link(LICENCE,"Open Licence")+' · '+link("https://coolcode.ca/wagewindow/","Wage Window")+'</p></footer></main></body></html>')
        target=stage/path/"index.html";target.parent.mkdir(parents=True,exist_ok=True);target.write_text(doc)

    tuition=edition["tuition"]
    prelim=edition["preliminary"]
    tuition_notes=('<p class="note">Published averages are weighted by enrolment. Each year uses current Canadian dollars. '
                   'The mix of enrolled programs and students can change over time. Financial aid and tax rebates are excluded. '
                   +link(FEE_URL,"Statistics Canada table 37-10-0003-01")+'</p>')
    regions = {}
    field_links=[]
    for field,places in tuition.items():
        available={g:ys for g,ys in places.items() if published(ys)}
        fp="records/"+slug(field)+"/";field_links.append(("./"+slug(field)+"/",field))
        field_rows=[]
        for place,years in available.items():
            last=max(y for y,n in years.items() if has_number(n))
            current=show(years[last])
            pr=" (preliminary)" if last in prelim else ""
            p=profile(field,place)
            regions.setdefault(place,[]).append((field,p,current,last))
            title=field+" undergraduate tuition in "+place if place!="Canada" else field+" undergraduate tuition across Canada"
            desc=f"The published average for Canadian undergraduates was {current} in {last}{pr}. Explore the available academic years and compare another place."
            compare = urlencode({"field":field,"left":place,"right":"Canada" if place!="Canada" else "Nova Scotia","year":last})
            body=('<section class="panel"><h2>Annual tuition history</h2><p>'+link("../../../?"+compare,"Open this comparison")+' · '+link("../","Compare places for "+field.lower())+'</p>'
                  +table("Weighted tuition fees in current CAD",["Academic year","Average tuition"],[(y+(" (preliminary)" if y in prelim else ""),[show(years[y])]) for y in sorted(years,reverse=True)])
                  +tuition_notes+'<p>'+link("../../places/"+slug(place)+"/","Other fields in "+place)+'</p></section>')
            if field == "Nursing" and place in ("Nova Scotia", "British Columbia"):
                field_note = "https://coolcode.ca/field-notes/nursing-tuition-and-rent-in-nova-scotia-and-bc/"
                body += '<p>' + link(field_note, "Compare nursing tuition and rent for an eight-month student budget") + '</p>'
            save(p,title,desc,body)
            field_rows.append((place,[current,escape(last+pr),link("./"+slug(place)+"/","History")]))
        title=field+" undergraduate tuition by place"
        desc=f"Compare published Canadian undergraduate tuition for {field.lower()} in {len(available)} geographic areas. Each row identifies the most recent year with an amount."
        save(fp,title,desc,'<section class="panel">'+table("Latest published average in current CAD",["Place","Tuition","Academic year","Series"],field_rows)+tuition_notes+'</section>')

    for place,records in regions.items():
        rows=[(field,[amount,escape(year+(" (p)" if year in prelim else "")),link("../../../"+path,"History")]) for field,path,amount,year in records]
        save("records/places/"+slug(place)+"/","Canadian undergraduate tuition in "+place,
             f"Browse the latest published tuition averages and complete histories for {len(rows)} study fields or totals in {place}.",
             '<section class="panel">'+table("Latest available average · current CAD · (p) preliminary",["Field","Tuition","Year","Series"],rows)+tuition_notes+'</section>')

    years = sorted({y for places in tuition.values() for series in places.values() for y in series}, reverse=True)
    year_links = []
    for year in years:
        year_slug = slug(year)
        year_links.append(("./years/" + year_slug + "/", year))
        by_field = []
        by_place = []
        for field, places in tuition.items():
            national = places.get("Canada", {})
            if has_number(national.get(year)):
                by_field.append((field, [show(national[year]), link("../../../" + profile(field, "Canada"), "History")]))
        aggregate = "Total, field of study"
        for place, series in tuition.get(aggregate, {}).items():
            if has_number(series.get(year)):
                by_place.append((place, [show(series[year]), link("../../../" + profile(aggregate, place), "History")]))
        desc = f"Compare Canada's undergraduate tuition averages for {year} by field of study, then see the all-field average in each place with a published amount."
        if year in prelim:
            desc += " These estimates are preliminary."
        body = ('<section class="panel"><h2>Fields across Canada</h2>'
                + table("Domestic undergraduate tuition in current CAD", ["Field", "Average", "Series"], by_field)
                + '</section><section class="panel"><h2>All fields by place</h2>'
                + table("Domestic undergraduate tuition in current CAD", ["Place", "Average", "Series"], by_place)
                + tuition_notes + '</section>')
        save("records/years/" + year_slug + "/", "Canadian undergraduate tuition in " + year, desc, body)

    source_body = ('<section class="panel"><h2>Tuition before financial aid</h2>'
                   '<p>Statistics Canada publishes annual tuition for Canadian undergraduate students. '
                   'The averages reflect each program’s share of enrolment. A place with a larger share of students in higher-fee programs can have a higher all-field average. '
                   'The published amount excludes financial assistance and tax rebates. Housing, books and other living costs need a separate budget.</p>'
                   '<p>Annual fees use current Canadian dollars. The number of dollars in two academic years can differ with both tuition and purchasing power. '
                   'Preliminary values may change. “Unavailable” identifies an unpublished cell in the source. '
                   'Provinces can charge different rates based on student residency. Compare published averages with the institution’s fee schedule for your circumstances.</p>'
                   '<p>' + link(FEE_URL, "Canadian undergraduate tuition fees by field of study, table 37-10-0003-01") + '</p></section>'
                   '<section class="panel"><h2>Employment income after graduation</h2>'
                   '<p>The median is the middle of the earnings distribution among the covered graduates, including zero earnings and net self-employment income. '
                   'Places identify where graduates studied. The measures are for Canadian undergraduate degree graduates aged 15–64 and use '
                   + escape(edition["income_units"]) + '. The follow-up covers the same cohort at two, five and ten years. '
                   'It excludes graduates who returned to full-time studies or lacked income information during the ten-year period. '
                   'A suppressed cell is withheld from publication.</p><p>Graduate fields are broader than some tuition fields. '
                   'For example, the health group covers multiple programs, including nursing. Statistics Canada classifies medicine, dentistry, veterinary medicine, optometry, pharmacy and law as professional degrees outside this graduate cohort. Tuition and earnings refer to different populations and times. '
                   'A direct estimate of payback for a current student would require individual fee, financing, living cost and earnings information.</p><p>'
                   + link(INCOME_URL, "Graduate employment income by field of study, table 37-10-0287-01") + '</p></section>'
                   '<section class="panel"><h2>Source checks and reuse</h2><p>The scheduled monthly check downloads both public tables. '
                   'The saved edition changes only after it passes validation. The latest check was ' + checked + '. The academic or graduation year identifies the period measured.</p>'
                   '<p>' + link("../../data/edition.json", "Download the saved data (JSON)") + ' · ' + link(LICENCE, "Statistics Canada Open Licence") + '</p></section>')
    save("records/sources/", "How to read tuition and graduate income",
         "Find the source tables, definitions, selection criteria and update schedule for Tuition Trail.", source_body)

    income_links=[]
    for group, places in edition["earnings"].items():
        path="records/graduate-income/"+slug(group)+"/"
        income_links.append(("./graduate-income/"+slug(group)+"/",group))
        title=group+" graduate employment income"
        desc=f"Explore the median employment income of earlier Canadian undergraduate degree cohorts in {group.lower()} at two, five and ten years after graduation."
        body='<section class="panel"><h2>Income after graduation</h2><p>'+link("../../../?"+urlencode({"incomeField":group})+"#graduate-income","Choose a place and cohort")+'</p>'
        body+='<p>Figures use '+escape(edition["income_units"])+'. Places identify where graduates studied. The group excludes graduates missing income information or returning to full-time studies during the ten-year follow-up. Figures include self-employment and reported zero earnings. '+link(INCOME_URL,"Statistics Canada table 37-10-0287-01")+'</p>'
        for place,years in places.items():
            if not any(published(p) for p in years.values()): continue
            body+=table(place+" · Canadian undergraduate degree graduates aged 15–64",["Graduation year","+2 years","+5 years","+10 years"],[(year,[show(years[year].get(str(n))) for n in (2,5,10)]) for year in sorted(years,reverse=True)])
        save(path,title,desc,body+'</section>')
    directory='<section class="panel"><h2>Tuition by field of study</h2>'+listing(field_links)+'</section><section class="panel"><h2>Tuition by place</h2>'+listing([("./places/"+slug(g)+"/",g) for g in sorted(regions)])+'</section><section class="panel"><h2>Graduate earnings by broad field</h2>'+listing(income_links)+'</section>'
    directory += '<section class="panel"><h2>Tuition by academic year</h2>' + listing(year_links) + '</section><p>' + link("./sources/", "Sources and interpretation") + '</p>'
    save("records/","Canadian tuition histories and graduate income cohorts","Browse tuition by place and field. In a separate set of records, follow earlier graduates’ earnings across ten years.",directory)
    site=ET.Element("urlset",xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for path in sorted(paths):
        ET.SubElement(ET.SubElement(site,"url"),"loc").text=base+path
    if canonical_enabled:
        (stage/"sitemap.xml").write_bytes(ET.tostring(site,encoding="utf-8",xml_declaration=True))
    vals=sum(has_number(n) for g in tuition.values() for ys in g.values() for n in ys.values())
    status={"checked_at":edition["checked_at"],"tuition_values":vals,"tuition_fields":len(tuition),"tuition_places":len(regions),"graduate_fields":len(income_links),"sitemap_urls":len(paths)}
    (stage/"data/status.json").write_text(json.dumps(status,indent=2)+"\n")
    return status
