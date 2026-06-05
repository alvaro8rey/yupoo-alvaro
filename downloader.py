"""
Yupoo Image Downloader - rewrite moderno y multiplataforma
Uso: python downloader.py <url_catalogo> [--carpeta ./fotos] [--solo-portadas] [--sin-traduccion]
"""

import asyncio
import aiohttp
import aiofiles
import os
import re
import ssl
import certifi
import argparse
import logging
from pathlib import Path
from io import BytesIO

from bs4 import BeautifulSoup
from PIL import Image, ImageFile
from deep_translator import GoogleTranslator

ImageFile.LOAD_TRUNCATED_IMAGES = True

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("yupoo")

SSL_CTX = ssl.create_default_context(cafile=certifi.where())
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://yupoo.com/",
}


def sanitize(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name.strip("_ ")[:120] or "sin_titulo"


def translate(text: str) -> str:
    try:
        result = GoogleTranslator(source="auto", target="es").translate(text)
        return result if result else text
    except Exception:
        return text


class YupooDownloader:
    def __init__(self, base_url: str, output: Path, covers_only: bool = False, no_translate: bool = False):
        self.base_url = base_url.rstrip("/")
        self.output = output
        self.covers_only = covers_only
        self.translate = not no_translate
        self.sem = asyncio.Semaphore(3)
        self.session: aiohttp.ClientSession = None
        self.catalog_name = ""

    # ------------------------------------------------------------------ HTTP

    async def get(self, url: str, binary: bool = False, retries: int = 5):
        for attempt in range(retries):
            try:
                async with self.sem:
                    async with self.session.get(
                        url, headers=HEADERS, ssl=SSL_CTX,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as resp:
                        if resp.status == 200:
                            return await resp.read() if binary else await resp.text()
                        if resp.status in (429, 567, 503):
                            wait = 10 * (attempt + 1)
                            log.warning(f"Rate limit (HTTP {resp.status}), esperando {wait}s -> {url}")
                            await asyncio.sleep(wait)
                        else:
                            log.warning(f"HTTP {resp.status} -> {url}")
            except Exception as e:
                log.warning(f"Intento {attempt+1}/{retries} fallido ({url}): {e}")
            await asyncio.sleep(2 ** attempt)
        log.error(f"No se pudo descargar: {url}")
        return None

    # ------------------------------------------------------------------ PAGES

    async def get_page_count(self, url: str) -> int:
        html = await self.get(url)
        if not html:
            return 0
        soup = BeautifulSoup(html, "lxml")
        inp = soup.select_one('form.pagination__jumpwrap input[name="page"]')
        return int(inp["max"]) if inp else 1

    # ------------------------------------------------------------------ CATALOG NAME

    def extract_catalog_name(self, url: str) -> str:
        m = re.search(r'https?://([^.]+)\.x\.yupoo\.com', url)
        if m:
            return m.group(1)
        m = re.search(r'https?://([^.]+)\.yupoo\.com', url)
        return m.group(1) if m else "catalogo"

    # ------------------------------------------------------------------ ALBUMS

    async def get_albums_from_page(self, page_url: str) -> list[dict]:
        html = await self.get(page_url)
        if not html:
            return []
        soup = BeautifulSoup(html, "lxml")
        albums = []
        for a in soup.select("a.album__main"):
            href = a.get("href", "")
            title = a.get("title") or a.get_text(strip=True) or "sin_titulo"
            # construir URL completa del album
            if href.startswith("http"):
                album_url = href
            else:
                album_url = f"https://{self.catalog_name}.x.yupoo.com{href}"
            # quitar parámetros excepto uid=1
            album_url = re.sub(r'\?.*$', '', album_url) + "?uid=1"
            albums.append({"title": title, "url": album_url})
        return albums

    async def get_all_albums(self) -> list[dict]:
        gallery_url = f"{self.base_url}/albums?tab=gallery&page=1"
        total = await self.get_page_count(gallery_url)
        log.info(f"Páginas del catálogo: {total}")

        tasks = [
            self.get_albums_from_page(f"{self.base_url}/albums?tab=gallery&page={p}")
            for p in range(1, total + 1)
        ]
        results = await asyncio.gather(*tasks)
        albums = [a for page in results for a in page]
        log.info(f"Albums encontrados: {len(albums)}")
        return albums

    # ------------------------------------------------------------------ IMAGES

    async def get_images_from_album(self, album_url: str) -> list[str]:
        html = await self.get(album_url)
        if not html:
            return []
        soup = BeautifulSoup(html, "lxml")
        imgs = []
        if self.covers_only:
            cover = soup.select_one(".showalbumheader__gallerycover img")
            if cover:
                src = cover.get("src") or cover.get("data-origin-src") or ""
                if src:
                    imgs.append("https:" + src if src.startswith("//") else src)
            return imgs
        for div in soup.select("div.showalbum__children"):
            wrap = div.select_one(".image__imagewrap")
            if wrap and wrap.get("data-type") == "video":
                continue
            img = div.select_one("img")
            if not img:
                continue
            src = img.get("data-origin-src") or img.get("src") or ""
            if src:
                imgs.append("https:" + src if src.startswith("//") else src)
        return imgs

    # ------------------------------------------------------------------ SAVE

    async def save_image(self, img_bytes: bytes, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            img = Image.open(BytesIO(img_bytes)).convert("RGB")
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=95)
            async with aiofiles.open(path, "wb") as f:
                await f.write(buf.getvalue())
        except Exception as e:
            log.warning(f"Error guardando imagen {path.name}: {e}")
            async with aiofiles.open(path, "wb") as f:
                await f.write(img_bytes)

    # ------------------------------------------------------------------ MAIN

    async def download_album(self, album: dict, album_dir: Path):
        if album_dir.exists() and any(album_dir.iterdir()):
            log.info(f"  [skip] {album_dir.name} ya existe")
            return
        img_urls = await self.get_images_from_album(album["url"])
        if not img_urls:
            log.warning(f"  Sin imágenes: {album['title']}")
            return
        log.info(f"  {album['title']} -> {len(img_urls)} imágenes")
        tasks = []
        for url in img_urls:
            filename = re.findall(r'/([^/]+)$', url)[0].split("?")[0]
            stem = Path(filename).stem
            path = album_dir / f"{stem}.jpg"
            tasks.append(self.download_one(url, path))
        await asyncio.gather(*tasks)

    async def download_one(self, url: str, path: Path):
        if path.exists():
            return
        data = await self.get(url, binary=True)
        if data:
            await self.save_image(data, path)

    async def get_albums_from_category(self, cat_url: str) -> list[dict]:
        """Obtiene álbums de una URL de categoría o colección."""
        # normalizar URL quitando parámetros
        base = re.sub(r'\?.*$', '', cat_url.rstrip("/"))
        total = await self.get_page_count(f"{base}?page=1")
        log.info(f"  Páginas en categoría: {total}")
        tasks = [
            self.get_albums_from_page(f"{base}?page={p}")
            for p in range(1, total + 1)
        ]
        results = await asyncio.gather(*tasks)
        return [a for page in results for a in page]

    def is_album_url(self, url: str) -> bool:
        return bool(re.search(r'/albums/\d+', url))

    def is_category_url(self, url: str) -> bool:
        return bool(re.search(r'/(categories|collections)/', url))

    async def run(self, specific_urls: list[str] = None):
        self.catalog_name = self.extract_catalog_name(self.base_url)
        log.info(f"Catálogo: {self.catalog_name}")

        connector = aiohttp.TCPConnector(limit=5, ssl=SSL_CTX)
        async with aiohttp.ClientSession(connector=connector) as session:
            self.session = session

            if specific_urls:
                albums = []
                for url in specific_urls:
                    if self.is_album_url(url):
                        # es un álbum directo: obtener su título del HTML
                        html = await self.get(url)
                        if html:
                            soup = BeautifulSoup(html, "lxml")
                            title_tag = soup.select_one("span.showalbumheader__gallerytitle")
                            title = title_tag.text.strip() if title_tag else "album"
                            clean_url = re.sub(r'\?.*$', '', url) + "?uid=1"
                            albums.append({"title": title, "url": clean_url})
                    elif self.is_category_url(url):
                        cat_albums = await self.get_albums_from_category(url)
                        albums.extend(cat_albums)
                    else:
                        log.warning(f"URL no reconocida, ignorando: {url}")
            else:
                albums = await self.get_all_albums()

            if not albums:
                log.error("No se encontraron álbums. Verifica la URL.")
                return

            log.info(f"Total álbums a descargar: {len(albums)}")
            for i, album in enumerate(albums, 1):
                title_raw = album["title"]
                title_es = translate(title_raw) if self.translate else title_raw
                folder_name = sanitize(title_es)
                album_dir = self.output / self.catalog_name / folder_name
                log.info(f"[{i}/{len(albums)}] {title_raw!r} -> {folder_name!r}")
                await self.download_album(album, album_dir)
                await asyncio.sleep(3)

        log.info(f"Descarga completa. Imágenes en: {self.output / self.catalog_name}")


# ---------------------------------------------------------------------- CLI

def menu_interactivo() -> tuple[str, list[str] | None, bool, bool, str]:
    """Menú simple en terminal, devuelve (base_url, urls_especificas, solo_portadas, sin_traduccion, carpeta)."""
    print("\n===== YUPOO DOWNLOADER =====")
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

    return base_url, specific_urls, covers_only, sin_trad, carpeta


def main():
    parser = argparse.ArgumentParser(description="Descargador de imágenes Yupoo")
    parser.add_argument("url", nargs="?", help="URL base del catálogo (omitir para menú interactivo)")
    parser.add_argument("--urls", nargs="+", help="URLs concretas de álbums o categorías")
    parser.add_argument("--carpeta", default="./fotos_yupoo", help="Carpeta de destino")
    parser.add_argument("--solo-portadas", action="store_true")
    parser.add_argument("--sin-traduccion", action="store_true")
    args = parser.parse_args()

    if args.url:
        base_url = args.url
        specific_urls = args.urls or None
        covers_only = args.solo_portadas
        no_translate = args.sin_traduccion
        carpeta = args.carpeta
    else:
        base_url, specific_urls, covers_only, no_translate, carpeta = menu_interactivo()

    downloader = YupooDownloader(
        base_url=base_url,
        output=Path(carpeta),
        covers_only=covers_only,
        no_translate=no_translate,
    )
    asyncio.run(downloader.run(specific_urls=specific_urls))


if __name__ == "__main__":
    main()
