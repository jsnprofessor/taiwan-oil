"""Write .review/issue.md for the weekly 「需要檢查的加油站」 issue (empty = nothing to check)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVIEW_DIR = ROOT / ".review"
STATIONS_PATH = ROOT / "site" / "data" / "stations.json"
TITLE = "需要檢查的加油站"


def _pin(lat, lng):
    return f"https://www.google.com/maps?q={lat},{lng}"


def _listing(pid):
    return f"https://www.google.com/maps/place/?q=place_id:{pid}"


def _line(stations_by_id, sid, extra=""):
    s = stations_by_id.get(sid)
    if not s:
        return f"- `{sid}`（已不在 CPC 資料中）{extra}"
    where = f"{s.get('city', '')}{s.get('district', '')}{s.get('addr', '')}"
    return f"- `{sid}` {s['name']} — {where} · [CPC 位置]({_pin(s['lat'], s['lng'])}){extra}"


def build(moved, match, stations_by_id):
    sections = []

    def section(title, lines):
        if lines:
            sections.append(f"### {title}\n\n" + "\n".join(lines))

    section("找不到或不確定的 Google 地圖配對（下週會再試）", [
        _line(stations_by_id, d["id"], f" · [Google 候選]({_listing(d['pid'])})" if d.get("pid") else "")
        for d in match.get("doubtful", [])])
    section('位置可能有誤：請在 data/places.json 為這些站加上 fix，並把 src 改成 "reviewed"', [
        _line(stations_by_id, f["id"], f" · 相距 {f['far'] / 1000:.1f} 公里 · [Google 地圖上的位置]({_listing(f['pid'])})")
        for f in match.get("far_unfixed", [])])
    section('CPC 改了已檢查站點的名稱或地址（要重新配對，把該站的 src 改成 "auto"）', [
        _line(stations_by_id, sid) for sid in match.get("reviewed_changed", [])])
    section("CPC 移動了你修正過的站點（CPC 可能已更正；確認後可刪除該站的 fix）", [
        _line(stations_by_id, m["id"], f" · [CPC 的新位置]({_pin(*m['cpc'])})") for m in moved])
    notes = []
    if match.get("error"):
        notes.append(f"- 這次配對未完成：{match['error']}")
    if match.get("remaining"):
        notes.append(f"- 還有 {match['remaining']} 個站點等待配對（每週最多 50 個）")
    section("其他", notes)
    if not sections:
        return ""
    return "\n\n".join(sections) + "\n\n---\n此清單由每週更新自動產生，處理完畢後會自動關閉。\n"


def main():
    def read(name, default):
        p = REVIEW_DIR / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
    stations = json.loads(STATIONS_PATH.read_text(encoding="utf-8"))["stations"]
    text = build(read("moved.json", []), read("match.json", {}), {s["id"]: s for s in stations})
    REVIEW_DIR.mkdir(exist_ok=True)
    (REVIEW_DIR / "issue.md").write_text(text, encoding="utf-8")
    print("Review issue: " + ("has items" if text else "nothing to check"))


if __name__ == "__main__":
    main()
