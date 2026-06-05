"""
generar_web.py — Generador de catálogo web estático.

Uso:
    python generar_web.py

Genera web/index.html y web/producto_X.html por cada producto.
"""

import json
import shutil
from pathlib import Path

from db import init_db, get_todos_productos

# ── Configuración ────────────────────────────────────────────────────────────
BOT_USERNAME = "tu_bot"          # ← username del bot sin @
STORE_NAME   = "Camisetas Premium"
MONEDA       = "€"
PRECIO_BASE           = 18
PRECIO_NOMBRE_NUMERO  = 21
PRECIO_CON_PARCHES    = 22
# ─────────────────────────────────────────────────────────────────────────────

ROOT           = Path(__file__).parent
WEB_DIR        = ROOT / "web"
FOTOS_DIR      = WEB_DIR / "fotos"
FRONTEND_PUBLIC = ROOT / "frontend" / "public"
FRONTEND_FOTOS  = FRONTEND_PUBLIC / "fotos"

PLACEHOLDER = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='400'%3E%3Crect width='400' height='400' fill='%23e2e8f0'/%3E%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' font-family='sans-serif' font-size='16' fill='%2394a3b8'%3ESin imagen%3C/text%3E%3C/svg%3E"

# ── CSS compartido ────────────────────────────────────────────────────────────
CSS_BASE = """
:root{--primary:#111827;--accent:#2563eb;--accent2:#f59e0b;--bg:#f9fafb;--card:#fff;--text:#111827;--muted:#6b7280;--border:#e5e7eb;--radius:14px}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
a{color:inherit;text-decoration:none}
header{background:var(--primary);color:#fff;padding:1.2rem 2rem;display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap}
header h1{font-size:clamp(1.1rem,3vw,1.6rem);letter-spacing:.03em;font-weight:800}
header .tagline{opacity:.6;font-size:.85rem}
.container{max-width:1200px;margin:0 auto;padding:0 1.2rem}

/* ── INDEX ── */
.filtro{padding:1.5rem 0 .5rem;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.8rem}
.filtro h2{font-size:1.1rem;font-weight:700;color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:1.2rem;padding-bottom:3rem}
.card{background:var(--card);border-radius:var(--radius);border:1px solid var(--border);overflow:hidden;display:flex;flex-direction:column;transition:transform .2s,box-shadow .2s;cursor:pointer}
.card:hover{transform:translateY(-4px);box-shadow:0 12px 28px rgba(0,0,0,.1)}
.card-img{position:relative;padding-top:100%;background:#e5e7eb;overflow:hidden}
.card-img img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;transition:transform .3s}
.card:hover .card-img img{transform:scale(1.04)}
.id-badge{position:absolute;top:8px;left:8px;background:rgba(0,0,0,.6);color:#fff;font-size:.65rem;font-weight:700;padding:.2rem .5rem;border-radius:6px}
.card-body{padding:.85rem 1rem 1rem;flex:1;display:flex;flex-direction:column;gap:.3rem}
.card-name{font-size:.9rem;font-weight:600;line-height:1.4;flex:1}
.card-price{font-size:1.15rem;font-weight:800;color:var(--accent)}
.card-price small{font-size:.75rem;font-weight:400;color:var(--muted)}
.card-cta{margin-top:.6rem;font-size:.8rem;color:var(--accent);font-weight:600;display:flex;align-items:center;gap:.3rem}

/* ── DETALLE ── */
.back{display:inline-flex;align-items:center;gap:.4rem;color:var(--muted);font-size:.85rem;padding:1.2rem 0 .5rem;transition:color .15s}
.back:hover{color:var(--accent)}
.detail{display:grid;grid-template-columns:1fr 1fr;gap:2.5rem;padding:1rem 0 3rem;align-items:start}
.gallery{display:flex;flex-direction:column;gap:.6rem}
.gallery-main{border-radius:var(--radius);overflow:hidden;background:#e5e7eb;aspect-ratio:1;width:100%}
.gallery-main img{width:100%;height:100%;object-fit:cover;cursor:zoom-in}
.gallery-thumbs{display:flex;flex-wrap:wrap;gap:.4rem}
.thumb{width:70px;height:70px;border-radius:8px;overflow:hidden;border:2px solid transparent;cursor:pointer;flex-shrink:0}
.thumb.active,.thumb:hover{border-color:var(--accent)}
.thumb img{width:100%;height:100%;object-fit:cover}
.info{display:flex;flex-direction:column;gap:1rem}
.info-id{font-size:.8rem;color:var(--muted);font-weight:600;letter-spacing:.05em}
.info h1{font-size:clamp(1.2rem,3vw,1.7rem);font-weight:800;line-height:1.3}
.precios{background:#f0f9ff;border:1px solid #bae6fd;border-radius:10px;padding:1rem 1.2rem;display:flex;flex-direction:column;gap:.5rem}
.precios h3{font-size:.8rem;font-weight:700;color:#0369a1;text-transform:uppercase;letter-spacing:.06em;margin-bottom:.2rem}
.precio-fila{display:flex;justify-content:space-between;align-items:center;font-size:.9rem}
.precio-fila .label{color:var(--text)}
.precio-fila .val{font-weight:800;color:var(--primary);font-size:1rem}
.precio-fila .val.destacado{color:var(--accent);font-size:1.2rem}
.divider{height:1px;background:var(--border)}
.info-section h3{font-size:.8rem;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:.4rem}
.info-section p{font-size:.9rem;color:var(--text);line-height:1.6}
.btn-tg{display:flex;align-items:center;justify-content:center;gap:.6rem;background:#2563eb;color:#fff;font-weight:700;font-size:1rem;padding:.9rem 1.5rem;border-radius:10px;transition:background .15s;margin-top:.5rem}
.btn-tg:hover{background:#1d4ed8}
.btn-tg svg{width:22px;height:22px;fill:#fff;flex-shrink:0}
footer{text-align:center;padding:2rem;color:var(--muted);font-size:.82rem;border-top:1px solid var(--border)}
@media(max-width:700px){
  .detail{grid-template-columns:1fr}
  .grid{grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:.8rem}
}
"""

