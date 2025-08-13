# find_doctor_server.py — MCP server: CSV doctor finder by speciality + city/state (Top-5)
import os, csv, logging
from typing import List, Optional
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

mcp = FastMCP("Doctor Assistant")

# 你的 CSV 路径（不设置则默认同目录下 medical_information.csv）
CSV_FILE_PATH = os.getenv("DOCTOR_DB_CSV", "medical_information.csv")

# -------- helpers --------
def _norm(s: Optional[str]) -> str:
    """lower + trim + 折叠空格"""
    s = (s or "").strip()
    s = " ".join(s.split())
    return s.casefold()

def _as_float(v) -> float:
    try:
        return float(str(v).strip())
    except Exception:
        return 0.0

def _read_rows(path: str) -> list[dict]:
    """
    严格按照截图列名读取：
    name, speciality, average_score, hospital_name, city, state
    若个别文件仍是别名（如 average_sc / hospital），做一次轻量兜底。
    """
    if not os.path.exists(path):
        log.warning("CSV not found: %s", path)
        return []

    rows: list[dict] = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        hdr = [h.strip().lower() for h in (reader.fieldnames or [])]

        # 轻量别名兜底（仅这两项最常见）
        has_avg = "average_score" in hdr or "average_sc" in hdr
        has_hosp = "hospital_name" in hdr or "hospital" in hdr

        for r in reader:
            # 精确字段
            name           = (r.get("name") or "").strip()
            speciality     = (r.get("speciality") or "").strip()
            # 评分允许 average_sc 兜底
            average_score  = r.get("average_score")
            if average_score is None:
                average_score = r.get("average_sc", "")
            # 医院允许 hospital 兜底
            hospital_name  = (r.get("hospital_name") or r.get("hospital") or "").strip()
            city           = (r.get("city") or "").strip()
            state          = (r.get("state") or "").strip()

            rows.append({
                "name": name,
                "speciality": speciality,
                "average_score": _as_float(average_score),
                "hospital_name": hospital_name,
                "city": city,
                "state": state,
            })

    if not rows:
        log.warning("CSV read 0 rows from: %s", path)
    return rows

def _spec_match(spec: str, wanted: set[str]) -> bool:
    """专科匹配：子串 + 等值（Orthopedic Sports Medicine ≈ Sports Medicine）"""
    s = _norm(spec)
    if not wanted:
        return True
    return any(w and (w in s or s in w) for w in wanted)

# -------- MCP tool --------
@mcp.tool()
async def find_top_doctors(
    specialities: List[str],
    city: Optional[str] = None,
    state: Optional[str] = None,
    limit: int = 5
) -> List[dict]:
    """
    从 CSV（medical_information.csv）按 speciality + city/state 过滤，
    按 average_score 降序返回前 N（默认 5）。
    期望列：name, speciality, average_score, hospital_name, city, state
    """
    rows = _read_rows(CSV_FILE_PATH)
    if not rows:
        return []

    want_specs = {_norm(s) for s in (specialities or [])}
    city_l, state_l = _norm(city), _norm(state)

    def ok_row(r):
        if city_l and _norm(r["city"]) != city_l:
            return False
        if state_l and _norm(r["state"]) != state_l:
            return False
        if not _spec_match(r["speciality"], want_specs):
            return False
        return True

    # 1) city+state
    filtered = [r for r in rows if ok_row(r)]

    # 2) 放宽（仅当无结果）
    if not filtered and city_l:
        filtered = [r for r in rows
                    if _norm(r["city"]) == city_l and _spec_match(r["speciality"], want_specs)]
    if not filtered and state_l:
        filtered = [r for r in rows
                    if _norm(r["state"]) == state_l and _spec_match(r["speciality"], want_specs)]
    if not filtered:
        filtered = [r for r in rows if _spec_match(r["speciality"], want_specs)]

    # 排序 & 截断
    filtered.sort(key=lambda r: (-r["average_score"], _norm(r["hospital_name"]), _norm(r["name"])))
    top = filtered[: max(1, int(limit or 5))]

    # 仅输出关心字段
    return [
        {
            "name": r["name"],
            "hospital_name": r["hospital_name"],
            "speciality": r["speciality"],
            "average_score": r["average_score"],
            "city": r["city"],
            "state": r["state"],
        }
        for r in top
    ]

if __name__ == "__main__":
    mcp.run()
