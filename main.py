import cloudscraper
import time
import random
import requests
import asyncio
import aiohttp

event_ids = ["302aface","393789cb"]

headers_template = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7,ja;q=0.6",
    "Priority": "u=1, i",
    "Sec-CH-UA": "\"Not)A;Brand\";v=\"8\", \"Chromium\";v=\"138\", \"Google Chrome\";v=\"138\"",
    "Sec-CH-UA-Arch": "\"x86\"",
    "Sec-CH-UA-Bitness": "\"64\"",
    "Sec-CH-UA-Full-Version": "\"138.0.7204.50\"",
    "Sec-CH-UA-Full-Version-List": "\"Not)A;Brand\";v=\"8.0.0.0\", \"Chromium\";v=\"138.0.7204.50\", \"Google Chrome\";v=\"138.0.7204.50\"",
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Model": "\"\"",
    "Sec-CH-UA-Platform": "\"Windows\"",
    "Sec-CH-UA-Platform-Version": "\"15.0.0\"",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest"
}

webhook_urls = [
    "https://discord.com/api/webhooks/1371436288330436618/_WsfwLwakJLC1vW7g01iZcDzPTiSnxhR4ijRv0gtsxv4Yo27J49Dx8zubkZqb_m-GW00"
]

scraper = cloudscraper.create_scraper()

def send_discord(title, event_id, sections):
    asyncio.run(send_discord_async(title, event_id, sections))

def fetch_data(event_id):
    base_url = f"https://kktix.com/g/events/{event_id}/base_info"
    stock_url = f"https://kktix.com/g/events/{event_id}/register_info"
    headers = headers_template.copy()
    headers["Referer"] = f"https://kktix.com/events/{event_id}/registrations/new"
    base_info = scraper.get(base_url, headers=headers).json()
    stock_info = scraper.get(stock_url, headers=headers).json()
    name = base_info.get("eventData", {}).get("event", {}).get("name", "")
    title = name.split("presented by")[0].strip() if "presented by" in name else name.strip()
    return base_info, stock_info, title

def get_stock_sections(base_info, stock_info):
    stock_sections = {}
    if "sections" in stock_info and stock_info["sections"]:
        for sec in stock_info["sections"]:
            stock_sections[sec["id"]] = sec.get("stock_level", "未知")

    arena_sections = {}
    try:
        arena_sections = base_info["eventData"]["event"]["arena"]["sections"]
    except (KeyError, TypeError):
        arena_sections = {}

    combined = {}
    for sec_id, sec_info in arena_sections.items():
        label = sec_info.get("label", f"區塊{sec_id}")
        if "包廂" in label or "身障" in label or "殘障" in label or "輪椅" in label:
            continue
        stock_level = stock_sections.get(int(sec_id), "SOLD_OUT")
        combined[sec_id] = (label, stock_level)
    return combined

def print_sections(title, event_id, sections):
    filtered = {sec_id: info for sec_id, info in sections.items() if info[1] != "SOLD_OUT"}
    if not filtered:
        return False
    print(f"🏟️ {title} 區塊與庫存狀態：")
    print(f"🔗 https://kktix.com/events/{event_id}/registrations/new")
    print(f"{'區塊名稱':<15} {'庫存狀態'}")
    for sec_id, (label, stock_level) in filtered.items():
        print(f"{label:<15} {stock_level}")
    print("-" * 30)
    return True

async def send_to_webhook(session, url, content):
    try:
        async with session.post(url, json={"content": content}, timeout=10) as resp:
            if resp.status != 204:
                text = await resp.text()
                print(f"⚠️ Discord 發送失敗（{url}）狀態碼：{resp.status}，內容：{text}")
    except Exception as e:
        print(f"⚠️ Discord 發送失敗（{url}）：{e}")

async def send_discord_async(title, event_id, sections):
    content_lines = [
        f"🎫 **{title}**",
        f"<https://kktix.com/events/{event_id}/registrations/new>",
        "",
        "**🎯 可售區塊更新：**"
    ]
    for _, (label, stock) in sections.items():
        if stock != "SOLD_OUT":
            content_lines.append(f"- {label}：清票中")
    if len(content_lines) <= 4:
        return

    content = "\n".join(content_lines)

    async with aiohttp.ClientSession() as session:
        tasks = [send_to_webhook(session, url, content) for url in webhook_urls]
        await asyncio.gather(*tasks)

last_stock_by_event = {event_id: {} for event_id in event_ids}

while True:
    try:
        for event_id in event_ids:
            base_info, stock_info, title = fetch_data(event_id)
            current_sections = get_stock_sections(base_info, stock_info)
            has_available = any(stock != "SOLD_OUT" for _, stock in current_sections.values())
            if has_available and current_sections != last_stock_by_event[event_id]:
                did_print = print_sections(title, event_id, current_sections)
                if did_print:
                    send_discord(title, event_id, current_sections)
                    last_stock_by_event[event_id] = current_sections
            time.sleep(0.2)
        time.sleep(random.uniform(1, 1.3))
    except Exception as e:
        print(f"錯誤：{e}，0.5秒後重試")
        time.sleep(0.5)
