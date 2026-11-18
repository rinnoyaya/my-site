"""把 content/ 裡「一筆一個檔案」的內容，合併成網站讀取的 data/*.json，
輸出到 _site/ 資料夾給 GitHub Pages 發佈。由 .github/workflows/deploy.yml 自動執行。"""
import glob, html, json, os, re, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "_site")
SKIP = {".git", ".github", "_site", "content", "scripts", ".pages.yml", "README.md", "r2-worker.js"}

# 集合資料夾 → 網站讀取的檔名，以及排序方式
COLLECTIONS = {
    "series": ("series.json", lambda x, f: (num(x.get("order")), str(x.get("title") or "")), False),
    "chapters": ("chapters.json", lambda x, f: (num(x.get("order")), str(x.get("date") or "")), False),
    "side-stories": ("side-stories.json", lambda x, f: str(x.get("date") or ""), False),
    "characters": ("characters.json", lambda x, f: (num(x.get("order")), str(x.get("name") or "")), False),
    "commissions": ("commissions.json", lambda x, f: str(x.get("date") or ""), False),
    "tools": ("tools.json", lambda x, f: (num(x.get("order")), str(x.get("date") or "")), False),
    "notes": ("notes.json", lambda x, f: str(x.get("date") or ""), False),
    "glossary": ("glossary.json", lambda x, f: (num(x.get("order")), str(x.get("term") or "")), False),
    # 網站歷程：新的在上面；同一天的話，後新增的（檔名較大）在上面
    "history": ("history.json", lambda x, f: (str(x.get("date") or ""), f), True),
}

def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 1e9  # 沒填排序的放最後

def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    for name in os.listdir(ROOT):
        if name in SKIP:
            continue
        src = os.path.join(ROOT, name)
        dst = os.path.join(OUT, name)
        (shutil.copytree if os.path.isdir(src) else shutil.copy2)(src, dst)
    os.makedirs(os.path.join(OUT, "data"), exist_ok=True)

    warnings = 0
    for folder, (outname, key, reverse) in COLLECTIONS.items():
        path = os.path.join(ROOT, "content", folder)
        if not os.path.isdir(path):
            out_file = os.path.join(OUT, "data", outname)
            if os.path.exists(out_file):
                print(f"[略過] content/{folder} 不存在，沿用 data/{outname}")
            else:
                # 資料夾還沒建立（例如還沒新增過任何名詞）：先放一個空清單，網站才不會出現讀取失敗
                with open(out_file, "w", encoding="utf-8") as fh:
                    fh.write("[]")
                print(f"[略過] content/{folder} 還沒有內容，先產生空的 data/{outname}")
            continue
        items = []
        for f in sorted(glob.glob(os.path.join(path, "*.json"))):
            try:
                with open(f, encoding="utf-8") as fh:
                    text = fh.read()
                if not text.strip():
                    continue
                obj = json.loads(text)
                if isinstance(obj, dict):
                    obj["_file"] = os.path.splitext(os.path.basename(f))[0]  # 分享頁網址用
                    items.append((obj, os.path.basename(f)))
                else:
                    print(f"[警告] {f} 不是單一物件，已略過"); warnings += 1
            except Exception as e:
                print(f"[警告] {f} 讀取失敗，已略過：{e}"); warnings += 1
        items.sort(key=lambda p: key(p[0], p[1]), reverse=reverse)
        items = [p[0] for p in items]
        with open(os.path.join(OUT, "data", outname), "w", encoding="utf-8") as fh:
            json.dump(items, fh, ensure_ascii=False, indent=1)
        print(f"[完成] content/{folder} → data/{outname}（{len(items)} 筆）")
    warnings += build_share_pages()
    inject_home_meta()
    write_version()
    print(f"建置完成，警告 {warnings} 個")

# ---------------- 分享頁 ----------------
# 每篇內容產生 /s/類型/代號/index.html：給 LINE、Discord、Facebook 讀取標題、摘要、封面，
# 一般訪客打開會立刻跳到網站上的那一篇。
SHARE_TYPES = [
    # (資料檔, 分享頁類型, 網站上的位置前綴, 代號欄位, 標題欄位, 摘要欄位, 圖片欄位)
    ("chapters.json", "read", "read-", "id", "title", "body", "image"),
    ("side-stories.json", "side", "side-", "id", "title", "body", "image"),
    ("notes.json", "note", "note-", "id", "title", "excerpt", None),
    ("characters.json", "char", "char-", "name", "name", "summary", "avatar"),
    ("tools.json", "tool", "tool-", "id", "title", "summary", "image"),
    ("commissions.json", "comm", "comm-", "_file", "title", "description", "image"),
]
SAFE_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

def site_origin():
    cname = os.path.join(ROOT, "CNAME")
    if os.path.isfile(cname):
        d = open(cname, encoding="utf-8").read().strip()
        if d:
            return "https://" + d
    return "https://obsidianfirelight.com"

def plain(text, limit=110):
    t = str(text or "")
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)                 # 圖片
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)             # 連結
    t = re.sub(r"\{[^|{}\n]{1,40}\|([^{}]+?)\}", r"\1", t)       # {樣式|文字}
    t = re.sub(r"\*\*|~~|==|\*", "", t)
    t = re.sub(r"^\s*(##|>|-)\s*", "", t, flags=re.M)
    t = re.sub(r"^-{3,}$", "", t, flags=re.M)
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= limit else t[:limit].rstrip() + "…"

