# my_speechtext.py — Voice/Text intake, Diagnosis+Dept via MCP, City/State + Speciality → Top-5 doctors from CSV
import asyncio, threading, tempfile, wave, time, re, json, os, tkinter as tk
from tkinter import ttk, messagebox
import pyaudio

from aurite import Aurite
from aurite.config.config_models import AgentConfig, LLMConfig, ClientConfig

# ------------------------------
# Config
# ------------------------------
CHUNK, FORMAT, CHANNELS, RATE = 1024, pyaudio.paInt16, 1, 16000
LANG_MAP = {"English": "en", "Chinese": "zh"}
SEX_OPTIONS = ["male", "female"]  # UI 下拉

# ------------------------------
# STT via speechtext_server
# ------------------------------
async def setup_and_run_agent(path, lang):
    aur = Aurite()
    await aur.initialize()
    try:
        await aur.register_llm_config(LLMConfig(
            llm_id="openai_gpt4_turbo", provider="openai", model_name="gpt-4-turbo"
        ))
        await aur.register_client(ClientConfig(
            name="speechtext_server",
            server_path="speechtext_server.py",
            protocol="stdio",
            capabilities=["tools"],
        ))
        await aur.register_agent(AgentConfig(
            name="SpeechAgent",
            system_prompt="You are a speech-to-text agent. Use transcribe_audio.",
            mcp_servers=["speechtext_server"],
            llm_config_id="openai_gpt4_turbo",
        ))
        res = await aur.run_agent(
            agent_name="SpeechAgent",
            user_message=f"Transcribe '{path}' as {lang}"
        )
        return res.primary_text
    finally:
        await aur.shutdown()

# ------------------------------
# Split symptoms vs. location via LLM
# ------------------------------
async def parse_symptom_and_location(raw_text: str) -> dict:
    aur = Aurite()
    await aur.initialize()
    try:
        await aur.register_llm_config(LLMConfig(
            llm_id="openai_gpt4_turbo", provider="openai", model_name="gpt-4-turbo"
        ))
        await aur.register_agent(AgentConfig(
            name="SegAgent",
            system_prompt=(
                "Split the input into STRICT JSON with keys 'symptoms' and 'location'. "
                "Rules: 'symptoms' -> health complaints only; 'location' -> address/city/state/country/zip. "
                "If missing, set ''. Output ONLY JSON."
            ),
            mcp_servers=[],
            llm_config_id="openai_gpt4_turbo"
        ))
        res = await aur.run_agent(
            agent_name="SegAgent",
            user_message=f"INPUT: {raw_text}\nRespond with JSON."
        )
        txt = res.primary_text.strip()
        try:
            data = json.loads(txt)
            return {"symptoms": data.get("symptoms", "").strip(),
                    "location": data.get("location", "").strip()}
        except Exception:
            return {"symptoms": raw_text, "location": ""}
    finally:
        await aur.shutdown()

# ------------------------------
# Diagnosis (Infermedica) + Department via diagnosis_server
# ------------------------------
async def diagnose_with_departments(symptoms_text: str, age: int, sex: str):
    """
    Orchestrates via diagnosis_server (MCP):
      1) parse_text_to_evidence(text, age, sex)
      2) run_diagnosis(evidence, age, sex)
      3) For Top-3 conditions, call get_department_by_evidence(name)
    Returns STRICT JSON list sorted by probability desc:
      [{"name": str, "probability": float, "department": str}, ...]
    """
    aur = Aurite()
    await aur.initialize()
    try:
        await aur.register_llm_config(LLMConfig(
            llm_id="openai_gpt4_turbo", provider="openai", model_name="gpt-4-turbo"
        ))
        await aur.register_client(ClientConfig(
            name="diagnosis_server",
            server_path="diagnosis_server.py",
            protocol="stdio",
            capabilities=["tools"],
        ))

        sys_prompt = (
            "你是诊断编排代理，必须按以下顺序调用 MCP 工具："
            "1) parse_text_to_evidence(text, age, sex)；"
            "2) run_diagnosis(evidence, age, sex)；"
            "3) 取概率 Top-3 的疾病，分别调用 get_department_by_evidence(disease_name) 返回 ENGLISH department。"
            "最终只返回严格 JSON 数组（按概率降序），每项含 name、probability（百分比数字）、department。不得输出其它文字。"
        )
        await aur.register_agent(AgentConfig(
            name="Diagnosis Agent",
            system_prompt=sys_prompt,
            mcp_servers=["diagnosis_server"],
            llm_config_id="openai_gpt4_turbo"
        ))

        payload = json.dumps({"text": symptoms_text, "age": int(age), "sex": sex}, ensure_ascii=False)
        res = await aur.run_agent(agent_name="Diagnosis Agent", user_message=payload)
        raw = res.primary_text.strip()
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                data.sort(key=lambda x: x.get("probability", 0), reverse=True)
                return data
        except Exception:
            pass
        return []
    finally:
        await aur.shutdown()

