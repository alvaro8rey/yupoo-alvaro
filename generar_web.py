"""
generar_web.py — Generador de catálogo web estático para la tienda de camisetas.

Uso:
    python generar_web.py

Genera web/index.html y copia las fotos a web/fotos/.
"""

import json
import shutil
from pathlib import Path

from db import init_db, get_todos_productos

# ── Configuración ────────────────────────────────────────────────────────────
BOT_USERNAME = "tu_bot"       # ← cambia por el username de tu bot sin @
STORE_NAME   = "Camisetas Premium"
MONEDA       = "€"
# ─────────────────────────────────────────────────────────────────────────────

ROOT      = Path(__file__).parent
WEB_DIR   = ROOT / "web"
FOTOS_DIR = WEB_DIR / "fotos"

PLACEHOLDER_SVG = """<svg xmlns='http://www.w3.org/2000/svg' width='300' height='300'
  viewBox='0 0 300 300'><rect width='300' height='300' fill='#e2e8f0'/>
  <text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle'
    font-family='sans-serif' font-size='14' fill='#94a3b8'>Sin imagen</text></svg>"""

CSS = """
:root {
  --primary: #1e3a5f;
  --accent:  #f59e0b;
  --bg:      #f8fafc;
  --card-bg: #ffffff;
  --text:    #1e293b;
  --muted:   #64748b;
  --radius:  12px;
  --shadow:  0 2px 12px rgba(0,0,0,.08);
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'Segoe UI', system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
}

header {
  background: var(--primary);
  color: #fff;
  padding: 1.5rem 2rem;
  text-align: center;
}

header h1 { font-size: clamp(1.4rem, 4vw, 2.2rem); letter-spacing: .02em; }
header p  { opacity: .75; margin-top: .4rem; font-size: .95rem; }

.catalog {
  max-width: 1200px;
  margin: 2rem auto;
  padding: 0 1rem;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 1.5rem;
}

.card {
  background: var(--card-bg);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: transform .2s, box-shadow .2s;
}

.card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0,0,0,.13);
}

.card-img-wrap {
  position: relative;
  width: 100%;
  padding-top: 100%;   /* square */
  overflow: hidden;
  background: #e2e8f0;
}

.card-img-wrap img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.id-badge {
  position: absolute;
  top: 8px;
  left: 8px;
  background: rgba(0,0,0,.55);
  color: #fff;
  font-size: .7rem;
  font-weight: 700;
  padding: .2rem .5rem;
  border-radius: 6px;
  letter-spacing: .04em;
}

.card-body {
  padding: 1rem 1.1rem 1.2rem;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: .5rem;
}

.card-title {
  font-size: 1rem;
  font-weight: 600;
  line-height: 1.35;
  flex: 1;
}

.card-price {
  font-size: 1.3rem;
  font-weight: 700;
  color: var(--primary);
}

.card-price span { font-size: .85rem; font-weight: 400; color: var(--muted); }

.card-sizes {
  display: flex;
  flex-wrap: wrap;
  gap: .3rem;
}

.size-tag {
  background: #e2e8f0;
  color: var(--muted);
  font-size: .7rem;
  font-weight: 600;
  padding: .15rem .45rem;
  border-radius: 4px;
}

.btn-tg {
  display: block;
  text-align: center;
  background: var(--accent);
  color: #fff;
  font-weight: 700;
  font-size: .95rem;
  padding: .7rem 1rem;
  border-radius: 8px;
  text-decoration: none;
  margin-top: .4rem;
  transition: background .15s;
}

.btn-tg:hover { background: #d97706; }

footer {
  text-align: center;
  padding: 2rem;
  color: var(--muted);
  font-size: .85rem;
}

@media (max-width: 480px) {
  .catalog { grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 1rem; }
  .card-title { font-size: .9rem; }
  .card-price { font-size: 1.1rem; }
  .btn-tg { font-size: .85rem; padding: .6rem; }
}
"""


def copiar_foto(foto_path: str, producto_id: int) -> str:
    """Copia la foto al directorio web/fotos/ y devuelve la ruta relativa HTML."""
    if not foto_path:
        return ""
    src = Path(foto_path)
    if not src.exists():
        return ""
    ext = src.suffix.lower()
    dest_name = f"producto_{producto_id}{ext}"
    dest = FOTOS_DIR / dest_name
    if not dest.exists() or src.stat().st_mtime > dest.stat().st_mtime:
        shutil.copy2(src, dest)
    return f"fotos/{dest_name}"


def render_card(producto: dict) -> str:
    prod_id   = producto["id"]
    nombre    = producto["nombre"]
    precio    = producto["precio"]
    foto_path = producto.get("foto_path", "")
    tallas    = json.loads(producto.get("tallas", '["S","M","L","XL","XXL"]'))

    img_rel = copiar_foto(foto_path, prod_id)

    if img_rel:
        img_tag = f'<img src="{img_rel}" alt="{nombre}" loading="lazy">'
    else:
        img_tag = (
            f'<img src="data:image/svg+xml,{PLACEHOLDER_SVG.replace(chr(10)," ")}" '
            f'alt="Sin imagen">'
        )

    if precio > 0:
        precio_html = f'{precio:.2f}<span> {MONEDA}</span>'
    else:
        precio_html = f'<span style="font-size:.9rem;color:#94a3b8">Precio a consultar</span>'

    tallas_html = "".join(f'<span class="size-tag">{t}</span>' for t in tallas)

    tg_link = f"https://t.me/{BOT_USERNAME}?start=producto_{prod_id}"

    return f"""
    <article class="card">
      <div class="card-img-wrap">
        {img_tag}
        <span class="id-badge">#{prod_id}</span>
      </div>
      <div class="card-body">
        <p class="card-title">{nombre}</p>
        <p class="card-price">{precio_html}</p>
        <div class="card-sizes">{tallas_html}</div>
        <a class="btn-tg" href="{tg_link}" target="_blank">
          📦 Pedir por Telegram
        </a>
      </div>
    </article>"""


def generar():
    init_db()
    WEB_DIR.mkdir(exist_ok=True)
    FOTOS_DIR.mkdir(exist_ok=True)

    productos = get_todos_productos(solo_activos=True)
    if not productos:
        print("[AVISO] No hay productos activos en la base de datos.")

    cards_html = "\n".join(render_card(p) for p in productos)

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{STORE_NAME}</title>
  <style>{CSS}</style>
</head>
<body>
  <header>
    <h1>{STORE_NAME}</h1>
    <p>Haz clic en cualquier producto para pedirlo directamente por Telegram</p>
  </header>

  <main class="catalog">
    {cards_html if cards_html else '<p style="text-align:center;color:#64748b;grid-column:1/-1">No hay productos disponibles en este momento.</p>'}
  </main>

  <footer>
    <p>{STORE_NAME} &bull; Todos los pedidos se gestionan por Telegram</p>
  </footer>
</body>
</html>
"""

    out = WEB_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"[OK] Web generada: {out}")
    print(f"     Productos incluidos: {len(productos)}")
    print(f"     Fotos copiadas a:    {FOTOS_DIR}")


if __name__ == "__main__":
    generar()