SCRIPT_GALLERY = """
function setMain(src){document.getElementById('main-img').src=src;document.querySelectorAll('.thumb').forEach(t=>t.classList.toggle('active',t.dataset.src===src))}
document.querySelectorAll('.thumb').forEach(t=>t.addEventListener('click',()=>setMain(t.dataset.src)));
"""


# ── helpers ───────────────────────────────────────────────────────────────────

def copiar_fotos_producto(producto: dict) -> list[str]:
    """Copia todas las imágenes del álbum a web/fotos/ y devuelve rutas relativas."""
    prod_id   = producto["id"]
    foto_path = producto.get("foto_path", "")
    rutas = []

    if foto_path:
        cover = Path(foto_path)
        if cover.exists():
            # buscar todas las imágenes en la misma carpeta
            carpeta = cover.parent
            imagenes = sorted(carpeta.glob("*.jp*g")) + sorted(carpeta.glob("*.png"))
            imagenes = sorted(set(imagenes), key=lambda p: p.name)
            if not imagenes:
                imagenes = [cover]
            for i, src in enumerate(imagenes):
                dest_name = f"p{prod_id}_{i:03d}{src.suffix.lower()}"
                dest = FOTOS_DIR / dest_name
                if not dest.exists() or src.stat().st_mtime > dest.stat().st_mtime:
                    shutil.copy2(src, dest)
                rutas.append(f"fotos/{dest_name}")

    return rutas


def img_tag(src: str, alt: str, clss: str = "") -> str:
    s = src if src else PLACEHOLDER
    return f'<img src="{s}" alt="{alt}" loading="lazy"{"" if not clss else f" class={chr(39)+clss+chr(39)}"}>'


# ── página de detalle ─────────────────────────────────────────────────────────

