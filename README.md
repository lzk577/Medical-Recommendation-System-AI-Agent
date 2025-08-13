# Medical-Recommendation-System-AI-Agent
A Tkinter desktop app + Aurite MCP agents that AI-powered assistant for patients that processes medical information efficiently across languages and recommends the best doctor based on a comprehensive score.

---

## 🚀 Quick Start

### 1) Environment Setup

Copy the example env file and fill your keys.


```bash
cp .env.example .env
```

Fill in `.env` (see full example below).


```dotenv
OPENAI_API_KEY=your_openai_key
INFERMEDICA_APP_ID=your_infermedica_app_id
INFERMEDICA_APP_KEY=your_infermedica_app_key
DOCTOR_DB_CSV=medical_information.csv  # optional
AURITE_LOG_LEVEL=INFO                  # optional
```

### 2) Install Dependencies

> Python 3.10+ recommended

```bash
pip install -U -r requirements.txt
```

> If `pyaudio` fails on Windows:
>
> ```bash
> pip install pipwin
> pipwin install pyaudio
> ```

### 3) Prepare Data

Put a CSV in project root (or set `DOCTOR_DB_CSV` in `.env`) with **columns**:

```
name, speciality, average_score, hospital_name, city, state
# street_address
```

**Example

```
Dr. Emily Zhang, Nephrology, 4.8, UCLA Medical Center, Los Angeles, CA
```

### 4) Start the App

```bash
python my_speechtext.py
```

Aurite launches MCP servers (`speechtext_server.py`, `diagnosis_server.py`, `find_doctor_server.py`) via stdio automatically.

---

## 🧭 Usage Flow

1. Choose **Voice** (press & hold) or **Text** mode.

2. Select **Language / Sex / Age**.

3. Speak or type symptoms; speech is **accurately** transcribed (medical terms preserved).

4. Input is **split** into *Symptoms* and *Location* and translated to **English**.

5. Click **Get Doctor & Hospital Suggestions**.

6. View **top conditions + department** and **Top-5 doctors** filtered by department & city/state.

---

## 📦 Project Structure

```
.
├─ my_speechtext.py          # Tkinter UI + orchestration
├─ speechtext_server.py      # MCP: speech → text
├─ diagnosis_server.py       # MCP: Infermedica + EN department
├─ find_doctor_server.py     # MCP: CSV Top-5 doctor finder
├─ medical_information.csv   # Doctor DB
├─ .env.example
├─ .env
└─ README.md
```

---

## ✨ Main Features

* **High-accuracy speech recognition** (medical terms preserved)

* **Semantic segmentation** → English *symptoms* & *location*

* **Infermedica diagnosis** with probabilities

* **English department mapping** per condition

* **CSV doctor finder**: filter by department + city/state, sort by `average_score`, show **Top-5**


---

## 🛠 Tech Stack

**Desktop UI**: Tkinter
**Agents/Orchestration**: Aurite (MCP)
**LLM**: OpenAI GPT
**Medical**: Infermedica API
**Data**: FastMCP tools + CSV

---

## ⚙️ Important Notes

* **Not medical advice**; demo/education only.

* Keep `.env` secrets safe — **do not commit**.

* Internet is required (OpenAI & Infermedica).

* CSV expects exact **city** names and **state abbreviations** (e.g., `CA`, `NC`).

---

## 🧩 Troubleshooting

* **MCP “Connection closed”**
  Ensure the three MCP scripts exist, `fastmcp` is installed, and there are no syntax errors.


* **No doctors found**
  Check parsed *city/state* and CSV fields; verify `speciality` strings match.


* **PyAudio install (Windows)**
  Use `pipwin install pyaudio`.
  Windows 用 `pipwin install pyaudio`。

---

## 🧪 Known Limitations

* Doctor recommendations are limited to your **CSV content** (no live web hospital search).

* Diagnosis quality depends on input clarity and API coverage.

* Output UI is **English-only**.


---

## 📄 License

Choose a license (e.g., MIT/GPL-3.0) and add `LICENSE`.

---

## 📁 Templates

### `.env.example`

```dotenv
# OpenAI (LLM orchestration, translation, department mapping)
OPENAI_API_KEY=sk-your_openai_api_key

# Infermedica (medical diagnosis)
INFERMEDICA_APP_ID=your_infermedica_app_id
INFERMEDICA_APP_KEY=your_infermedica_app_key

# Doctors CSV (relative or absolute path)
DOCTOR_DB_CSV=medical_information.csv

# Optional logging level for Aurite
AURITE_LOG_LEVEL=INFO
```

### `requirements.txt`

```txt
aurite>=0.4.0
mcp>=1.2.0
fastmcp>=0.3.0
aiohttp>=3.9.0
python-dotenv>=1.0.1
pyaudio>=0.2.13
requests>=2.32.3
```

> Windows tip (if PyAudio fails):
> `pip install pipwin && pipwin install pyaudio`

---