# ------------------------------
# Doctor Top-5 via find_doctor_server (CSV)
# ------------------------------
async def find_doctors_via_agent(departments: list[str], city: str, state: str, limit: int = 5):
    """
    Calls find_doctor_server.py -> find_top_doctors(specialities, city, state, limit)
    Returns list of doctor dicts with name, hospital_name, speciality, average_score, city, state, street_address.
    """
    aur = Aurite()
    await aur.initialize()
    try:
        await aur.register_llm_config(LLMConfig(
            llm_id="openai_gpt4_turbo", provider="openai", model_name="gpt-4-turbo"
        ))
        await aur.register_client(ClientConfig(
            name="doctor_server",
            server_path="find_doctor_server.py",
            protocol="stdio",
            capabilities=["tools"],
        ))
        sys_prompt = (
            "You MUST call the MCP tool `find_top_doctors` with the provided "
            "`specialities`, `city`, `state`, and `limit`. "
            "Return ONLY the raw JSON array you receive. No prose or markdown."
        )
        await aur.register_agent(AgentConfig(
            name="Doctor Agent",
            system_prompt=sys_prompt,
            mcp_servers=["doctor_server"],
            llm_config_id="openai_gpt4_turbo",
        ))
        msg = json.dumps({
            "specialities": departments or [],
            "city": city or None,
            "state": state or None,
            "limit": int(limit or 5),
        }, ensure_ascii=False)
        res = await aur.run_agent(agent_name="Doctor Agent", user_message=msg)
        raw = res.primary_text.strip()
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
        except Exception:
            pass
        return []
    finally:
        await aur.shutdown()

# ------------------------------
# Parse City/State from Detected Location (EN/CN heuristics)
# ------------------------------
def parse_city_state(location: str) -> tuple[str, str]:
    s = (location or "").strip()
    if not s:
        return "", ""
    # English: "Los Angeles, CA 90007"
    m = re.search(r"([A-Za-z .\-]+),\s*([A-Z]{2})(?:\s+\d{5})?", s)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    # Fallback: first two comma parts
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if len(parts) >= 2 and all(re.search(r"[A-Za-z]", p) for p in parts[:2]):
        return parts[0], parts[1]
    # Chinese: "...省...市..." or "...市..."
    m2 = re.search(r"(?P<prov>[^省]+省)?(?P<city>[^市]+市)", s)
    if m2:
        city = (m2.group("city") or "").replace("市", "").strip()
        prov = (m2.group("prov") or "").replace("省", "").strip()
        return city, prov
    return s, ""