def generar_detalle(producto: dict, fotos: list[str]):
    prod_id = producto["id"]
    nombre  = producto["nombre"]
    tg_link = f"https://t.me/{BOT_USERNAME}?start=producto_{prod_id}"

    main_foto = fotos[0] if fotos else PLACEHOLDER

    thumbs_html = ""
    for f in fotos:
        active = "active" if f == main_foto else ""
        thumbs_html += f'<div class="thumb {active}" data-src="{f}"><img src="{f}" alt=""></div>'

    gallery_html = f"""
    <div class="gallery">
      <div class="gallery-main">
        <img id="main-img" src="{main_foto}" alt="{nombre}">
      </div>
      {"" if len(fotos) <= 1 else f'<div class="gallery-thumbs">{thumbs_html}</div>'}
    </div>"""

    precios_html = f"""
    <div class="precios">
      <h3>Opciones de precio</h3>
      <div class="precio-fila">
        <span class="label">Sin personalización</span>
        <span class="val destacado">{PRECIO_BASE} {MONEDA}</span>
      </div>
      <div class="precio-fila">
        <span class="label">Con nombre y número</span>
        <span class="val">{PRECIO_NOMBRE_NUMERO} {MONEDA}</span>
      </div>
      <div class="precio-fila">
        <span class="label">Con nombre, número y parches</span>
        <span class="val">{PRECIO_CON_PARCHES} {MONEDA}</span>
      </div>
    </div>"""

    info_html = f"""
    <div class="info">
      <p class="info-id">REF #{prod_id:04d}</p>
      <h1>{nombre}</h1>
      {precios_html}
      <div class="info-section">
        <h3>Personalización</h3>
        <p>Puedes añadir nombre y número de dorsal, así como parches oficiales (Liga, Champions, Mundial…). Indícalo al hacer el pedido.</p>
      </div>
      <div class="info-section">
        <h3>Envío</h3>
        <p>Envío a toda España. Tiempo estimado: 10–15 días hábiles desde la confirmación del pedido.</p>
      </div>
      <div class="divider"></div>
      <a class="btn-tg" href="{tg_link}" target="_blank">
        <svg viewBox="0 0 24 24"><path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12L7.17 13.954l-2.96-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.978.605z"/></svg>
        Pedir por Telegram
      </a>
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{nombre} — {STORE_NAME}</title>
  <style>{CSS_BASE}</style>
</head>
<body>
  <header>
    <h1><a href="index.html">{STORE_NAME}</a></h1>
    <span class="tagline">Camisetas de fútbol de calidad</span>
  </header>
  <div class="container">
    <a class="back" href="index.html">← Volver al catálogo</a>
    <div class="detail">
      {gallery_html}
      {info_html}
    </div>
  </div>
  <footer><p>{STORE_NAME} · Pedidos y consultas por Telegram</p></footer>
  <script>{SCRIPT_GALLERY}</script>
</body>
</html>"""


# ── tarjeta del índice ────────────────────────────────────────────────────────

def render_card(producto: dict, fotos: list[str]) -> str:
    prod_id = producto["id"]
    nombre  = producto["nombre"]
    foto    = fotos[0] if fotos else PLACEHOLDER

    return f"""
    <a class="card" href="producto_{prod_id}.html">
      <div class="card-img">
        <img src="{foto}" alt="{nombre}" loading="lazy">
        <span class="id-badge">#{prod_id:04d}</span>
      </div>
      <div class="card-body">
        <p class="card-name">{nombre}</p>
        <p class="card-price">Desde {PRECIO_BASE} <small>{MONEDA}</small></p>
        <p class="card-cta">Ver detalle →</p>
      </div>
    </a>"""


# ── índice ────────────────────────────────────────────────────────────────────

def generar_index(productos: list[dict], fotos_map: dict) -> str:
    cards = "\n".join(render_card(p, fotos_map[p["id"]]) for p in productos)
    empty = '<p style="grid-column:1/-1;text-align:center;color:var(--muted);padding:3rem">No hay productos disponibles.</p>'

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{STORE_NAME}</title>
  <style>{CSS_BASE}</style>
