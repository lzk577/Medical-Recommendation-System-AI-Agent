# my_speechtext_project.py  — Light theme, no Full Screen button, Voice/Text toggle
import asyncio, threading, tempfile, wave, time, tkinter as tk
from tkinter import ttk, messagebox
import pyaudio

from aurite import Aurite
from aurite.config.config_models import AgentConfig, LLMConfig, ClientConfig

# ------------------------------
# Audio constants
# ------------------------------
CHUNK, FORMAT, CHANNELS, RATE = 1024, pyaudio.paInt16, 1, 16000
LANG_MAP = {"English": "en", "Chinese": "zh"}

# ------------------------------
# Aurite runner (STT only)
# ------------------------------
async def setup_and_run_agent(path, lang):
    """Call the Aurite agent which uses the speechtext_server MCP tool."""
    aur = Aurite()
    await aur.initialize()

    await aur.register_llm_config(LLMConfig(
        llm_id="openai_gpt4_turbo",
        provider="openai",
        model_name="gpt-4-turbo"
    ))
    await aur.register_client(ClientConfig(
        name="speechtext_server",
        server_path="speechtext_server.py",   # launch MCP tool server as a stdio child
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
    await aur.shutdown()
    return res.primary_text

# ------------------------------
# Main UI
# ------------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Patient Intake – Voice/Text")
        self.state('zoomed')   # Windows: start maximized. Use Esc to exit.
        self.minsize(1100, 700)

        # Global state
        self.audio = pyaudio.PyAudio()
        self.frames: list[bytes] = []
        self.is_recording = False
        self.is_processing = False
        self.input_mode = tk.StringVar(value="Voice")  # "Voice" or "Text"
        self.lang_var = tk.StringVar(value=list(LANG_MAP.keys())[0])

        # Theme / Styles
        self._build_styles()

        # Layout = three big zones: Recording | Transcription | Recommendations
        self._build_header()
        self._build_body()

        # keyboard shortcuts
        self.bind("<Escape>", lambda e: self._toggle_fullscreen(False))
        self.after(200, lambda: self.status_var.set("Ready"))

    # ---------- styling ----------
    def _build_styles(self):
        self.configure(bg="#ffffff")  # white background
        style = ttk.Style(self)
        style.theme_use("clam")

        # Colors (light theme)
        c_bg = "#ffffff"       # page
        c_panel = "#f8f9fa"    # card
        c_text = "#212529"     # main
        c_muted = "#6c757d"    # secondary
        c_primary = "#0d6efd"  # blue
        c_accent = "#198754"   # green
        c_warn = "#dc3545"     # red

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

        # Text widget look
        self.text_bg = "#ffffff"
        self.text_fg = "#000000"
        self.text_border = "#ced4da"

    # ---------- header ----------
    def _build_header(self):
        top = ttk.Frame(self, padding=20)
        top.pack(fill="x")

        ttk.Label(top, text="Patient Symptom Intake", style="Title.TLabel").pack(side="left", padx=(0, 20))
        self.status_var = tk.StringVar(value="Initializing…")
        ttk.Label(top, textvariable=self.status_var, style="Sub.TLabel").pack(side="left")

        right = ttk.Frame(top)
        right.pack(side="right")

        ttk.Label(right, text="Input Mode:", style="Sub.TLabel").grid(row=0, column=0, padx=8)
        self.mode_combo = ttk.Combobox(right, values=["Voice", "Text"], state="readonly",
                                       textvariable=self.input_mode, width=8)
        self.mode_combo.grid(row=0, column=1, padx=8)
        self.mode_combo.bind("<<ComboboxSelected>>", lambda e: self._on_mode_change())

        ttk.Label(right, text="Language:", style="Sub.TLabel").grid(row=0, column=2, padx=8)
        self.lang_combo = ttk.Combobox(right, values=list(LANG_MAP.keys()), state="readonly",
                                       textvariable=self.lang_var, width=10)
        self.lang_combo.grid(row=0, column=3, padx=8)

        # NOTE: Full-screen button removed by request. Use Esc to exit full screen.

    # ---------- body ----------
    def _build_body(self):
        body = ttk.Frame(self, padding=20)
        body.pack(fill="both", expand=True)

        # 3 columns: Recording | Transcription | Recommendations
        body.columnconfigure(0, weight=1, uniform="cols")
        body.columnconfigure(1, weight=1, uniform="cols")
        body.columnconfigure(2, weight=1, uniform="cols")

        # --- Recording card ---
        self.rec_card = ttk.Frame(body, style="Card.TFrame", padding=18)
        self.rec_card.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        ttk.Label(self.rec_card, text="Recording", style="Head.TLabel").pack(anchor="w", pady=(0, 10))

        # Voice controls
        self.btn_record = ttk.Button(self.rec_card, text="Hold to Record", style="Primary.TButton")
        self.btn_record.pack(fill="x")
        self.btn_record.bind('<ButtonPress-1>', self._start_recording)
        self.btn_record.bind('<ButtonRelease-1>', self._stop_recording)

        self.btn_transcribe = ttk.Button(self.rec_card, text="Transcribe Now", style="Accent.TButton",
                                         command=self._kick_transcription)
        self.btn_transcribe.pack(fill="x", pady=(12, 0))

        # Text controls (shown only in Text mode)
        self.text_input = tk.Text(self.rec_card, height=8, bd=0, highlightthickness=1)
        self._style_text(self.text_input)
        self.text_input.pack(fill="both", expand=False, pady=(12, 0))
        self.text_input_for_use = ttk.Button(self.rec_card, text="Use Text as Symptoms",
                                             style="Accent.TButton", command=self._use_text_directly)
        self.text_input_for_use.pack(fill="x", pady=(12, 0))

        # --- Transcription card ---
        self.tr_card = ttk.Frame(body, style="Card.TFrame", padding=18)
        self.tr_card.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        ttk.Label(self.tr_card, text="Transcription", style="Head.TLabel").pack(anchor="w", pady=(0, 10))
        self.tr_text = tk.Text(self.tr_card, height=16, bd=0, highlightthickness=1)
        self._style_text(self.tr_text)
        self.tr_text.pack(fill="both", expand=True)

        # --- Recommendations card ---
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

        # initialize current mode
        self._on_mode_change()

    # ---------- helpers ----------
    def _style_text(self, widget: tk.Text):
        widget.configure(bg=self.text_bg, fg=self.text_fg, insertbackground=self.text_fg,
                         font=("Consolas", 12), relief="flat", padx=10, pady=10)
        widget.configure(highlightbackground=self.text_border, highlightcolor=self.text_border)

    def _log_status(self, s: str):
        self.after(0, lambda: self.status_var.set(s))

    def _append_text(self, widget: tk.Text, msg: str, newline=True):
        def _do():
            widget.insert(tk.END, msg + ("\n" if newline else ""))
            widget.see(tk.END)
        self.after(0, _do)

    def _toggle_fullscreen(self, on: bool):
        # Button has been removed; keep only keyboard behavior.
        if on:
            self.state('zoomed')
        else:
            self.state('normal')
            self.geometry("1200x780")

    def _on_mode_change(self):
        mode = self.input_mode.get()
        if mode == "Voice":
            # hide text widgets
            self.text_input.pack_forget()
            self.text_input_for_use.pack_forget()
            # enable voice controls
            self.btn_record.state(["!disabled"])
            self.btn_transcribe.state(["!disabled"])
        else:
            # show text widgets
            self.text_input.pack(fill="both", expand=False, pady=(12, 0))
            self.text_input_for_use.pack(fill="x", pady=(12, 0))
            # disable voice controls
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
        stream = self.audio.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                                 input=True, frames_per_buffer=CHUNK)
        while self.is_recording:
            self.frames.append(stream.read(CHUNK, exception_on_overflow=False))
        stream.stop_stream()
        stream.close()
        # after recording stops, enable "Transcribe Now"
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

        # show result
        self._append_text(self.tr_text, f"📝 {txt}", True)

        # allow recommendations / retry
        def _after():
            self.is_processing = False
            self._set_buttons_during_processing(False)
            self.btn_get_reco.state(["!disabled"])
            self.btn_retry.state(["!disabled"])
            self._log_status("Transcription completed")
        self.after(0, _after)

    def _use_text_directly(self):
        """Text mode: take text as 'transcription' and enable recommendations."""
        if self.is_processing or self.input_mode.get() != "Text":
            return
        content = self.text_input.get("1.0", tk.END).strip()
        if not content:
            messagebox.showinfo("Info", "Please type your symptoms first.")
            return
        self.tr_text.delete("1.0", tk.END)
        self._append_text(self.tr_text, f"📝 {content}", True)
        self.btn_get_reco.state(["!disabled"])
        self.btn_retry.state(["!disabled"])
        self._log_status("Text captured")

    # ---------- recommendations flow (placeholder) ----------
    def _get_recommendations(self):
        """Placeholder: later call your real pipeline."""
        text = self.tr_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showinfo("Info", "No transcription available.")
            return
        self.rc_text.delete("1.0", tk.END)
        self._append_text(self.rc_text, "🔎 Analyzing symptoms and preparing recommendations...", True)

        def worker():
            time.sleep(1.0)
            demo = (
                "• Suspected conditions: Migraine, Tension headache\n"
                "• Suggested specialties: Neurology, Internal Medicine\n"
                "• Nearby hospitals (demo): City General Hospital, North Health Center\n"
                "• Next step: click 'Record Again' if the text is inaccurate."
            )
            self._append_text(self.rc_text, demo, True)
            self._log_status("Recommendations ready")
        threading.Thread(target=worker, daemon=True).start()

    def _reset_for_retry(self):
        """Enable user to redo the recording if the transcription was poor."""
        self.frames.clear()
        self.tr_text.delete("1.0", tk.END)
        self.rc_text.delete("1.0", tk.END)
        self.btn_get_reco.state(["disabled"])
        self.btn_retry.state(["disabled"])
        # reset flags
        self.is_recording = False
        self.is_processing = False
        self._set_buttons_during_recording(False)
        self._set_buttons_during_processing(False)
        self._log_status("Ready for a new attempt")

    # ---------- button state helpers ----------
    def _set_buttons_during_recording(self, recording: bool):
        if recording:
            self.btn_record.state(["disabled"])
            self.btn_transcribe.state(["disabled"])  # unlocked when recording stops
            self.mode_combo.state(["disabled"])
            self.lang_combo.state(["disabled"])
        else:
            # enable depending on mode
            if self.input_mode.get() == "Voice":
                self.btn_record.state(["!disabled"])
                self.btn_transcribe.state(["!disabled"])
            else:
                self.btn_record.state(["disabled"])
                self.btn_transcribe.state(["disabled"])
            self.mode_combo.state(["!disabled"])
            self.lang_combo.state(["!disabled"])

    def _set_buttons_during_processing(self, processing: bool):
        states = ["disabled"] if processing else ["!disabled"]
        # while processing: forbid re-entry
        if self.input_mode.get() == "Voice":
            self.btn_record.state(["disabled"] if processing else ["!disabled"])
            self.btn_transcribe.state(states)
        else:
            self.btn_record.state(["disabled"])
            self.btn_transcribe.state(["disabled"])
        self.mode_combo.state(["disabled"] if processing else ["!disabled"])
        self.lang_combo.state(["disabled"] if processing else ["!disabled"])

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
    time.sleep(0.2)  # let UI paint nicely
    app = App()
    app.protocol('WM_DELETE_WINDOW', app.on_close)
    app.mainloop()