# ------------------------------
# Main UI
# ------------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Medical recommendation System")
        self.state('zoomed')
        self.minsize(1100, 720)

        # Global state
        self.audio = pyaudio.PyAudio()
        self.frames: list[bytes] = []
        self.is_recording = False
        self.is_processing = False

        self.input_mode = tk.StringVar(value="Voice")
        self.lang_var = tk.StringVar(value=list(LANG_MAP.keys())[0])
        self.loc_var  = tk.StringVar(value="")

        self.last_symptoms = ""
        self.last_location = ""

        # NEW: sex & age
        self.sex_var = tk.StringVar(value=SEX_OPTIONS[0])  # "male"
        self.age_var = tk.StringVar(value="30")

        self._build_styles()
        self._build_header()
        self._build_body()

        self.bind("<Escape>", lambda e: self._toggle_fullscreen(False))
        self.after(200, lambda: self.status_var.set("Ready"))

    # ---------- styling ----------
    def _build_styles(self):
        self.configure(bg="#ffffff")
        style = ttk.Style(self)
        style.theme_use("clam")
        c_bg="#ffffff"; c_panel="#f8f9fa"; c_text="#212529"; c_muted="#6c757d"
        c_primary="#0d6efd"; c_accent="#198754"; c_warn="#dc3545"
        style.configure("TFrame", background=c_bg)
        style.configure("Card.TFrame", background=c_panel, relief="flat")
        style.configure("Title.TLabel", background=c_bg, foreground=c_text, font=("Segoe UI", 26, "bold"))
        style.configure("Sub.TLabel", background=c_bg, foreground=c_muted, font=("Segoe UI", 12))
        style.configure("Head.TLabel", background=c_panel, foreground=c_text, font=("Segoe UI", 18, "bold"))
        style.configure("Text.TLabel", background=c_panel, foreground=c_text, font=("Consolas", 12))
        style.configure("Muted.TLabel", background=c_panel, foreground=c_muted, font=("Segoe UI", 11))
        style.configure("Primary.TButton", font=("Segoe UI", 12, "bold"), padding=12)
        style.map("Primary.TButton",
                  background=[("!disabled", c_primary), ("disabled", "#adb5bd")],
                  foreground=[("!disabled", "#ffffff"), ("disabled", "#6c757d")])
        style.configure("Accent.TButton", font=("Segoe UI", 12, "bold"), padding=12)
        style.map("Accent.TButton",
                  background=[("!disabled", c_accent), ("disabled", "#adb5bd")],
                  foreground=[("!disabled", "#ffffff"), ("disabled", "#6c757d")])
        style.configure("Warn.TButton", font=("Segoe UI", 12, "bold"), padding=12)
        style.map("Warn.TButton",
                  background=[("!disabled", c_warn), ("disabled", "#adb5bd")],
                  foreground=[("!disabled", "#ffffff"), ("disabled", "#6c757d")])
        self.text_bg="#ffffff"; self.text_fg="#000000"; self.text_border="#ced4da"

    # ---------- header ----------
    def _build_header(self):
        top = ttk.Frame(self, padding=20)
        top.pack(fill="x")

        ttk.Label(top, text="Medical recommendation System", style="Title.TLabel").pack(side="left", padx=(0, 20))
        self.status_var = tk.StringVar(value="Initializing…")
        ttk.Label(top, textvariable=self.status_var, style="Sub.TLabel").pack(side="left")

        right = ttk.Frame(top); right.pack(side="right")
        ttk.Label(right, text="Input Mode:", style="Sub.TLabel").grid(row=0, column=0, padx=8)
        self.mode_combo = ttk.Combobox(right, values=["Voice", "Text"], state="readonly",
                                       textvariable=self.input_mode, width=8)
        self.mode_combo.grid(row=0, column=1, padx=8)
        self.mode_combo.bind("<<ComboboxSelected>>", lambda e: self._on_mode_change())

        ttk.Label(right, text="Language:", style="Sub.TLabel").grid(row=0, column=2, padx=8)
        self.lang_combo = ttk.Combobox(right, values=list(LANG_MAP.keys()), state="readonly",
                                       textvariable=self.lang_var, width=10)
        self.lang_combo.grid(row=0, column=3, padx=8)

        # NEW: Sex
        ttk.Label(right, text="Sex:", style="Sub.TLabel").grid(row=0, column=4, padx=(16, 8))
        self.sex_combo = ttk.Combobox(right, values=SEX_OPTIONS, state="readonly",
                                      textvariable=self.sex_var, width=8)
        self.sex_combo.grid(row=0, column=5, padx=8)

        # NEW: Age
        ttk.Label(right, text="Age:", style="Sub.TLabel").grid(row=0, column=6, padx=(16, 8))
        vcmd_age = (self.register(self._validate_age), "%P")
        self.age_entry = ttk.Entry(right, width=6, textvariable=self.age_var,
                                   validate="key", validatecommand=vcmd_age)
        self.age_entry.grid(row=0, column=7, padx=8)

    # ---------- body ----------
    def _build_body(self):
        body = ttk.Frame(self, padding=20)
        body.pack(fill="both", expand=True)

        body.columnconfigure(0, weight=1, uniform="cols")
        body.columnconfigure(1, weight=1, uniform="cols")
        body.columnconfigure(2, weight=1, uniform="cols")

        # Recording
        self.rec_card = ttk.Frame(body, style="Card.TFrame", padding=18)
        self.rec_card.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        ttk.Label(self.rec_card, text="Recording", style="Head.TLabel").pack(anchor="w", pady=(0, 10))
        self.btn_record = ttk.Button(self.rec_card, text="Hold to Record", style="Primary.TButton")
        self.btn_record.pack(fill="x")
        self.btn_record.bind('<ButtonPress-1>', self._start_recording)
        self.btn_record.bind('<ButtonRelease-1>', self._stop_recording)

        self.btn_transcribe = ttk.Button(self.rec_card, text="Transcribe Now", style="Accent.TButton",
                                         command=self._kick_transcription)
        self.btn_transcribe.pack(fill="x", pady=(12, 0))

        # Text (Text mode only)
        self.text_input = tk.Text(self.rec_card, height=8, bd=0, highlightthickness=1)
        self._style_text(self.text_input)
        self.text_input.pack(fill="both", expand=False, pady=(12, 0))
        self.text_input_for_use = ttk.Button(self.rec_card, text="Use Text as Symptoms",
                                             style="Accent.TButton", command=self._use_text_directly)
        self.text_input_for_use.pack(fill="x", pady=(12, 0))

        # Transcription
        self.tr_card = ttk.Frame(body, style="Card.TFrame", padding=18)
        self.tr_card.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        ttk.Label(self.tr_card, text="Transcription", style="Head.TLabel").pack(anchor="w", pady=(0, 10))
        self.tr_text = tk.Text(self.tr_card, height=16, bd=0, highlightthickness=1)
        self._style_text(self.tr_text)
        self.tr_text.pack(fill="both", expand=True)

        # Detected location
        loc_row = ttk.Frame(self.tr_card, style="Card.TFrame")
        loc_row.pack(fill="x", pady=(8, 0))
        ttk.Label(loc_row, text="Detected Location:", style="Muted.TLabel").pack(side="left")
        ttk.Label(loc_row, textvariable=self.loc_var, style="Text.TLabel").pack(side="left", padx=(8, 0))

        # Recommendations
        self.rc_card = ttk.Frame(body, style="Card.TFrame", padding=18)
        self.rc_card.grid(row=0, column=2, sticky="nsew", padx=10, pady=10)

        ttk.Label(self.rc_card, text="Recommendations", style="Head.TLabel").pack(anchor="w", pady=(0, 10))
        self.rc_text = tk.Text(self.rc_card, height=16, bd=0, highlightthickness=1)
        self._style_text(self.rc_text)
        self.rc_text.pack(fill="both", expand=True)

        self.btn_get_reco = ttk.Button(self.rc_card, text="Get Doctor & Hospital Suggestions",
                                       style="Primary.TButton", command=self._get_recommendations, state="disabled")
        self.btn_get_reco.pack(fill="x", pady=(12, 0))

        self.btn_retry = ttk.Button(self.rc_card, text="Record Again", style="Warn.TButton",
                                    command=self._reset_for_retry, state="disabled")
        self.btn_retry.pack(fill="x", pady=(10, 0))

        self._on_mode_change()

    # ---------- helpers ----------
    def _style_text(self, w: tk.Text):
        w.configure(bg=self.text_bg, fg=self.text_fg, insertbackground=self.text_fg,
                    font=("Consolas", 12), relief="flat", padx=10, pady=10)
        w.configure(highlightbackground=self.text_border, highlightcolor=self.text_border)

    def _log_status(self, s: str):
        self.after(0, lambda: self.status_var.set(s))

    def _append_text(self, w: tk.Text, msg: str, nl=True):
        def _do():
            w.insert(tk.END, msg + ("\n" if nl else ""))
            w.see(tk.END)
        self.after(0, _do)

    def _toggle_fullscreen(self, on: bool):
        if on:
            self.state('zoomed')
        else:
            self.state('normal')
            self.geometry("1200x780")

    def _on_mode_change(self):
        mode = self.input_mode.get()
        if mode == "Voice":
            self.text_input.pack_forget()
            self.text_input_for_use.pack_forget()
            self.btn_record.state(["!disabled"])
            self.btn_transcribe.state(["!disabled"])
        else:
            self.text_input.pack(fill="both", expand=False, pady=(12, 0))
            self.text_input_for_use.pack(fill="x", pady=(12, 0))
            self.btn_record.state(["disabled"])
            self.btn_transcribe.state(["disabled"])

    # ---------- recording flow ----------
    def _start_recording(self, _evt):
        if self.is_processing or self.input_mode.get() != "Voice":
            return
        self.frames = []
        self.is_recording = True
        self._set_buttons_during_recording(True)
        threading.Thread(target=self._record_loop, daemon=True).start()
        self._log_status("Recording...")
        self._append_text(self.tr_text, "⏺️ Start recording", True)

    def _stop_recording(self, _evt):
        if not self.is_recording:
            return
        self.is_recording = False
        self._log_status("Recording stopped")
        self._append_text(self.tr_text, "⏹️ Stop recording", True)

    def _record_loop(self):
        stream = self.audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
        while self.is_recording:
            self.frames.append(stream.read(CHUNK, exception_on_overflow=False))
        stream.stop_stream()
        stream.close()
        self.after(0, lambda: self.btn_transcribe.state(["!disabled"]))

    def _kick_transcription(self):
        if self.is_processing or self.input_mode.get() != "Voice":
            return
        if not self.frames:
            messagebox.showinfo("Info", "Please record first: hold the button to speak.")
            return
        self.is_processing = True
        self._set_buttons_during_processing(True)
        self._log_status("Transcribing...")
        threading.Thread(target=self._transcribe_thread, daemon=True).start()

    def _transcribe_thread(self):
        # write temp wav
        wav = tempfile.NamedTemporaryFile(suffix='.wav', delete=False).name
        with wave.open(wav, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(self.audio.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(self.frames))

        lang = LANG_MAP[self.lang_var.get()]
        try:
            txt = asyncio.run(setup_and_run_agent(wav, lang))
        except Exception as e:
            txt = f"[Error] {e}"

        # semantic parse -> symptoms/location
        try:
            parsed = asyncio.run(parse_symptom_and_location(txt))
            symptoms = parsed.get("symptoms", txt)
            location = parsed.get("location", "")
        except Exception:
            symptoms, location = txt, ""

        self.last_symptoms = symptoms
        self.last_location = location

        # update UI
        self.tr_text.delete("1.0", tk.END)
        self._append_text(self.tr_text, f"📝 {symptoms}", True)
        self.loc_var.set(location)

        # allow recommendations / retry
        def _after():
            self.is_processing = False
            self._set_buttons_during_processing(False)
            self.btn_get_reco.state(["!disabled"])
            self.btn_retry.state(["!disabled"])
            self._log_status("Transcription completed")
        self.after(0, _after)

    def _use_text_directly(self):
        if self.is_processing or self.input_mode.get() != "Text":
            return
        content = self.text_input.get("1.0", tk.END).strip()
        if not content:
            messagebox.showinfo("Info", "Please type your symptoms first.")
            return
        self.tr_text.delete("1.0", tk.END)
        try:
            parsed = asyncio.run(parse_symptom_and_location(content))
            symptoms = parsed.get("symptoms", content)
            location = parsed.get("location", "")
        except Exception:
            symptoms, location = content, ""

        self.last_symptoms = symptoms
        self.last_location = location

        # update UI
        self._append_text(self.tr_text, f"📝 {symptoms}", True)
        self.loc_var.set(location)
        self.btn_get_reco.state(["!disabled"])
        self.btn_retry.state(["!disabled"])
        self._log_status("Text captured")

    # ---------- recommendations flow ----------
    def _get_recommendations(self):
        symptoms = (self.last_symptoms or "").strip()
        location = (self.last_location or "").strip()
        if not symptoms:
            messagebox.showinfo("Info", "No symptoms captured yet.")
            return

        age = self._get_age_int()
        sex = self.sex_var.get()

        self.rc_text.delete("1.0", tk.END)
        self._append_text(self.rc_text, "🔎 Running diagnosis and matching top city doctors...", True)

        def worker():
            # 1) 诊断 + 科室
            try:
                conditions = asyncio.run(diagnose_with_departments(symptoms_text=symptoms, age=age, sex=sex))
            except Exception as e:
                conditions = []
                self._append_text(self.rc_text, f"[Diagnosis error] {e}", True)

            # 2) 解析 city/state
            city, state = parse_city_state(location)

            # 3) 取科室（Top-3）并查 CSV（Top-5）
            departments = [c.get("department", "") for c in conditions if c.get("department")]
            try:
                top_docs = asyncio.run(find_doctors_via_agent(departments, city, state, limit=5))
            except Exception as e:
                top_docs = []
                self._append_text(self.rc_text, f"[Doctor match error] {e}", True)

            # 4) Render
            lines = []
            lines.append(f"• Symptoms: {symptoms or '(none)'}")
            lines.append(f"• Location: {location or '(unknown)'}  → Parsed city/state: {city or '-'}, {state or '-'}")
            lines.append(f"• Sex/Age: {sex}, {age}")

            if conditions:
                lines.append("• Suspected conditions (by probability):")
                for c in conditions[:10]:
                    nm = c.get("name", "?")
                    pr = c.get("probability", 0.0)
                    dp = c.get("department", "")
                    lines.append(f"   - {nm} ({pr:.2f}%)  科室：{dp or '未知'}")
            else:
                lines.append("• Suspected conditions: (none)")

            if top_docs:
                lines.append("• Top doctors in your city/state:")
                for r in top_docs:
                    nm = r.get("name","?")
                    hosp = r.get("hospital_name","?")
                    sp = r.get("speciality","?")
                    sc = r.get("average_score", 0)
                    cc = r.get("city",""); ss = r.get("state","")
                    lines.append(f"   - {nm} | {sp} | {hosp} | {cc}, {ss} | ★{float(sc):.2f}")
            else:
                lines.append("• Top doctors in your city/state: (none)")

            lines.append("• Next step: click 'Record Again' if the text is inaccurate.")
            self._append_text(self.rc_text, "\n".join(lines), True)
            self._log_status("Recommendations ready")

        threading.Thread(target=worker, daemon=True).start()

    def _reset_for_retry(self):
        self.frames.clear()
        self.tr_text.delete("1.0", tk.END)
        self.rc_text.delete("1.0", tk.END)
        self.btn_get_reco.state(["disabled"])
        self.btn_retry.state(["disabled"])

        self.last_symptoms = ""
        self.last_location = ""
        self.loc_var.set("")

        self.is_recording = False
        self.is_processing = False
        self._set_buttons_during_recording(False)
        self._set_buttons_during_processing(False)
        self._log_status("Ready for a new attempt")

    # ---------- button state helpers ----------
    def _set_buttons_during_recording(self, recording: bool):
        if recording:
            self.btn_record.state(["disabled"])
            self.btn_transcribe.state(["disabled"])
            self.mode_combo.state(["disabled"])
            self.lang_combo.state(["disabled"])
            self.sex_combo.state(["disabled"])
            self.age_entry.state(["disabled"])
        else:
            if self.input_mode.get() == "Voice":
                self.btn_record.state(["!disabled"])
                self.btn_transcribe.state(["!disabled"])
            else:
                self.btn_record.state(["disabled"])
                self.btn_transcribe.state(["disabled"])
            self.mode_combo.state(["!disabled"])
            self.lang_combo.state(["!disabled"])
            self.sex_combo.state(["!disabled"])
            self.age_entry.state(["!disabled"])

    def _set_buttons_during_processing(self, processing: bool):
        states = ["disabled"] if processing else ["!disabled"]
        if self.input_mode.get() == "Voice":
            self.btn_record.state(["disabled"] if processing else ["!disabled"])
            self.btn_transcribe.state(states)
        else:
            self.btn_record.state(["disabled"])
            self.btn_transcribe.state(["disabled"])
        self.mode_combo.state(["disabled"] if processing else ["!disabled"])
        self.lang_combo.state(["disabled"] if processing else ["!disabled"])
        self.sex_combo.state(["disabled"] if processing else ["!disabled"])
        self.age_entry.state(["disabled"] if processing else ["!disabled"])

    # ---------- validation + getters ----------
    def _validate_age(self, proposed: str) -> bool:
        if proposed.strip() == "":
            return True
        if not proposed.isdigit():
            return False
        v = int(proposed)
        return 0 <= v <= 120

    def _get_age_int(self) -> int:
        try:
            v = int(self.age_var.get().strip())
            return v if 0 <= v <= 120 else 30
        except Exception:
            return 30

    # ---------- window close ----------
    def on_close(self):
        try:
            self.audio.terminate()
        finally:
            self.destroy()

# ------------------------------
# Entry
# ------------------------------
if __name__ == '__main__':
    time.sleep(0.2)
    app = App()
    app.protocol('WM_DELETE_WINDOW', app.on_close)
    app.mainloop()