</head>
<body>
  <header>
    <h1>{STORE_NAME}</h1>
    <span class="tagline">Camisetas de fútbol · Pedidos por Telegram</span>
  </header>
  <div class="container">
    <div class="filtro">
      <h2>{len(productos)} productos disponibles</h2>
    </div>
    <div class="grid">
      {cards if cards else empty}
    </div>
  </div>
  <footer><p>{STORE_NAME} · Todos los pedidos se gestionan por Telegram</p></footer>
</body>
</html>"""


# ── exportar data.json para la SPA React ─────────────────────────────────────

def copiar_fotos_frontend(producto: dict) -> list[str]:
    """Copia imágenes del producto a frontend/public/fotos/ y devuelve rutas relativas."""
    prod_id   = producto["id"]
    foto_path = producto.get("foto_path", "")
    rutas = []

    if foto_path:
        cover = Path(foto_path)
        if cover.exists():
            carpeta  = cover.parent
            imagenes = sorted(set(sorted(carpeta.glob("*.jp*g")) + sorted(carpeta.glob("*.png"))), key=lambda p: p.name)
            if not imagenes:
                imagenes = [cover]
            for i, src in enumerate(imagenes):
                dest_name = f"p{prod_id}_{i:03d}{src.suffix.lower()}"
                dest = FRONTEND_FOTOS / dest_name
                if not dest.exists() or src.stat().st_mtime > dest.stat().st_mtime:
                    shutil.copy2(src, dest)
                rutas.append(f"fotos/{dest_name}")

    return rutas


def exportar_json():
    """Genera frontend/public/data.json con todos los productos activos."""
    init_db()
    FRONTEND_PUBLIC.mkdir(parents=True, exist_ok=True)
    FRONTEND_FOTOS.mkdir(parents=True, exist_ok=True)

    productos = get_todos_productos(solo_activos=True)
    if not productos:
        print("[AVISO] No hay productos activos en la base de datos.")

    data = []
    for p in productos:
        fotos = copiar_fotos_frontend(p)
        foto_cover = fotos[0] if fotos else ""
        data.append({
            "id":        p["id"],
            "nombre":    p["nombre"],
            "precio":    p["precio"],
            "foto_path": foto_cover,
            "yupoo_url": p["yupoo_url"],
            "tallas":    json.loads(p["tallas"]) if isinstance(p["tallas"], str) else p["tallas"],
            "liga":      p.get("liga", ""),
            "equipo":    p.get("equipo", ""),
            "fotos":     fotos,
        })

    out = FRONTEND_PUBLIC / "data.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    total_fotos = sum(len(d["fotos"]) for d in data)
    print(f"[OK] data.json generado en: {out}")
    print(f"     {len(data)} productos · {total_fotos} fotos")


# ── main ──────────────────────────────────────────────────────────────────────

def generar():
    # ── Export JSON for the React SPA ──
    exportar_json()

    # ── Old static HTML generation (kept for reference, commented out) ──
    # init_db()
    # WEB_DIR.mkdir(exist_ok=True)
    # FOTOS_DIR.mkdir(exist_ok=True)
    # productos = get_todos_productos(solo_activos=True)
    # if not productos:
    #     print("[AVISO] No hay productos activos en la base de datos.")
    #     return
    # fotos_map = {}
    # for p in productos:
    #     fotos_map[p["id"]] = copiar_fotos_producto(p)
    # (WEB_DIR / "index.html").write_text(generar_index(productos, fotos_map), encoding="utf-8")
    # for p in productos:
    #     html = generar_detalle(p, fotos_map[p["id"]])
    #     (WEB_DIR / f"producto_{p['id']}.html").write_text(html, encoding="utf-8")
    # print(f"[OK] Web generada en: {WEB_DIR}")
    # print(f"     {len(productos)} productos · {sum(len(v) for v in fotos_map.values())} fotos")


if __name__ == "__main__":
    generar()
