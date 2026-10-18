from html import escape


def render_catalogue(equipment, categories, search, category, status):
    category_options = "".join(
        f'<option value="{escape(value)}"{" selected" if value == category else ""}>{escape(value)}</option>'
        for value in categories
    )
    status_options = "".join(
        f'<option value="{value}"{" selected" if value == status else ""}>{value}</option>'
        for value in ("available", "maintenance", "inactive")
    )
    cards = "".join(
        '<article class="card">'
        f'<div class="tags"><span>{escape(item.category)}</span>'
        f'<span class="status {escape(item.status)}">{escape(item.status)}</span></div>'
        f'<h2>{escape(item.name)}</h2><p>{escape(item.description)}</p>'
        f'<p class="location">Collection: {escape(item.location)}</p></article>'
        for item in equipment
    )
    if not equipment:
        cards = '<p class="empty">No equipment matches your search. Try changing or clearing the filters.</p>'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Equipment catalogue · Community Lending</title>
<link rel="icon" href="data:,">
<style>
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #f5f7f6; color: #18352d; font: 16px/1.6 system-ui, sans-serif; }}
header {{ background: #173e34; color: white; padding: 18px max(20px, calc((100vw - 1120px) / 2)); }}
main {{ max-width: 1160px; margin: auto; padding: 40px 20px; }}
h1 {{ font-size: clamp(1.8rem, 5vw, 2.8rem); line-height: 1.2; margin: 8px 0 16px; }}
.intro {{ max-width: 650px; margin-bottom: 28px; }}
.eyebrow {{ color: #376a59; text-transform: uppercase; letter-spacing: .1em; font-size: .8rem; font-weight: 700; }}
form {{ display: grid; grid-template-columns: 2fr 1fr 1fr auto; gap: 16px; align-items: end;
background: white; padding: 24px; border: 1px solid #d7e2dc; border-radius: 12px; }}
label {{ display: grid; gap: 6px; font-size: .9rem; font-weight: 600; min-width: 0; }}
input, select, button {{ font: inherit; min-height: 46px; border-radius: 6px; padding: 10px 12px; }}
input, select {{ width: 100%; min-width: 0; border: 1px solid #879d93; background: white; color: #18352d; }}
button {{ background: #23614d; color: white; border: 0; cursor: pointer; font-weight: 600; }}
:focus-visible {{ outline: 3px solid #aa6a12; outline-offset: 3px; }}
.summary {{ display: flex; justify-content: space-between; gap: 16px; align-items: center; margin: 24px 0; }}
a {{ color: #23614d; }}
.grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20px; }}
.card {{ background: white; border: 1px solid #d7e2dc; border-radius: 12px; padding: 24px; overflow-wrap: anywhere; }}
.card h2 {{ font-size: 1.25rem; margin: 20px 0 10px; }}
.tags {{ display: flex; flex-wrap: wrap; gap: 8px; font-size: .8rem; }}
.tags span {{ border-radius: 5px; padding: 3px 8px; background: #edf1ee; }}
.tags .available {{ background: #dcefe4; color: #195039; }}
.tags .maintenance {{ background: #fff0cc; color: #765000; }}
.tags .inactive {{ background: #e9e9ed; color: #50505a; }}
.location {{ color: #50665d; margin-bottom: 0; }}
.empty {{ grid-column: 1 / -1; padding: 28px; border: 1px dashed #879d93; border-radius: 12px; }}
@media (max-width: 900px) {{ form {{ grid-template-columns: 1fr 1fr; }} .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
@media (max-width: 600px) {{ main {{ padding: 28px 16px; }} form {{ padding: 18px; grid-template-columns: 1fr; }}
.grid {{ grid-template-columns: 1fr; }} .card {{ padding: 20px; }} .summary {{ flex-wrap: wrap; }} }}
</style>
</head>
<body>
<header>Community Lending</header>
<main>
<section class="intro"><p class="eyebrow">Shared resources, used well</p>
<h1>Equipment catalogue</h1><p>Find equipment for your next community activity.</p></section>
<form method="get" action="/" aria-label="Filter equipment">
<label>Search<input type="search" name="search" value="{escape(search)}" placeholder="Name or description"></label>
<label>Category<select name="category"><option value="">All categories</option>{category_options}</select></label>
<label>Status<select name="status"><option value="">All statuses</option>{status_options}</select></label>
<button type="submit">Apply filters</button>
</form>
<div class="summary"><span>{len(equipment)} equipment items</span><a href="/">Clear filters</a></div>
<section class="grid" aria-label="Equipment results">{cards}</section>
</main>
</body>
</html>"""
