"""
admin.py — Flask admin panel for the t-shirt store.

Run standalone:  python admin.py
Run with bot:    python main.py
"""

import os
import json
from functools import wraps

from flask import (
    Flask,
    render_template_string,
    request,
    redirect,
    url_for,
    session,
    flash,
    Response,
    abort,
)

import db

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "cambiar-en-produccion-xk92j")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

LIGAS = ["La Liga", "Premier League", "Bundesliga", "Serie A", "Ligue 1", "Selecciones"]
TALLAS_DISPONIBLES = ["S", "M", "L", "XL", "XXL", "XXXL"]

# ── CSS base ─────────────────────────────────────────────────────────────────

BASE_STYLE = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: #f0f2f5; display: flex; min-height: 100vh; }

/* Sidebar */
.sidebar {
    width: 220px; min-height: 100vh; background: #1a1d23;
    color: #cdd3dc; display: flex; flex-direction: column; flex-shrink: 0;
    position: fixed; top: 0; left: 0; bottom: 0; overflow-y: auto;
}
.sidebar .brand {
    padding: 24px 20px 16px; font-size: 1.1rem; font-weight: 700;
    color: #fff; border-bottom: 1px solid #2d3340; letter-spacing: .5px;
}
.sidebar .brand span { color: #5b9bd5; }
.sidebar nav { padding: 16px 0; flex: 1; }
.sidebar nav a {
    display: block; padding: 11px 20px; color: #9aa3b0; text-decoration: none;
    font-size: .9rem; transition: background .15s, color .15s; border-left: 3px solid transparent;
}
.sidebar nav a:hover, .sidebar nav a.active {
    background: #24293a; color: #fff; border-left-color: #5b9bd5;
}
.sidebar .logout-area { padding: 16px 20px; border-top: 1px solid #2d3340; }
.sidebar .logout-area a {
    color: #9aa3b0; text-decoration: none; font-size: .85rem;
}
.sidebar .logout-area a:hover { color: #e57373; }

/* Main content */
.main { margin-left: 220px; flex: 1; display: flex; flex-direction: column; }
.topbar {
    background: #fff; border-bottom: 1px solid #e0e4ea;
    padding: 16px 28px; display: flex; align-items: center; justify-content: space-between;
}
.topbar h1 { font-size: 1.2rem; font-weight: 600; color: #1a1d23; }
.content { padding: 28px; flex: 1; }

/* Cards */
.card {
    background: #fff; border-radius: 10px; box-shadow: 0 1px 4px rgba(0,0,0,.08);
    padding: 24px; margin-bottom: 24px;
}

/* Buttons */
.btn {
    display: inline-block; padding: 8px 16px; border-radius: 6px; border: none;
    cursor: pointer; font-size: .875rem; font-weight: 500; text-decoration: none;
    transition: opacity .15s; line-height: 1.4;
}
.btn:hover { opacity: .85; }
.btn-primary { background: #5b9bd5; color: #fff; }
.btn-success { background: #48bb78; color: #fff; }
.btn-danger  { background: #e57373; color: #fff; }
.btn-warning { background: #f6ad55; color: #fff; }
.btn-secondary { background: #e2e8f0; color: #4a5568; }
.btn-sm { padding: 5px 11px; font-size: .8rem; }

/* Flash messages */
.flash { padding: 12px 18px; border-radius: 7px; margin-bottom: 18px; font-size: .9rem; }
.flash-success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
.flash-error   { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
.flash-info    { background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }

/* Table */
table { width: 100%; border-collapse: collapse; font-size: .9rem; }
th { background: #f7f9fb; text-align: left; padding: 10px 14px;
     font-weight: 600; color: #4a5568; border-bottom: 2px solid #e2e8f0; }
td { padding: 10px 14px; border-bottom: 1px solid #f0f2f5; vertical-align: middle; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #fafbfc; }
.thumb { width: 52px; height: 52px; object-fit: cover; border-radius: 6px;
         border: 1px solid #e2e8f0; }
.thumb-placeholder {
    width: 52px; height: 52px; border-radius: 6px; background: #e2e8f0;
    display: flex; align-items: center; justify-content: center;
    color: #a0aec0; font-size: 1.4rem; border: 1px solid #cbd5e0;
}
.badge {
    display: inline-block; padding: 2px 8px; border-radius: 12px;
    font-size: .75rem; font-weight: 600;
}
.badge-active   { background: #d4edda; color: #155724; }
.badge-inactive { background: #f8d7da; color: #721c24; }

/* Forms */
.form-group { margin-bottom: 18px; }
label { display: block; font-size: .875rem; font-weight: 600; color: #4a5568;
        margin-bottom: 6px; }
input[type=text], input[type=number], input[type=url], input[type=password],
select, textarea {
    width: 100%; padding: 9px 12px; border: 1px solid #cbd5e0; border-radius: 6px;
    font-size: .9rem; color: #2d3748; transition: border-color .15s; background: #fff;
}
input:focus, select:focus, textarea:focus {
    outline: none; border-color: #5b9bd5; box-shadow: 0 0 0 3px rgba(91,155,213,.12);
}
.form-row { display: flex; gap: 20px; }
.form-row .form-group { flex: 1; }
.checkboxes { display: flex; flex-wrap: wrap; gap: 12px; }
.checkboxes label {
    display: flex; align-items: center; gap: 6px; font-weight: 400;
    cursor: pointer; font-size: .9rem;
}
.checkboxes input[type=checkbox] { width: auto; cursor: pointer; }

/* Photo grid */
.photo-grid { display: flex; flex-wrap: wrap; gap: 16px; }
.photo-card {
    width: 180px; border: 1px solid #e2e8f0; border-radius: 10px;
    overflow: hidden; background: #fff;
    box-shadow: 0 1px 3px rgba(0,0,0,.06);
}
.photo-card img { width: 100%; height: 140px; object-fit: cover; display: block; }
.photo-card .photo-actions {
    padding: 10px; display: flex; flex-direction: column; gap: 6px;
}
.photo-card.is-portada { border: 2px solid #5b9bd5; }
.portada-label {
    background: #5b9bd5; color: #fff; font-size: .7rem; font-weight: 700;
    padding: 2px 8px; text-align: center; letter-spacing: .5px;
}

/* Login page */
.login-wrap {
    min-height: 100vh; background: #1a1d23;
    display: flex; align-items: center; justify-content: center;
}
.login-box {
    background: #fff; border-radius: 12px; padding: 40px 36px;
    width: 360px; box-shadow: 0 8px 32px rgba(0,0,0,.25);
}
.login-box h2 { font-size: 1.4rem; color: #1a1d23; margin-bottom: 8px; }
.login-box p  { color: #718096; font-size: .9rem; margin-bottom: 28px; }

@media (max-width: 680px) {
    .sidebar { width: 100%; min-height: auto; position: relative; flex-direction: row; }
    .main { margin-left: 0; }
    .form-row { flex-direction: column; gap: 0; }
}
"""

# ── Layout helpers ────────────────────────────────────────────────────────────

def _render(title: str, content: str, active: str = "") -> str:
    flashes = ""
    for cat, msg in session.pop("_flashes", []) if False else []:
        pass  # handled below via get_flashed_messages inside template

    return render_template_string(
        BASE_LAYOUT,
        title=title,
        content=content,
        active=active,
        style=BASE_STYLE,
    )


BASE_LAYOUT = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} — Admin Tienda</title>
<style>{{ style }}</style>
</head>
<body>
<div class="sidebar">
  <div class="brand">Tienda <span>Admin</span></div>
  <nav>
    <a href="{{ url_for('productos_list') }}"
       class="{{ 'active' if active == 'productos' else '' }}">Productos</a>
  </nav>
  <div class="logout-area">
    <a href="{{ url_for('logout') }}">Cerrar sesion</a>
  </div>
</div>
<div class="main">
  <div class="topbar"><h1>{{ title }}</h1></div>
  <div class="content">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% for cat, msg in messages %}
        <div class="flash flash-{{ cat }}">{{ msg }}</div>
      {% endfor %}
    {% endwith %}
    {{ content | safe }}
  </div>
</div>
</body>
</html>"""

LOGIN_PAGE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Login — Admin Tienda</title>
<style>{{ style }}</style>
</head>
<body>
<div class="login-wrap">
  <div class="login-box">
    <h2>Admin Tienda</h2>
    <p>Introduce la contrasena para acceder al panel.</p>
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% for cat, msg in messages %}
        <div class="flash flash-{{ cat }}" style="margin-bottom:16px">{{ msg }}</div>
      {% endfor %}
    {% endwith %}
    <form method="post">
      <div class="form-group">
        <label for="pwd">Contrasena</label>
        <input type="password" id="pwd" name="password" autofocus required>
      </div>
      <button type="submit" class="btn btn-primary" style="width:100%;padding:11px">Entrar</button>
    </form>
  </div>
</div>
</body>
</html>"""


# ── Auth ──────────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated


@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            next_url = request.args.get("next") or url_for("productos_list")
            return redirect(next_url)
        flash("Contrasena incorrecta.", "error")
    return render_template_string(LOGIN_PAGE, style=BASE_STYLE)


@app.route("/admin/logout")
def logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("login"))


# ── Public photo endpoint ─────────────────────────────────────────────────────

@app.route("/foto/<int:foto_id>")
def serve_foto(foto_id: int):
    data = db.get_foto_datos(foto_id)
    if data is None:
        abort(404)
    # Try to detect image type from magic bytes
    mime = "image/jpeg"
    if data[:4] == b'\x89PNG':
        mime = "image/png"
    elif data[:6] in (b'GIF87a', b'GIF89a'):
        mime = "image/gif"
    elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        mime = "image/webp"
    return Response(data, mimetype=mime, headers={
        "Cache-Control": "public, max-age=86400"
    })


# ── Admin redirect ────────────────────────────────────────────────────────────

@app.route("/admin")
@app.route("/admin/")
@login_required
def admin_index():
    return redirect(url_for("productos_list"))


# ── Products list ─────────────────────────────────────────────────────────────

@app.route("/admin/productos")
@login_required
def productos_list():
    productos = db.get_todos_productos(solo_activos=False)

    rows = ""
    for p in productos:
        tallas = json.loads(p.get("tallas") or "[]")
        tallas_str = ", ".join(tallas) if tallas else "—"
        activo_badge = (
            '<span class="badge badge-active">Activo</span>' if p["activo"]
            else '<span class="badge badge-inactive">Inactivo</span>'
        )
        toggle_label = "Desactivar" if p["activo"] else "Activar"
        toggle_class = "btn-warning" if p["activo"] else "btn-success"

        if p.get("portada_id"):
            thumb = f'<img src="{url_for("serve_foto", foto_id=p["portada_id"])}" class="thumb" alt="">'
        else:
            thumb = '<div class="thumb-placeholder">T</div>'

        rows += f"""
        <tr>
          <td>{thumb}</td>
          <td><strong>{p['nombre']}</strong></td>
          <td>{p.get('liga','')}</td>
          <td>{p.get('equipo','')}</td>
          <td>€{p['precio']:.2f}</td>
          <td>{tallas_str}</td>
          <td>{activo_badge}</td>
          <td>
            <a href="{url_for('producto_editar', producto_id=p['id'])}" class="btn btn-secondary btn-sm">Editar</a>
            <a href="{url_for('producto_fotos', producto_id=p['id'])}" class="btn btn-primary btn-sm">Fotos</a>
            <form method="post" action="{url_for('producto_toggle', producto_id=p['id'])}" style="display:inline">
              <button class="btn {toggle_class} btn-sm">{toggle_label}</button>
            </form>
          </td>
        </tr>"""

    content = f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
      <p style="color:#718096">{len(productos)} producto(s)</p>
      <a href="{url_for('producto_nuevo')}" class="btn btn-success">+ Nuevo producto</a>
    </div>
    <div class="card" style="padding:0;overflow:hidden">
      <table>
        <thead>
          <tr>
            <th style="width:68px">Foto</th>
            <th>Nombre</th>
            <th>Liga</th>
            <th>Equipo</th>
            <th>Precio</th>
            <th>Tallas</th>
            <th>Estado</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""

    return render_template_string(BASE_LAYOUT, title="Productos", content=content,
                                  active="productos", style=BASE_STYLE)


# ── Toggle active ─────────────────────────────────────────────────────────────

@app.route("/admin/productos/<int:producto_id>/toggle", methods=["POST"])
@login_required
def producto_toggle(producto_id: int):
    p = db.get_producto_admin(producto_id)
    if not p:
        abort(404)
    nuevo = 0 if p["activo"] else 1
    with db.get_connection() as conn:
        conn.execute("UPDATE productos SET activo = ? WHERE id = ?", (nuevo, producto_id))
        conn.commit()
    flash("Estado actualizado.", "success")
    return redirect(url_for("productos_list"))


# ── Product form helpers ──────────────────────────────────────────────────────

def _product_form(p=None, action_url="", submit_label="Guardar", with_photos=True):
    p = p or {}
    nombre = p.get("nombre", "")
    precio = p.get("precio", 18)
    liga = p.get("liga", "")
    equipo = p.get("equipo", "")
    yupoo_url = p.get("yupoo_url", "")
    activo_checked = "checked" if p.get("activo", 1) else ""
    tallas_sel = json.loads(p.get("tallas") or "[]")

    ligas_opts = "".join(f'<option value="{l}">{l}</option>' for l in LIGAS)

    tallas_checks = ""
    for t in TALLAS_DISPONIBLES:
        chk = "checked" if t in tallas_sel else ""
        tallas_checks += f'<label><input type="checkbox" name="tallas" value="{t}" {chk}> {t}</label>'

    photos_section = ""
    if with_photos:
        photos_section = """
        <div class="form-group">
          <label>Fotos (puedes subir varias)</label>
          <input type="file" name="fotos" multiple accept="image/*"
                 style="width:100%;padding:8px;border:1px solid #cbd5e0;border-radius:6px;background:#fff">
          <p style="color:#718096;font-size:.8rem;margin-top:4px">
            La primera foto subida sera la portada.
          </p>
        </div>"""

    return f"""
    <form method="post" action="{action_url}" enctype="multipart/form-data">
      <div class="card">
        <div class="form-row">
          <div class="form-group">
            <label>Nombre <span style="color:#e53e3e">*</span></label>
            <input type="text" name="nombre" value="{nombre}" required>
          </div>
          <div class="form-group">
            <label>Precio (€)</label>
            <input type="number" name="precio" value="{precio}" step="0.01" min="0">
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Liga</label>
            <input type="text" name="liga" value="{liga}" list="ligas-list">
            <datalist id="ligas-list">{ligas_opts}</datalist>
          </div>
          <div class="form-group">
            <label>Equipo</label>
            <input type="text" name="equipo" value="{equipo}">
          </div>
        </div>
        <div class="form-group">
          <label>URL Yupoo</label>
          <input type="url" name="yupoo_url" value="{yupoo_url}" placeholder="https://...">
        </div>
        <div class="form-group">
          <label>Tallas disponibles</label>
          <div class="checkboxes">{tallas_checks}</div>
        </div>
        {photos_section}
        <div class="form-group">
          <label style="display:flex;align-items:center;gap:8px;font-weight:400;cursor:pointer">
            <input type="checkbox" name="activo" value="1" {activo_checked} style="width:auto">
            Producto activo (visible en la tienda)
          </label>
        </div>
        <div style="display:flex;gap:12px;margin-top:8px">
          <button type="submit" class="btn btn-primary">{submit_label}</button>
          <a href="{url_for('productos_list')}" class="btn btn-secondary">Cancelar</a>
        </div>
      </div>
    </form>"""


def _parse_product_form(form):
    tallas = form.getlist("tallas")
    return {
        "nombre": form.get("nombre", "").strip(),
        "precio": float(form.get("precio") or 18),
        "liga": form.get("liga", "").strip(),
        "equipo": form.get("equipo", "").strip(),
        "yupoo_url": form.get("yupoo_url", "").strip(),
        "tallas": json.dumps(tallas),
        "activo": 1 if form.get("activo") else 0,
    }


# ── New product ───────────────────────────────────────────────────────────────

@app.route("/admin/productos/nuevo", methods=["GET", "POST"])
@login_required
def producto_nuevo():
    if request.method == "POST":
        data = _parse_product_form(request.form)
        if not data["nombre"]:
            flash("El nombre es obligatorio.", "error")
            return render_template_string(
                BASE_LAYOUT, title="Nuevo producto",
                content=_product_form(action_url=url_for("producto_nuevo"),
                                      submit_label="Crear producto"),
                active="productos", style=BASE_STYLE)

        with db.get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO productos (nombre, precio, liga, equipo, yupoo_url, tallas, activo) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (data["nombre"], data["precio"], data["liga"], data["equipo"],
                 data["yupoo_url"], data["tallas"], data["activo"])
            )
            conn.commit()
            producto_id = cur.lastrowid

        # Handle photo uploads
        fotos = request.files.getlist("fotos")
        first = True
        for f in fotos:
            if f and f.filename:
                datos = f.read()
                if datos:
                    db.guardar_foto(producto_id, datos, f.filename, es_portada=first)
                    first = False

        flash(f"Producto '{data['nombre']}' creado.", "success")
        return redirect(url_for("productos_list"))

    content = _product_form(action_url=url_for("producto_nuevo"), submit_label="Crear producto")
    return render_template_string(BASE_LAYOUT, title="Nuevo producto", content=content,
                                  active="productos", style=BASE_STYLE)


# ── Edit product ──────────────────────────────────────────────────────────────

@app.route("/admin/productos/<int:producto_id>/editar", methods=["GET", "POST"])
@login_required
def producto_editar(producto_id: int):
    p = db.get_producto_admin(producto_id)
    if not p:
        abort(404)

    if request.method == "POST":
        data = _parse_product_form(request.form)
        if not data["nombre"]:
            flash("El nombre es obligatorio.", "error")
        else:
            with db.get_connection() as conn:
                conn.execute(
                    "UPDATE productos SET nombre=?, precio=?, liga=?, equipo=?, "
                    "yupoo_url=?, tallas=?, activo=? WHERE id=?",
                    (data["nombre"], data["precio"], data["liga"], data["equipo"],
                     data["yupoo_url"], data["tallas"], data["activo"], producto_id)
                )
                conn.commit()
            flash("Producto actualizado.", "success")
            return redirect(url_for("productos_list"))

    action = url_for("producto_editar", producto_id=producto_id)
    content = _product_form(p=p, action_url=action, submit_label="Guardar cambios",
                            with_photos=False)
    return render_template_string(BASE_LAYOUT, title=f"Editar: {p['nombre']}",
                                  content=content, active="productos", style=BASE_STYLE)


# ── Photo management ──────────────────────────────────────────────────────────

@app.route("/admin/productos/<int:producto_id>/fotos", methods=["GET", "POST"])
@login_required
def producto_fotos(producto_id: int):
    p = db.get_producto_admin(producto_id)
    if not p:
        abort(404)

    if request.method == "POST":
        fotos = request.files.getlist("fotos")
        count = 0
        tiene_fotos = bool(db.get_fotos_producto(producto_id))
        first = not tiene_fotos
        for f in fotos:
            if f and f.filename:
                datos = f.read()
                if datos:
                    db.guardar_foto(producto_id, datos, f.filename, es_portada=first)
                    first = False
                    count += 1
        if count:
            flash(f"{count} foto(s) subida(s).", "success")
        else:
            flash("No se subio ninguna foto.", "info")
        return redirect(url_for("producto_fotos", producto_id=producto_id))

    fotos = db.get_fotos_producto(producto_id)

    cards = ""
    for foto in fotos:
        is_portada = foto["es_portada"]
        portada_label = '<div class="portada-label">PORTADA</div>' if is_portada else ""
        portada_btn = "" if is_portada else f"""
          <form method="post" action="{url_for('foto_set_portada', foto_id=foto['id'])}">
            <button class="btn btn-primary btn-sm" style="width:100%">Establecer portada</button>
          </form>"""
        cards += f"""
        <div class="photo-card {'is-portada' if is_portada else ''}">
          {portada_label}
          <img src="{url_for('serve_foto', foto_id=foto['id'])}" alt="{foto['nombre']}">
          <div class="photo-actions">
            {portada_btn}
            <form method="post" action="{url_for('foto_eliminar', foto_id=foto['id'])}"
                  onsubmit="return confirm('Eliminar esta foto?')">
              <button class="btn btn-danger btn-sm" style="width:100%">Eliminar</button>
            </form>
          </div>
        </div>"""

    if not cards:
        cards = '<p style="color:#718096;padding:24px 0">Este producto no tiene fotos aun.</p>'

    upload_form = f"""
    <div class="card">
      <h3 style="margin-bottom:16px;font-size:1rem">Subir nuevas fotos</h3>
      <form method="post" action="{url_for('producto_fotos', producto_id=producto_id)}"
            enctype="multipart/form-data">
        <div class="form-group">
          <input type="file" name="fotos" multiple accept="image/*"
                 style="width:100%;padding:8px;border:1px solid #cbd5e0;border-radius:6px;background:#fff">
        </div>
        <button type="submit" class="btn btn-primary">Subir fotos</button>
      </form>
    </div>"""

    content = f"""
    <div style="margin-bottom:16px">
      <a href="{url_for('productos_list')}" class="btn btn-secondary btn-sm">Volver a productos</a>
      <a href="{url_for('producto_editar', producto_id=producto_id)}"
         class="btn btn-secondary btn-sm" style="margin-left:8px">Editar producto</a>
    </div>
    <div class="card">
      <h3 style="margin-bottom:20px;font-size:1rem">Fotos del producto ({len(fotos)})</h3>
      <div class="photo-grid">{cards}</div>
    </div>
    {upload_form}"""

    return render_template_string(BASE_LAYOUT, title=f"Fotos: {p['nombre']}",
                                  content=content, active="productos", style=BASE_STYLE)


@app.route("/admin/fotos/<int:foto_id>/portada", methods=["POST"])
@login_required
def foto_set_portada(foto_id: int):
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT producto_id FROM fotos_producto WHERE id = ?", (foto_id,)
        ).fetchone()
    if not row:
        abort(404)
    producto_id = row["producto_id"]
    db.set_portada(foto_id, producto_id)
    flash("Portada actualizada.", "success")
    return redirect(url_for("producto_fotos", producto_id=producto_id))


@app.route("/admin/fotos/<int:foto_id>/eliminar", methods=["POST"])
@login_required
def foto_eliminar(foto_id: int):
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT producto_id FROM fotos_producto WHERE id = ?", (foto_id,)
        ).fetchone()
    if not row:
        abort(404)
    producto_id = row["producto_id"]
    db.eliminar_foto(foto_id)
    flash("Foto eliminada.", "success")
    return redirect(url_for("producto_fotos", producto_id=producto_id))


# ── Init & run ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    db.init_db()
    app.run(host="0.0.0.0", port=8080, debug=True)
