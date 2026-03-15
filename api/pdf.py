from http.server import BaseHTTPRequestHandler
import json
import io
import base64

PDF_CSS = """
@import url('https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,600;1,400&family=Cinzel:wght@400;600&display=swap');

* { box-sizing: border-box; margin: 0; padding: 0; }

@page {
    size: A4;
    margin: 2.2cm 2.5cm 2.5cm 2.5cm;
    @bottom-center {
        content: "AstroPro  ·  Profesjonalna Analiza Astrologiczna  ·  " counter(page) " / " counter(pages);
        font-family: 'EB Garamond', Georgia, serif;
        font-size: 8pt;
        color: #94a3b8;
    }
}

body {
    font-family: 'EB Garamond', Georgia, serif;
    font-size: 11pt;
    line-height: 1.75;
    color: #1e293b;
}

/* ── Cover ── */
.cover {
    text-align: center;
    padding: 60pt 0 50pt;
    border-bottom: 2pt solid #c9a84c;
    margin-bottom: 0;
    page-break-after: always;
}
.cover-glyph  { font-size: 18pt; color: #c9a84c; margin-bottom: 10pt; }
.cover-title  { font-family: 'Cinzel', Georgia, serif; font-size: 22pt; color: #7a5c10;
                letter-spacing: 3pt; font-weight: 600; margin-bottom: 10pt; }
.cover-sub    { font-size: 11pt; color: #64748b; font-style: italic; margin: 4pt 0; }
.cover-yr     { font-size: 10pt; color: #94a3b8; margin-top: 14pt; }

/* ── Data table page ── */
.data-page    { page-break-after: always; }

/* ── Headings ── */
h1 {
    font-family: 'Cinzel', Georgia, serif;
    font-size: 15pt;
    color: #c9a84c;
    text-align: center;
    letter-spacing: 2pt;
    margin: 20pt 0 8pt;
    font-weight: 400;
}
h2 {
    font-family: 'Cinzel', Georgia, serif;
    font-size: 13pt;
    color: #1e3a8a;
    font-weight: 600;
    margin: 28pt 0 8pt;
    padding-bottom: 5pt;
    border-bottom: 1.5pt solid #c9a84c;
    page-break-before: always;
    page-break-after: avoid;
}
h2:first-of-type { page-break-before: avoid; }
h3 {
    font-family: 'Cinzel', Georgia, serif;
    font-size: 10.5pt;
    color: #7a5c10;
    font-weight: 600;
    margin: 16pt 0 5pt;
    text-transform: uppercase;
    letter-spacing: 0.5pt;
    page-break-after: avoid;
}

/* ── Body text ── */
p  { margin-bottom: 8pt; orphans: 3; widows: 3; }
ul, ol { padding-left: 18pt; margin: 6pt 0 8pt; }
li { margin-bottom: 4pt; }
strong { color: #1e3a8a; font-weight: 600; }
em { font-style: italic; }

/* ── Tables ── */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 10pt 0 12pt;
    font-size: 10pt;
    page-break-inside: avoid;
}
thead { display: table-header-group; }
th {
    background-color: #1e3a8a;
    color: #c9a84c;
    padding: 6pt 8pt;
    text-align: left;
    font-family: 'Cinzel', Georgia, serif;
    font-size: 9pt;
    letter-spacing: 0.5pt;
    font-weight: 600;
}
td {
    padding: 5.5pt 8pt;
    border-bottom: 0.5pt solid #e2e8f0;
    vertical-align: top;
}
tr:nth-child(even) td { background-color: #f8fafc; }
td:first-child { color: #1e3a8a; font-weight: 600; }

/* ── Footer note ── */
.report-footer {
    text-align: center;
    margin-top: 30pt;
    padding-top: 10pt;
    border-top: 0.5pt solid #e2e8f0;
    color: #94a3b8;
    font-size: 9pt;
    font-style: italic;
}
"""

def build_html(data):
    name       = data.get('name', '')
    date       = data.get('date', '')
    time_      = data.get('time', '')
    birth      = data.get('birth', '')
    reloc      = data.get('reloc', '')
    year       = data.get('year', '')
    month_year = data.get('month_year', '')
    planets    = data.get('planets_html', '')
    aspects    = data.get('aspects_html', '')
    report     = data.get('report_html', '')

    reloc_line = f'<div class="cover-sub">Relokacja: {reloc}</div>' if reloc else ''

    return f"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<title>AstroPro — {name}</title>
</head>
<body>

<div class="cover">
  <div class="cover-glyph">✦ ASTRO PRO ✦</div>
  <div class="cover-title">{name.upper()}</div>
  <div class="cover-sub">{date} &middot; {time_} &middot; {birth}</div>
  {reloc_line}
  <div class="cover-yr">Pe&lstrok;na Analiza Psychologiczno-Ewolucyjna {year}</div>
</div>

<div class="data-page">
  <h1>Dane Horoskopu</h1>
  <h2>Pozycje Planet</h2>
  {planets}
  <h2>Aspekty Planetarne</h2>
  {aspects}
</div>

<h1>Pe&lstrok;na Analiza Astrologiczna</h1>

{report}

<div class="report-footer">
  ✦ AstroPro &mdash; Profesjonalna Analiza Astrologiczna ✦<br>
  Wygenerowano: {month_year} &middot; Swiss Ephemeris + Placidus + Silnik Aspekt&oacute;w
</div>

</body>
</html>"""


class handler(BaseHTTPRequestHandler):

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200); self._cors(); self.end_headers()

    def do_POST(self):
        try:
            from weasyprint import HTML, CSS

            length = int(self.headers.get('Content-Length', 0))
            data   = json.loads(self.rfile.read(length))

            html_str = build_html(data)
            css_obj  = CSS(string=PDF_CSS)

            buf = io.BytesIO()
            HTML(string=html_str, base_url=None).write_pdf(buf, stylesheets=[css_obj])
            pdf_bytes = buf.getvalue()

            self.send_response(200)
            self.send_header('Content-Type', 'application/pdf')
            self.send_header('Content-Disposition',
                f'attachment; filename="AstroPro_{data.get("name","report").replace(" ","_")}.pdf"')
            self.send_header('Content-Length', str(len(pdf_bytes)))
            self._cors()
            self.end_headers()
            self.wfile.write(pdf_bytes)

        except Exception as e:
            import traceback
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self._cors(); self.end_headers()
            self.wfile.write(json.dumps({
                'error': str(e),
                'trace': traceback.format_exc()
            }).encode())

    def log_message(self, fmt, *args): pass
