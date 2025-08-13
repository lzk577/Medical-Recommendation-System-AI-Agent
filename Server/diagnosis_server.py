# diagnosis_server.py  — MCP server for Infermedica + GPT dept mapping
import os
import aiohttp
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("Diagnosis Assistant")

INFER_APP_ID  = os.getenv("INFERMEDICA_APP_ID", "")
INFER_APP_KEY = os.getenv("INFERMEDICA_APP_KEY", "")
BASE_URL = "https://api.infermedica.com/v3"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

async def _request(method: str, endpoint: str, payload=None):
    headers = {
        "App-Id": INFER_APP_ID,
        "App-Key": INFER_APP_KEY,
        "Content-Type": "application/json",
        "Accept-Language": "en",
    }
    async with aiohttp.ClientSession() as session:
        async with session.request(method, f"{BASE_URL}{endpoint}", headers=headers, json=payload) as resp:
            if resp.status != 200:
                try:
                    detail = await resp.text()
                except Exception:
                    detail = ""
                return {"error": f"Request failed: {resp.status} {detail}"}
            return await resp.json()

@mcp.tool()
async def get_symptoms() -> list:
    data = await _request("GET", "/symptoms")
    if isinstance(data, dict) and data.get("error"):
        return []
    return [{"id": s["id"], "name": s["name"]} for s in data]

@mcp.tool()
async def parse_text_to_evidence(text: str, age: int = 30, sex: str = "male") -> list:
    payload = {"text": text, "age": {"value": age}, "sex": sex}
    data = await _request("POST", "/parse", payload)
    if isinstance(data, dict) and data.get("error"):
        return []
    mentions = data.get("mentions", [])
    return [{"id": m["id"], "choice_id": "present"} for m in mentions]

@mcp.tool()
async def run_diagnosis(evidence: list, age: int = 30, sex: str = "male") -> list:
    payload = {"sex": sex, "age": {"value": age}, "evidence": evidence}
    data = await _request("POST", "/diagnosis", payload)
    if isinstance(data, dict) and data.get("error"):
        return []
    conditions = data.get("conditions", [])
    return [{"name": c["name"], "probability": round(c["probability"] * 100, 2)} for c in conditions]

@mcp.tool()
async def get_department_by_evidence(disease_name: str) -> str:
    """
    Return the best-fitting HOSPITAL DEPARTMENT in ENGLISH for the disease.
    Output ONE concise department name only, e.g. 'Neurology', 'Urology',
    'Nephrology', 'Cardiology', 'Orthopedics', 'Otolaryngology (ENT)'.
    """
    if not OPENAI_API_KEY:
        return "Unknown"

    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "gpt-4o-mini",
        "temperature": 0,
        "max_tokens": 20,
        "messages": [
            {
                "role": "system",
                "content": "You are a medical expert. Reply with a SINGLE concise ENGLISH hospital department name only."
            },
            {
                "role": "user",
                "content": f"For the disease '{disease_name}', which hospital department should the patient visit?"
            }
        ]
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status != 200:
                return "Unknown"
            result = await resp.json()
            try:
                return result["choices"][0]["message"]["content"].strip()
            except Exception:
                return "Unknown"


if __name__ == "__main__":
    mcp.run()
