import asyncio
import html
import json
import logging
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

BASE_URL = "https://asvezestemlaurodefreitas.com.br"
CATALOG_URL = f"{BASE_URL}/produtos/"
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "120"))
MAX_LOAD_MORE_CLICKS = int(os.getenv("MAX_LOAD_MORE_CLICKS", "40"))
STATE_FILE = Path(os.getenv("STATE_FILE", "data/state.json"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("product-monitor")

ACCESSORY_TERMS = (
    "controle", "controller", "headset", "fone", "carregador", "cabo",
    "base carregadora", "suporte", "capa", "case", "pelicula", "skin",
    "volante", "adaptador", "bateria", "dock",
    "camera", "bolsa", "mochila", "adesivo", "protetor",
    "peca de reposicao",
)

SOLD_OUT_TERMS = (
    "produto esgotado", "produto indisponivel", "esgotado", "sem estoque",
    "nao temos mais estoque",
    "avise-me quando chegar", "nao temos estoque", "indisponivel no momento",
)

def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", value.lower()).strip()

def is_target_console(title: str) -> bool:
    name = normalize(title)

    # Excluir o PS5 Pro mesmo se outras palavras-chave estiverem presentes.
    if re.search(r"\bps[\s-]*5[\s-]*pro\b|\bplay[\s-]*station[\s-]*5[\s-]*pro\b|\bplaystation[\s-]*5[\s-]*pro\b|\bplay[\s-]*5[\s-]*pro\b", name):
        return False

    has_console_name = bool(
        re.search(r"\bps\s*5\b", name)
        or re.search(r"\bplay\s*station\s*5\b", name)
        or re.search(r"\bplay\s*5\b", name)
        or re.search(r"\bplaystation5\b", name)
        or re.search(r"\bsony\s+(?:playstation|ps)\s*5?\b", name)
    )
    if not has_console_name:
        return False

    return not any(term in name for term in ACCESSORY_TERMS)

def extract_price(text: str) -> str:
    matches = re.findall(r"R\$\s*[\d.]+,\d{2}", text or "")
    return matches[0] if matches else "Preço não identificado"

def load_state() -> dict:
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Falha ao ler estado salvo; iniciando estado vazio.")
    return {}

def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = STATE_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(STATE_FILE)

def send_telegram_message(message: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError("Configure TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID antes de iniciar o monitor.")
    response = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=20,
    )
    response.raise_for_status()

async def collect_catalog_products(page) -> dict:
    await page.goto(CATALOG_URL, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(1500)

    seen = {}
    for _ in range(MAX_LOAD_MORE_CLICKS + 1):
        items = await page.locator('a[href*="/produtos/"]').evaluate_all(
            """els => els.map(a => ({
                href: a.href,
                title: (a.innerText || a.getAttribute('title') || '').trim()
            }))"""
        )
        for item in items:
            href = (item.get("href") or "").split("#")[0]
            title = re.sub(r"\s+", " ", item.get("title") or "").strip()
            path = urlparse(href).path.rstrip("/")
            if href and title and path.startswith("/produtos/") and path != "/produtos":
                seen[href] = title

        more = page.get_by_text("Mostrar mais produtos", exact=True)
        try:
            if await more.count() == 0 or not await more.first.is_visible():
                break
            before = len(seen)
            await more.first.click(timeout=7000)
            await page.wait_for_timeout(1200)
            if len(seen) == before and _ > 2:
                # Continua por mais uma leitura para evitar parar durante animação.
                await page.wait_for_timeout(1000)
        except PlaywrightTimeoutError:
            logger.info("Botão de carregamento adicional não respondeu; encerrando paginação.")
            break
        except Exception as exc:
            logger.info("Não foi possível carregar mais produtos: %s", exc)
            break

    # Captura os links após o último carregamento.
    items = await page.locator('a[href*="/produtos/"]').evaluate_all(
        """els => els.map(a => ({
            href: a.href,
            title: (a.innerText || a.getAttribute('title') || '').trim()
        }))"""
    )
    for item in items:
        href = (item.get("href") or "").split("#")[0]
        title = re.sub(r"\s+", " ", item.get("title") or "").strip()
        path = urlparse(href).path.rstrip("/")
        if href and title and path.startswith("/produtos/") and path != "/produtos":
            seen[href] = title
    return seen

async def inspect_product(browser, url: str, catalog_title: str) -> dict:
    page = await browser.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(500)

        try:
            title = (await page.locator("h1").first.inner_text(timeout=5000)).strip()
        except Exception:
            title = catalog_title
        title = re.sub(r"\s+", " ", title) or catalog_title

        body = await page.locator("body").inner_text(timeout=10000)
        normalized = normalize(body)
        sold_out = any(term in normalized for term in SOLD_OUT_TERMS)
        last_piece = "atencao, ultima peca" in normalized

        buy_available = False
        for role in ("button", "link"):
            locator = page.get_by_role(role, name=re.compile(r"comprar", re.I))
            try:
                for i in range(min(await locator.count(), 5)):
                    element = locator.nth(i)
                    if await element.is_visible() and await element.is_enabled():
                        buy_available = True
                        break
            except Exception:
                continue
            if buy_available:
                break

        in_stock = not sold_out and (last_piece or buy_available)
        return {
            "title": title,
            "price": extract_price(body),
            "in_stock": in_stock,
            "evidence": "aviso de última peça" if last_piece else (
                "botão Comprar habilitado" if in_stock else "estoque não confirmado"
            ),
        }
    finally:
        await page.close()

async def monitor_cycle(browser, state: dict) -> None:
    page = await browser.new_page()
    try:
        catalog = await collect_catalog_products(page)
    finally:
        await page.close()

    targets = {url: title for url, title in catalog.items() if is_target_console(title)}
    logger.info("Catálogo: %d links de produto; %d candidatos PS5 (exceto Pro).",
                len(catalog), len(targets))

    for url, catalog_title in targets.items():
        try:
            product = await inspect_product(browser, url, catalog_title)
            previous = bool(state.get(url, {}).get("in_stock", False))
            if product["in_stock"] and not previous:
                message = (
                    "🎮 <b>PS5 disponível na Às Vezes Tem!</b>\\n\\n"
                    f"<b>Produto:</b> {html.escape(product['title'])}\\n"
                    f"<b>Preço:</b> {html.escape(product['price'])}\\n"
                    f"<b>Indício:</b> {html.escape(product['evidence'])}\\n\\n"
                    f'<a href="{html.escape(url, quote=True)}">Ver produto na loja</a>'
                )
                # Só registra como alertado depois que o Telegram confirmar o envio.
                send_telegram_message(message)
                logger.info("Novo alerta: %s", product["title"])

            state[url] = {
                "title": product["title"],
                "in_stock": product["in_stock"],
                "last_checked": datetime.now(timezone.utc).isoformat(),
            }
            save_state(state)

            if not (product["in_stock"] and not previous):
                logger.info("%s | disponível=%s | %s",
                            product["title"], product["in_stock"], product["evidence"])
        except Exception:
            logger.exception("Erro ao verificar %s", url)

async def main():
    if CHECK_INTERVAL_SECONDS < 60:
        logger.warning("Intervalo inferior a 60s; considere respeitar a carga do site.")
    state = load_state()
    logger.info("Monitor iniciado. Intervalo: %d segundos.", CHECK_INTERVAL_SECONDS)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            while True:
                try:
                    await monitor_cycle(browser, state)
                except Exception:
                    logger.exception("Falha no ciclo; o monitor tentará novamente.")
                await asyncio.sleep(CHECK_INTERVAL_SECONDS)
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
