"""把 content/ 裡「一筆一個檔案」的內容，合併成網站讀取的 data/*.json，
輸出到 _site/ 資料夾給 GitHub Pages 發佈。由 .github/workflows/deploy.yml 自動執行。"""
import glob, json, os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "_site")
SKIP = {".git", ".github", "_site", "content", "scripts", ".pages.yml", "README.md"}

# 集合資料夾 → 網站讀取的檔名，以及排序方式
COLLECTIONS = {
    "series": ("series.json", lambda x, f: (num(x.get("order")), str(x.get("title") or "")), False),
    "chapters": ("chapters.json", lambda x, f: (num(x.get("order")), str(x.get("date") or "")), False),
    "side-stories": ("side-stories.json", lambda x, f: str(x.get("date") or ""), False),
    "characters": ("characters.json", lambda x, f: (num(x.get("order")), str(x.get("name") or "")), False),
    "commissions": ("commissions.json", lambda x, f: str(x.get("date") or ""), False),
    "gallery": ("gallery.json", lambda x, f: str(x.get("date") or ""), False),
    "notes": ("notes.json", lambda x, f: str(x.get("date") or ""), False),
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
            print(f"[略過] content/{folder} 不存在，沿用 data/{outname}")
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
    print(f"建置完成，警告 {warnings} 個")

if __name__ == "__main__":
    sys.exit(main())