def img_of(x, f):
    return str((x.get(f + "Url") or x.get(f) or "")).strip() if f else ""

def absolute(url, origin):
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        return url
    return origin + "/" + url.lstrip("/")

def build_share_pages():
    origin = site_origin()
    try:
        site = json.load(open(os.path.join(OUT, "data", "site.json"), encoding="utf-8"))
    except Exception:
        site = {}
    site_name = site.get("siteName") or "黑曜石堡壘"
    default_img = absolute(img_of(site, "heroImage"), origin) or origin + "/icon.png"
    count = warnings = 0
    for datafile, kind, hash_prefix, id_field, title_field, desc_field, img_field in SHARE_TYPES:
        path = os.path.join(OUT, "data", datafile)
        if not os.path.isfile(path):
            continue
        try:
            items = json.load(open(path, encoding="utf-8")) or []
        except Exception:
            continue
        for x in items:
            if not isinstance(x, dict):
                continue
            slug = x.get("_file") if kind in ("char", "comm") else (x.get(id_field) or x.get("_file"))
            slug = str(slug or "").strip()
            if not SAFE_SLUG.match(slug):
                print(f"[警告] 分享頁略過：{x.get(title_field)}（網址代號只能用英文、數字、-、_）"); warnings += 1
                continue
            key = slug if kind == "comm" else str(x.get(id_field) or x.get("title") or "")
            target = f"/#{hash_prefix}{key}"  # 相對網址：在任何網址下都能正確跳轉
            title = str(x.get(title_field) or site_name)
            if kind == "read" and x.get("series"):
                title = f"{x['series']}・{title}"
            if kind == "comm":
                title = f"委託圖〈{title}〉"
            adult = x.get("adult") in (True, "true")
            if adult:
                desc, image = "成人內容（18+），未滿 18 歲請勿閱覽。", origin + "/icon.png"
            else:
                desc = plain(x.get(desc_field)) or plain(x.get("body")) or (f"繪師：{x.get('artist')}" if kind == "comm" and x.get("artist") else "") or site.get("heroText") or site_name
                image = absolute(img_of(x, img_field), origin)
                if not image and kind == "tool":  # 小工具沒封面就用第一張教學圖卡
                    first = [c for c in (x.get("cards") or []) if isinstance(c, dict) and img_of(c, "image")]
                    lines = [l.split("|")[0].split("｜")[0].strip() for l in str(x.get("cardUrls") or "").splitlines() if l.strip()]
                    image = absolute(img_of(first[0], "image") if first else (lines[0] if lines else ""), origin)
                image = image or default_img
            url = f"{origin}/s/{kind}/{slug}/"
            e = lambda v: html.escape(str(v), quote=True)
            page = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}｜{e(site_name)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(url)}">
<meta property="og:site_name" content="{e(site_name)}">
<meta property="og:type" content="article">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(url)}">
<meta property="og:image" content="{e(image)}">
<meta name="twitter:card" content="{'summary' if adult else 'summary_large_image'}">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="{e(image)}">
<link rel="icon" type="image/png" href="/favicon.png?v=2">
<meta http-equiv="refresh" content="0; url={e(target)}">
<script>location.replace({json.dumps(target)});</script>
<style>body{{font-family:sans-serif;background:#11141d;color:#e5e8f1;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}}a{{color:#93a3ff}}</style>
</head>
<body><p>正在前往《{e(title)}》… <a href="{e(target)}">沒有自動跳轉請點這裡</a></p></body>
</html>
"""
            out_dir = os.path.join(OUT, "s", kind, slug)
            os.makedirs(out_dir, exist_ok=True)
            with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as fh:
                fh.write(page)
            count += 1
    print(f"[完成] 產生分享頁 {count} 個")
    return warnings

# 首頁的標題和社群預覽資訊（原本固定是「我的網站」）
def write_version():
    """把 index.html 裡的版本號寫成 data/version.json，網頁發現自己是舊版時會自動更新"""
    try:
        m = re.search(r'const SITE_VERSION="([^"]+)"', open(os.path.join(OUT, "index.html"), encoding="utf-8").read())
    except OSError:
        return
    if m:
        with open(os.path.join(OUT, "data", "version.json"), "w", encoding="utf-8") as fh:
            json.dump({"version": m.group(1)}, fh, ensure_ascii=False)
        print(f"[完成] 版本號 {m.group(1)}")

def inject_home_meta():
    path = os.path.join(OUT, "index.html")
    try:
        site = json.load(open(os.path.join(OUT, "data", "site.json"), encoding="utf-8"))
        page = open(path, encoding="utf-8").read()
    except Exception:
        return
    origin = site_origin()
    e = lambda v: html.escape(str(v), quote=True)
    name = site.get("siteName") or "我的網站"
    desc = plain(site.get("heroText") or site.get("heroEyebrow") or "", 150) or name
    image = absolute(img_of(site, "heroImage"), origin) or origin + "/icon.png"
    meta = f"""<title>{e(name)}</title>
<meta name="description" content="{e(desc)}">
<meta property="og:site_name" content="{e(name)}">
<meta property="og:type" content="website">
<meta property="og:title" content="{e(name)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(origin)}/">
<meta property="og:image" content="{e(image)}">
<meta name="twitter:card" content="summary_large_image">"""
    page = re.sub(r"<title>.*?</title>", lambda m: meta, page, count=1, flags=re.S)
    open(path, "w", encoding="utf-8").write(page)
    print("[完成] 首頁標題與預覽資訊")

if __name__ == "__main__":
    sys.exit(main())
