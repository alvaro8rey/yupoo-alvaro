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

ImageFile.LOAD_TRUNCATED_IMAGES = True
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("yupoo")


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

        log.info(f"  Álbum: {title_raw!r} -> {folder!r}")
        album_dir.mkdir(parents=True, exist_ok=True)

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

        captured: dict[str, bytes] = {}

        async def capture_response(response):
            url = response.url
            if "photo.yupoo.com" in url and url.endswith((".jpeg", ".jpg", ".png", ".webp")):
                try:
                    body = await response.body()
                    if body:
                        captured[url] = body
                except Exception:
                    pass

        page.on("response", capture_response)
        try:
            await page.goto(album["url"], wait_until="domcontentloaded", timeout=20000)
        except Exception as e:
            log.warning(f"  Timeout cargando álbum, continuando: {e}")
            page.remove_listener("response", capture_response)
            return
        await human_delay(0.2, 0.5)

        # scroll progresivo para forzar lazy loading, máximo 30 iteraciones
        prev_height = 0
        for _ in range(30):
            await page.evaluate("window.scrollBy(0, 800)")
            await asyncio.sleep(0.15)
            height = await page.evaluate("document.body.scrollHeight")
            scroll_y = await page.evaluate("window.scrollY + window.innerHeight")
            if scroll_y >= height and height == prev_height:
                break
            prev_height = height
        await asyncio.sleep(0.5)

        # obtener lista de URLs en orden desde el DOM
        if self.covers_only:
            cover = await page.query_selector(".showalbumheader__gallerycover img")
            src = await cover.get_attribute("src") if cover else ""
            ordered_urls = ["https:" + src] if src and src.startswith("//") else ([src] if src else [])
        else:
            ordered_urls = []
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
                    ordered_urls.append("https:" + src if src.startswith("//") else src)

        # esperar a que se capturen las imágenes visibles
        await asyncio.sleep(1)
        page.remove_listener("response", capture_response)

        if not ordered_urls:
            log.warning(f"  Sin imágenes: {title_raw!r}")
            return

        log.info(f"  {len(ordered_urls)} imágenes")
        saved = 0
        for i, url in enumerate(ordered_urls, 1):
            filename = re.findall(r'/([^/?]+)', url)[-1]
            path = album_dir / f"{Path(filename).stem}.jpg"
            if path.exists():
                saved += 1
                continue
            body = captured.get(url)
            if body:
                await self.save_image(body, path)
                log.info(f"    [{i}/{len(ordered_urls)}] {path.name}")
                saved += 1
            else:
                log.warning(f"    [{i}/{len(ordered_urls)}] no capturada: {url}")

        if saved == 0:
            # si no se capturó nada elimina la carpeta vacía
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
            log.warning(f"Error procesando {path.name}: {e} — guardando raw")
            async with aiofiles.open(path, "wb") as f:
                await f.write(img_bytes)

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

            for i, album in enumerate(albums, 1):
                log.info(f"[{i}/{len(albums)}]")
                await self.download_album(page, album)
                await human_delay(0.3, 0.8)

            await browser.close()
        log.info(f"Hecho. Imágenes en: {self.output / self.catalog_name}")


# ------------------------------------------------------------------ CLI

def menu_interactivo():
    print("\n===== YUPOO DOWNLOADER (Playwright) =====")
    base_url = input("URL del catálogo (ej: https://nombre.x.yupoo.com): ").strip()
    print()
    print("¿Qué quieres descargar?")
    print("  1. Toda la colección — todas las fotos")
    print("  2. Toda la colección — solo portadas")
    print("  3. Álbums o categorías concretas — todas las fotos")
    print("  4. Álbums o categorías concretas — solo portadas")
    opcion = input("Opción (1-4): ").strip()

    specific_urls = None
    covers_only = opcion in ("2", "4")

    if opcion in ("3", "4"):
        print("Pega las URLs una por una. Escribe 'ok' cuando termines:")
        specific_urls = []
        while True:
            u = input("  URL: ").strip()
            if u.lower() == "ok":
                break
            if u:
                specific_urls.append(u)

    carpeta = input("\nCarpeta de destino [./fotos_yupoo]: ").strip() or "./fotos_yupoo"
    sin_trad = input("¿Desactivar traducción al español? (s/N): ").strip().lower() == "s"
    visible = input("¿Mostrar navegador? (s/N): ").strip().lower() == "s"

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
