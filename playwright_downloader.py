"""
Yupoo Downloader con Playwright — evita bloqueos WAF usando navegador real.

Instalación:
    pip install playwright httpx aiofiles Pillow deep-translator
    playwright install chromium

Uso interactivo:
    python playwright_downloader.py

Uso directo:
    python playwright_downloader.py https://nombre.x.yupoo.com
    python playwright_downloader.py https://nombre.x.yupoo.com --solo-portadas
    python playwright_downloader.py https://nombre.x.yupoo.com --urls https://.../albums/123
"""

import asyncio
import random
import re
import argparse
import logging
from pathlib import Path
from io import BytesIO

import aiofiles
from PIL import Image, ImageFile
from playwright.async_api import async_playwright, Page
from deep_translator import GoogleTranslator
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich import print as rprint

ImageFile.LOAD_TRUNCATED_IMAGES = True
logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("yupoo")

console = Console()
PURPLE  = "#6149ab"
LPURPLE = "#baa6ff"
GREEN   = "#0ba162"
RED     = "#c7383f"


# ------------------------------------------------------------------ helpers

def sanitize(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name.strip("_ ")[:120] or "sin_titulo"


def translate(text: str) -> str:
    try:
        result = GoogleTranslator(source="auto", target="es").translate(text)
        return result if result else text
    except Exception:
        return text


async def human_delay(min_s=0.3, max_s=0.8):
    await asyncio.sleep(random.uniform(min_s, max_s))


# ------------------------------------------------------------------ scraper

class YupooPlaywright:
    def __init__(self, base_url: str, output: Path, covers_only=False, no_translate=False, headless=True):
        self.base_url = base_url.rstrip("/")
        self.output = output
        self.covers_only = covers_only
        self.translate = not no_translate
        self.headless = headless
        self.catalog_name = self._extract_catalog_name(base_url)

    def _extract_catalog_name(self, url: str) -> str:
        m = re.search(r'https?://([^.]+)\.x\.yupoo\.com', url)
        if m:
            return m.group(1)
        m = re.search(r'https?://([^.]+)\.yupoo\.com', url)
        return m.group(1) if m else "catalogo"

    # -------------------------------------------------------- page navigation

    async def get_page_count(self, page: Page, url: str) -> int:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await human_delay()
        inp = await page.query_selector('form.pagination__jumpwrap input[name="page"]')
        if inp:
            return int(await inp.get_attribute("max") or "1")
        return 1

    async def scrape_albums_from_page(self, page: Page, url: str) -> list[dict]:
        captured_covers: dict[str, bytes] = {}

        async def capture_response(response):
            r_url = response.url
            if "photo.yupoo.com" in r_url:
                try:
                    body = await response.body()
                    if body:
                        captured_covers[r_url] = body
                except Exception:
                    pass

        if self.covers_only:
            page.on("response", capture_response)

        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await human_delay()

        anchors = await page.query_selector_all("a.album__main")
        albums = []
        for a in anchors:
            href = await a.get_attribute("href") or ""
            title = await a.get_attribute("title") or await a.inner_text() or "sin_titulo"
            title = title.strip()
            if href.startswith("http"):
                album_url = href
            else:
                album_url = f"https://{self.catalog_name}.x.yupoo.com{href}"
            album_url = re.sub(r'\?.*$', '', album_url) + "?uid=1"

            cover_bytes = None
            cover_url = None
            if self.covers_only:
                img = await a.query_selector("img")
                if img:
                    src = await img.get_attribute("src") or ""
                    if src:
                        cover_url = "https:" + src if src.startswith("//") else src
                        cover_bytes = captured_covers.get(cover_url)

            albums.append({"title": title, "url": album_url, "cover": cover_bytes, "cover_url": cover_url})

        if self.covers_only:
            page.remove_listener("response", capture_response)

        return albums

    async def get_all_albums(self, page: Page) -> list[dict]:
        first = f"{self.base_url}/albums?tab=gallery&page=1"
        total = await self.get_page_count(page, first)
        log.info(f"Páginas del catálogo: {total}")
        albums = []
        for p in range(1, total + 1):
            url = f"{self.base_url}/albums?tab=gallery&page={p}"
            page_albums = await self.scrape_albums_from_page(page, url)
            albums.extend(page_albums)
            log.info(f"  Página {p}/{total}: {len(page_albums)} álbums")
            await human_delay()
        log.info(f"Total álbums encontrados: {len(albums)}")
        return albums

    async def get_albums_from_category(self, page: Page, cat_url: str) -> list[dict]:
        base = re.sub(r'\?.*$', '', cat_url.rstrip("/"))
        total = await self.get_page_count(page, f"{base}?page=1")
        albums = []
        for p in range(1, total + 1):
            page_albums = await self.scrape_albums_from_page(page, f"{base}?page={p}")
            albums.extend(page_albums)
            await human_delay()
        return albums

    async def _fetch_image(self, page: Page, url: str) -> bytes | None:
        """Navega a la URL de imagen con el browser y captura los bytes."""
        result = {}
        async def on_resp(response):
            if result:
                return
            ct = response.headers.get("content-type", "")
            if "image" in ct:
                try:
                    body = await response.body()
                    if body and len(body) > 1000:
                        result["body"] = body
                except Exception:
                    pass
        page.on("response", on_resp)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        except Exception:
            pass
        await asyncio.sleep(0.5)
        page.remove_listener("response", on_resp)
        if not result:
            log.warning(f"No se recibió imagen válida para: {url}")
        return result.get("body")

    async def _fetch_via_browser(self, page: Page, url: str) -> bytes | None:
        """Descarga una URL de imagen navegando a ella con el browser real."""
        captured = {}
        async def on_response(response):
            if response.url == url:
                try:
                    captured["body"] = await response.body()
                except Exception:
                    pass
        page.on("response", on_response)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(0.5)
        except Exception:
            pass
        page.remove_listener("response", on_response)
        return captured.get("body")

    async def download_album(self, page: Page, album: dict):
        title_raw = album["title"]
        title_es = translate(title_raw) if self.translate else title_raw
        folder = sanitize(title_es)
        album_dir = self.output / self.catalog_name / folder

        if album_dir.exists() and any(album_dir.iterdir()):
            log.info(f"  [skip] {folder}")
            return

        # resolver colisiones de nombre usando .url para identificar cada álbum
        album_url_clean = re.sub(r'\?.*$', '', album["url"])
        base_dir = album_dir
        n = 2
        while album_dir.exists() and any(album_dir.iterdir()):
            url_file = album_dir / ".url"
            if url_file.exists() and url_file.read_text().strip() == album_url_clean:
                # misma carpeta, mismo álbum → skip
                log.info(f"  [skip] {album_dir.name}")
                return
            # carpeta con otro álbum → probar siguiente sufijo
            album_dir = base_dir.parent / f"{base_dir.name} - {n}"
            n += 1

        log.info(f"  Álbum: {title_raw!r} -> {album_dir.name!r}")
        album_dir.mkdir(parents=True, exist_ok=True)
        (album_dir / ".url").write_text(album_url_clean)

        # modo solo portadas: entrar al álbum y coger solo la primera imagen
        if self.covers_only:
            folder_name = sanitize(title_es)
            path = album_dir / f"{folder_name}.jpg"

            captured = {}
            async def capture_first(response):
                url = response.url
                if "photo.yupoo.com" in url and not captured:
                    try:
                        body = await response.body()
                        if body:
                            captured["body"] = body
                            captured["url"] = url
                    except Exception:
                        pass

            page.on("response", capture_first)
            try:
                await page.goto(album["url"], wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(0.8)
            except Exception as e:
                log.warning(f"  Timeout: {e}")
            page.remove_listener("response", capture_first)

            if captured.get("body"):
                await self.save_image(captured["body"], path)
                size_kb = len(captured["body"]) // 1024
                log.info(f"    guardada: {path.name} ({size_kb}KB)")
            else:
                log.warning(f"    sin imagen: {title_raw!r}")
                try:
                    album_dir.rmdir()
                except Exception:
                    pass
            return

        try:
            await page.goto(album["url"], wait_until="domcontentloaded", timeout=20000)
        except Exception as e:
            log.warning(f"  Timeout cargando álbum, continuando: {e}")
            return
        await human_delay(0.2, 0.5)

        # scroll para forzar que el DOM cargue todos los elementos lazy
        prev_height = 0
        for _ in range(30):
            await page.evaluate("window.scrollBy(0, 800)")
            await asyncio.sleep(0.2)
            height = await page.evaluate("document.body.scrollHeight")
            scroll_y = await page.evaluate("window.scrollY + window.innerHeight")
            if scroll_y >= height and height == prev_height:
                break
            prev_height = height
        await asyncio.sleep(0.5)

        # obtener URLs originales del DOM (data-origin-src = alta resolución)
        if self.covers_only:
            cover = await page.query_selector(".showalbumheader__gallerycover img")
            src = await cover.get_attribute("src") if cover else ""
            img_urls = ["https:" + src] if src and src.startswith("//") else ([src] if src else [])
        else:
            img_urls = []
            divs = await page.query_selector_all("div.showalbum__children")
            for div in divs:
                wrap = await div.query_selector(".image__imagewrap")
                if wrap and await wrap.get_attribute("data-type") == "video":
                    continue
                img = await div.query_selector("img")
                if not img:
                    continue
                src = await img.get_attribute("data-origin-src") or await img.get_attribute("src") or ""
                if src:
                    img_urls.append("https:" + src if src.startswith("//") else src)

        if not img_urls:
            log.warning(f"  Sin imágenes en DOM: {title_raw!r}")
            try:
                album_dir.rmdir()
            except Exception:
                pass
            return

        log.info(f"  {len(img_urls)} imágenes")
        saved = 0
        for i, url in enumerate(img_urls, 1):
            filename = re.findall(r'/([^/?]+)', url)[-1]
            path = album_dir / f"{Path(filename).stem}.jpg"
            if path.exists():
                saved += 1
                continue
            # navegar directamente a la URL de la imagen — el navegador la carga sin WAF
            body = await self._fetch_image(page, url)
            if body:
                await self.save_image(body, path)
                log.info(f"    [{i}/{len(img_urls)}] {path.name}")
                saved += 1
            else:
                log.warning(f"    [{i}/{len(img_urls)}] fallido: {url}")
            await asyncio.sleep(0.2)

        if saved == 0:
            try:
                album_dir.rmdir()
            except Exception:
                pass

    async def save_image(self, img_bytes: bytes, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            img = Image.open(BytesIO(img_bytes)).convert("RGB")
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=95)
            async with aiofiles.open(path, "wb") as f:
                await f.write(buf.getvalue())
        except Exception as e:
            log.warning(f"Imagen inválida {path.name}: {e} — descartada")

    # -------------------------------------------------------- run

    async def run(self, specific_urls: list[str] = None):
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()

            if specific_urls:
                albums = []
                for url in specific_urls:
                    if re.search(r'/(categories|collections)/', url):
                        albums.extend(await self.get_albums_from_category(page, url))
                    elif re.search(r'/albums/\d+', url):
                        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                        await human_delay()
                        t = await page.query_selector("span.showalbumheader__gallerytitle")
                        title = (await t.inner_text()).strip() if t else "album"
                        clean = re.sub(r'\?.*$', '', url) + "?uid=1"
                        albums.append({"title": title, "url": clean})
                    else:
                        log.warning(f"URL no reconocida: {url}")
            else:
                albums = await self.get_all_albums(page)

            if not albums:
                log.error("No se encontraron álbums.")
                await browser.close()
                return

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                console=console,
                transient=False,
            ) as progress:
                task = progress.add_task(f"[{LPURPLE}]Descargando álbums...[/]", total=len(albums))
                for album in albums:
                    title_es = translate(album["title"]) if self.translate else album["title"]
                    progress.update(task, description=f"[{LPURPLE}]{sanitize(title_es)[:40]}[/]")
                    await self.download_album(page, album)
                    progress.advance(task)
                    await human_delay(0.3, 0.8)

            await browser.close()
        console.print(f"\n[b {GREEN}]✓ Descarga completa.[/] Imágenes en: [b]{self.output / self.catalog_name}[/]")


# ------------------------------------------------------------------ CLI



def pedir_url() -> str:
    while True:
        console.print(f"\n[{LPURPLE}]URL del catálogo Yupoo[/]")
        console.print(f"[dim]ej: https://nombre.x.yupoo.com[/]")
        url = Prompt.ask(f"[{PURPLE}]>[/]").strip()
        if url.startswith("http") and "yupoo.com" in url:
            return url
        console.print(f"[{RED}]URL no válida, inténtalo de nuevo[/]")


def pedir_opcion() -> str:
    while True:
        console.print(f"\n[b {PURPLE}]¿Qué quieres descargar?[/]")
        console.print(f"  [{LPURPLE}]1.[/] Toda la colección  —  todas las fotos  [{RED}](pesado)[/]")
        console.print(f"  [{LPURPLE}]2.[/] Toda la colección  —  solo portadas")
        console.print(f"  [{LPURPLE}]3.[/] Álbums o categorías concretas  —  todas las fotos")
        console.print(f"  [{LPURPLE}]4.[/] Álbums o categorías concretas  —  solo portadas")
        console.print(f"  [{LPURPLE}]0.[/] [{RED}]Volver[/]")
        op = Prompt.ask(f"[{PURPLE}]Opción[/]", choices=["0","1","2","3","4"]).strip()
        return op


def pedir_urls_especificas() -> list[str] | None:
    console.print(f"\n[{LPURPLE}]Pega las URLs una por una.[/]")
    console.print(f"[dim]Escribe [b]ok[/b] para continuar o [b]0[/b] para volver[/]")
    urls = []
    while True:
        u = Prompt.ask(f"  [{PURPLE}]URL[/]").strip()
        if u.lower() == "0":
            return None
        if u.lower() == "ok":
            if urls:
                return urls
            console.print(f"[{RED}]Añade al menos una URL[/]")
        elif u.startswith("http"):
            urls.append(u)
            console.print(f"  [{GREEN}]✓[/] {u}")
        else:
            console.print(f"  [{RED}]URL no válida[/]")


def pedir_carpeta() -> str:
    default = "./fotos_yupoo"
    console.print(f"\n[{LPURPLE}]Selecciona la carpeta de destino...[/]")
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", True)
        carpeta = filedialog.askdirectory(title="Selecciona carpeta de destino")
        root.destroy()
        if carpeta:
            console.print(f"  [{GREEN}]✓[/] {carpeta}")
            return carpeta
    except Exception:
        pass
    console.print(f"[dim](No se pudo abrir el selector, escribe la ruta)[/]")
    carpeta = Prompt.ask(f"[{PURPLE}]Carpeta[/]", default=default).strip()
    return carpeta or default


def menu_interactivo():
    console.print(Panel(
        f"[b {GREEN}]YUPOO DOWNLOADER[/]",
        subtitle=f"[dim]Descargador de imágenes Yupoo[/]",
        border_style=PURPLE,
        padding=(0, 4),
    ))

    base_url = pedir_url()

    while True:
        opcion = pedir_opcion()
        if opcion == "0":
            base_url = pedir_url()
            continue

        specific_urls = None
        covers_only = opcion in ("2", "4")

        if opcion in ("3", "4"):
            specific_urls = pedir_urls_especificas()
            if specific_urls is None:
                continue  # volver al menú de opciones

        carpeta = pedir_carpeta()
        sin_trad = not Confirm.ask(f"\n[{LPURPLE}]¿Traducir nombres al español?[/]", default=True)
        visible  = Confirm.ask(f"[{LPURPLE}]¿Mostrar navegador?[/]", default=False)

        console.print(f"\n[b {GREEN}]Iniciando descarga...[/]\n")
        return base_url, specific_urls, covers_only, sin_trad, carpeta, not visible


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", nargs="?")
    parser.add_argument("--urls", nargs="+")
    parser.add_argument("--carpeta", default="./fotos_yupoo")
    parser.add_argument("--solo-portadas", action="store_true")
    parser.add_argument("--sin-traduccion", action="store_true")
    parser.add_argument("--visible", action="store_true", help="Mostrar navegador (no headless)")
    args = parser.parse_args()

    if args.url:
        base_url, specific_urls, covers_only = args.url, args.urls or None, args.solo_portadas
        no_translate, carpeta, headless = args.sin_traduccion, args.carpeta, not args.visible
    else:
        base_url, specific_urls, covers_only, no_translate, carpeta, headless = menu_interactivo()

    dl = YupooPlaywright(
        base_url=base_url,
        output=Path(carpeta),
        covers_only=covers_only,
        no_translate=no_translate,
        headless=headless,
    )
    asyncio.run(dl.run(specific_urls=specific_urls))


if __name__ == "__main__":
    main()
