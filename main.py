"""
Nexus Wallet v3.2 - Professional Multi-Chain HD Wallet
Complete UI with real transaction signing, i18n, custom RPC/tokens
"""

import os, time, webbrowser, threading
from datetime import datetime
from tkinter import filedialog
import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont, ImageTk
import qrcode, pyperclip

from wallet_core import (
    WalletManager, SUPPORTED_COINS, COIN_ORDER, ADDRESS_FORMATS,
    HDWalletEngine, _OWN_COINS, get_coin_order, get_coin_explorer,
    L, set_lang, get_available_langs,
)
from blockchain_api import BlockchainAPI
import tx_engine

class TH:
    bg     = "#060b14"
    bg2    = "#0c1120"
    card   = "#111827"
    card2  = "#1a2332"
    inp    = "#0d1321"
    acc    = "#8b5cf6"
    acch   = "#a78bfa"
    accd   = "#1e1346"
    teal   = "#06d6a0"
    teald  = "#082e24"
    gold   = "#fbbf24"
    goldd  = "#2d2510"
    red    = "#ef4444"
    redd   = "#2d1414"
    t1     = "#f1f5f9"
    t2     = "#94a3b8"
    t3     = "#475569"
    t4     = "#1e293b"
    brd    = "#1e293b"
    brd2   = "#334155"

CC = {"BTC":"#f7931a","ETH":"#627eea","BNB":"#f3ba2f","MATIC":"#8247e5",
      "LTC":"#345d9d","DOGE":"#c2a633","BCH":"#8dc351","TRX":"#ff0013",
      "SOL":"#9945ff","USDT":"#26a17b","USDC":"#2775ca"}

FC = {"BIP44":"#ef4444","BIP49":"#f59e0b","BIP84":"#3b82f6","BIP86":"#8b5cf6","SINGLE":"#6b7280"}

VER = "3.2"


class SmoothScroll(ctk.CTkFrame):
    def __init__(self, master, **kw):
        fg = kw.pop("fg_color", "transparent")
        super().__init__(master, fg_color=fg)
        self._canvas = tk.Canvas(self, highlightthickness=0, bd=0, bg="#060b14")
        self._sb = ctk.CTkScrollbar(self, command=self._canvas.yview,
                                     button_color=TH.brd, button_hover_color=TH.brd2)
        self.inner = ctk.CTkFrame(self._canvas, fg_color="transparent")
        self._win = self._canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self._canvas.configure(yscrollcommand=self._sb.set, yscrollincrement=3)
        self._canvas.pack(side="left", fill="both", expand=True)
        self._sb.pack(side="right", fill="y", padx=(0,2))
        self.inner.bind("<Configure>", self._on_inner)
        self._canvas.bind("<Configure>", self._on_canvas)
        self._canvas.bind("<Enter>", self._bind_wheel)
        self._canvas.bind("<Leave>", self._unbind_wheel)

    def _on_inner(self, e):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas(self, e):
        self._canvas.itemconfigure(self._win, width=e.width)

    def _bind_wheel(self, e):
        self._canvas.bind_all("<MouseWheel>", self._wheel)
        self._canvas.bind_all("<Button-4>", self._wup)
        self._canvas.bind_all("<Button-5>", self._wdn)

    def _unbind_wheel(self, e):
        self._canvas.unbind_all("<MouseWheel>")
        self._canvas.unbind_all("<Button-4>")
        self._canvas.unbind_all("<Button-5>")

    def _wheel(self, e):
        self._canvas.yview_scroll(int(-5 * (e.delta / 45)), "units")

    def _wup(self, e): self._canvas.yview_scroll(-6, "units")
    def _wdn(self, e): self._canvas.yview_scroll(6, "units")
    def scroll_top(self): self._canvas.yview_moveto(0)


def fb(b, sym=""):
    if b is None: return "---"
    if b == 0: return "0.00"
    if b < 0.0001: s = f"{b:.8f}"
    elif b < 1: s = f"{b:.6f}"
    elif b < 1000: s = f"{b:.4f}"
    else: s = f"{b:,.2f}"
    return f"{s} {sym}" if sym else s

def fu(v):
    if v is None: return "$---"
    return f"${v:,.2f}" if v >= 0.01 else "$0.00"

def fch(c):
    if c is None: return ""
    return f"+{c:.1f}%" if c >= 0 else f"{c:.1f}%"

def fprice(p):
    if not p: return "$---"
    if p >= 100: return f"${p:,.0f}"
    if p >= 1: return f"${p:,.2f}"
    if p >= 0.001: return f"${p:.4f}"
    return f"${p:.6f}"

def sa(a, n=6):
    if not a: return ""
    return a if len(a) <= n*2+4 else f"{a[:n]}...{a[-n:]}"

def fmt_label(coin, fmt):
    cfg = SUPPORTED_COINS.get(coin, {})
    if cfg.get("format_label", None) == "" or fmt == "SINGLE": return ""
    return ADDRESS_FORMATS.get(fmt, {}).get("name", fmt)

def make_icon(color, sz=40, letter=""):
    img = Image.new("RGBA", (sz*3, sz*3), (0,0,0,0))
    d = ImageDraw.Draw(img)
    r, g, b = int(color[1:3],16), int(color[3:5],16), int(color[5:7],16)
    m = sz * 3
    d.ellipse([4,4,m-5,m-5], fill=(r,g,b,50))
    d.ellipse([m//6, m//6, m-m//6, m-m//6], fill=(r,g,b,220))
    d.ellipse([m//4, m//6, m*3//4, m//3], fill=(255,255,255,30))
    if letter:
        try: f = ImageFont.truetype("arial.ttf", m//3)
        except: f = ImageFont.load_default()
        bb = d.textbbox((0,0), letter, font=f)
        d.text(((m-bb[2]+bb[0])//2, (m-bb[3]+bb[1])//2), letter, fill=(255,255,255,245), font=f)
    img = img.resize((sz, sz), Image.Resampling.LANCZOS)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(sz, sz))

def make_qr(data, sz=200):
    q = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=8, border=2)
    q.add_data(data); q.make(fit=True)
    img = q.make_image(fill_color="#f1f5f9", back_color="#111827").convert("RGBA")
    return ctk.CTkImage(light_image=img.resize((sz,sz), Image.Resampling.LANCZOS),
                        dark_image=img.resize((sz,sz), Image.Resampling.LANCZOS), size=(sz,sz))


class NexusWallet(ctk.CTk):
    def __init__(self):
        super().__init__()

        import os
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_dir, "wallet-ico", "NexusWallet.ico")
        try:
            self.iconbitmap(icon_path) 
        except Exception as e:
            print(f"[WARNING] Failed to load ICO: {e}")
            try:
                ic = Image.new("RGBA",(64,64),(0,0,0,0))
                ImageDraw.Draw(ic).rounded_rectangle([4,4,60,60], radius=14, fill=(139,92,246))
                self.iconphoto(False, ImageTk.PhotoImage(ic))
            except: pass

        self.title("Nexus Wallet")
        self.geometry("1200x820")
        self.minsize(1050, 700)
        self.configure(fg_color=TH.bg)

        self.wm = WalletManager()
        self.api = BlockchainAPI(self.wm.config)
        self.tx_engine = tx_engine.TxEngine(self.wm.config)
        self.bals = {}; self.prices = {}
        self.page = "dashboard"; self._alive = True; self._dl = {}; self._ic = {}
        lang = self.wm.config.get("language", "en")
        set_lang(lang)
        if self.wm.storage.has_wallets(): self._login()
        else: self._welcome()

    def _clr(self):
        self._dl = {}
        for w in self.winfo_children(): w.destroy()

    def _cp(self, t):
        try: pyperclip.copy(t)
        except: self.clipboard_clear(); self.clipboard_append(t)
        self._toast(L("copied"))

    def _toast(self, m, err=False):
        t = ctk.CTkFrame(self, fg_color=TH.teal if not err else TH.red, corner_radius=12)
        t.place(relx=0.5, rely=0.92, anchor="center")
        ctk.CTkLabel(t, text=f"  {chr(10003) if not err else chr(10007)}  {m}  ",
                     font=ctk.CTkFont(size=13,weight="bold"), text_color="white").pack(padx=16, pady=10)
        self.after(2000, lambda: t.destroy() if t.winfo_exists() else None)

    def _icon(self, sym, sz=36):
        k = f"{sym}_{sz}"
        if k not in self._ic:
            cfg = SUPPORTED_COINS.get(sym, {})
            color = cfg.get("color", CC.get(sym, TH.acc))
            self._ic[k] = make_icon(color, sz, cfg.get("icon","?"))
        return self._ic[k]

    def E(self, p, ph="", show=None, w=400, h=46):
        return ctk.CTkEntry(p, placeholder_text=ph, show=show, fg_color=TH.inp,
                            border_color=TH.brd, text_color=TH.t1, placeholder_text_color=TH.t3,
                            height=h, corner_radius=12, width=w, font=ctk.CTkFont(size=14))

    def B(self, p, txt, cmd, pri=True, w=280, h=48):
        return ctk.CTkButton(p, text=txt, command=cmd,
                             fg_color=TH.acc if pri else TH.card2,
                             hover_color=TH.acch if pri else TH.brd2,
                             height=h, corner_radius=12, width=w,
                             font=ctk.CTkFont(size=15, weight="bold"))

    def _card(self, parent, title=None, border_color=None):
        c = ctk.CTkFrame(parent, fg_color=TH.card, corner_radius=16,
                          border_color=border_color or TH.brd, border_width=1)
        c.pack(fill="x", pady=5, padx=2)
        inn = ctk.CTkFrame(c, fg_color="transparent")
        inn.pack(fill="x", padx=22, pady=18)
        if title:
            ctk.CTkLabel(inn, text=title, font=ctk.CTkFont(size=14, weight="bold"),
                         text_color=TH.t1).pack(anchor="w", pady=(0,10))
        return inn

    def _mk_scroll(self, parent=None):
        p = parent or self._ct
        sc = SmoothScroll(p, fg_color="transparent")
        sc.pack(expand=True, fill="both", padx=20, pady=16)
        return sc.inner

    def _ask_password(self, title, prompt, cb):
        d = ctk.CTkToplevel(self); d.title(title); d.geometry("420x230")
        d.configure(fg_color=TH.card); d.transient(self); d.grab_set()
        d.resizable(False,False)
        d.geometry(f"+{self.winfo_x()+(self.winfo_width()-420)//2}+{self.winfo_y()+(self.winfo_height()-230)//2}")
        ctk.CTkLabel(d, text=prompt, font=ctk.CTkFont(size=14), text_color=TH.t2).pack(pady=(25,12))
        pe = self.E(d, L("password"), show=chr(9679), w=320); pe.pack(pady=5); pe.focus()
        st = ctk.CTkLabel(d, text="", font=ctk.CTkFont(size=12), text_color=TH.red); st.pack(pady=3)
        def go():
            pw = pe.get()
            if not pw: st.configure(text=L("enter_pw")); return
            if self.wm.verify_password(pw): d.destroy(); cb(pw)
            else: st.configure(text=L("wrong_pw")); pe.delete(0,"end")
        pe.bind("<Return>", lambda e: go())
        bf = ctk.CTkFrame(d, fg_color="transparent"); bf.pack(pady=10)
        ctk.CTkButton(bf, text=L("cancel"), fg_color=TH.card2, hover_color=TH.brd2,
                      width=120, height=40, corner_radius=10, command=d.destroy).pack(side="left", padx=6)
        ctk.CTkButton(bf, text=L("confirm"), fg_color=TH.acc, hover_color=TH.acch,
                      width=120, height=40, corner_radius=10, command=go).pack(side="left", padx=6)

    def _coin_order(self):
        return get_coin_order(self.wm.config)

    # ---- WELCOME ----
    def _welcome(self):
        self._clr()
        f = ctk.CTkFrame(self, fg_color="transparent"); f.pack(expand=True, fill="both")
        c = ctk.CTkFrame(f, fg_color="transparent"); c.place(relx=0.5, rely=0.46, anchor="center")
        lo = ctk.CTkFrame(c, fg_color=TH.accd, corner_radius=24, width=96, height=96)
        lo.pack(pady=(0,24)); lo.pack_propagate(False)
        ctk.CTkLabel(lo, text="N", font=ctk.CTkFont(size=44, weight="bold"),
                     text_color=TH.acc).place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(c, text=L("app_name"), font=ctk.CTkFont(size=36, weight="bold"),
                     text_color=TH.t1).pack(pady=(0,4))
        ctk.CTkLabel(c, text=L("app_subtitle"), font=ctk.CTkFont(size=14), text_color=TH.t3).pack(pady=(0,36))
        for txt, cmd, pri in [(L("create_wallet"), self._create_scr, True),
                               (L("import_wallet"), self._import_scr, False),
                               (L("restore_backup"), self._restore_scr, False)]:
            self.B(c, f"  {txt}", cmd, pri=pri, w=340).pack(pady=5)
        bf = ctk.CTkFrame(c, fg_color="transparent"); bf.pack(pady=(30,0))
        for sym in COIN_ORDER[:7]:
            ctk.CTkFrame(bf, fg_color=CC.get(sym, TH.t3), corner_radius=4, width=8, height=8).pack(side="left", padx=3)
        ctk.CTkLabel(c, text=f"v{VER} | {len(self._coin_order())} assets | AES-256 | BIP39",
                     font=ctk.CTkFont(size=11), text_color=TH.t4).pack(pady=(8,0))

    # ---- CREATE ----
    def _create_scr(self):
        self._clr()
        sc = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                     scrollbar_button_color=TH.brd, scrollbar_button_hover_color=TH.brd2)
        sc.pack(expand=True, fill="both", padx=50, pady=30)
        try: sc._parent_canvas.configure(yscrollincrement=3)
        except: pass
        hdr = ctk.CTkFrame(sc, fg_color="transparent"); hdr.pack(fill="x", pady=(0,20))
        ctk.CTkButton(hdr, text=L("back"), fg_color="transparent", text_color=TH.t2,
                      hover_color=TH.card2, width=80, corner_radius=8,
                      command=self._welcome if not self.wm.storage.has_wallets() else self._login).pack(side="left")
        ctk.CTkLabel(hdr, text=L("create_wallet"), font=ctk.CTkFont(size=24, weight="bold"),
                     text_color=TH.t1).pack(side="left", padx=20)
        c1 = self._card(sc, L("wallet_name"))
        self._ne = self.E(c1, "My Wallet"); self._ne.pack(fill="x")
        c2 = self._card(sc, L("password"))
        self._p1 = self.E(c2, L("min_8_chars"), show=chr(9679)); self._p1.pack(fill="x", pady=(0,6))
        self._p2 = self.E(c2, L("confirm_password"), show=chr(9679)); self._p2.pack(fill="x", pady=(0,8))
        sf = ctk.CTkFrame(c2, fg_color="transparent"); sf.pack(fill="x")
        ctk.CTkLabel(sf, text=L("seed_strength")+": ", text_color=TH.t2).pack(side="left")
        self._sv = ctk.StringVar(value=L("words_24"))
        ctk.CTkSegmentedButton(sf, values=[L("words_12"), L("words_24")], variable=self._sv,
                               fg_color=TH.inp, selected_color=TH.acc, selected_hover_color=TH.acch,
                               unselected_color=TH.card2, unselected_hover_color=TH.brd2,
                               text_color=TH.t2).pack(side="left", padx=10)
        self._cs = ctk.CTkLabel(sc, text="", font=ctk.CTkFont(size=13), text_color=TH.red); self._cs.pack(pady=8)
        self.B(sc, f"  {L('generate_wallet')}", self._do_create, w=340).pack(pady=6)

    def _do_create(self):
        nm = self._ne.get().strip() or "My Wallet"
        pw, pw2 = self._p1.get(), self._p2.get()
        if len(pw) < 8: self._cs.configure(text=L("pw_too_short")); return
        if pw != pw2: self._cs.configure(text=L("passwords_dont_match")); return
        st = 128 if "12" in self._sv.get() else 256
        self._cs.configure(text=L("generating"), text_color=TH.teal); self.update()
        ok, mn, _ = self.wm.create_wallet(pw, name=nm, strength=st)
        if ok: self._seed_scr(mn)
        else: self._cs.configure(text=str(mn), text_color=TH.red)

    def _seed_scr(self, mn):
        self._clr()
        sc = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                     scrollbar_button_color=TH.brd, scrollbar_button_hover_color=TH.brd2)
        sc.pack(expand=True, fill="both", padx=50, pady=30)
        try: sc._parent_canvas.configure(yscrollincrement=3)
        except: pass
        w = ctk.CTkFrame(sc, fg_color=TH.redd, corner_radius=14, border_color="#5c2020", border_width=1)
        w.pack(fill="x", pady=(0,16))
        wi = ctk.CTkFrame(w, fg_color="transparent"); wi.pack(padx=20, pady=14)
        ctk.CTkLabel(wi, text=L("backup_warning"), font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=TH.red).pack(anchor="w")
        ctk.CTkLabel(wi, text=L("backup_desc"), font=ctk.CTkFont(size=12),
                     text_color="#e08080", wraplength=600).pack(anchor="w")
        mc = ctk.CTkFrame(sc, fg_color=TH.card, corner_radius=14, border_color=TH.brd, border_width=1)
        mc.pack(fill="x", pady=6)
        wg = ctk.CTkFrame(mc, fg_color="transparent"); wg.pack(padx=18, pady=18)
        words = mn.split()
        for i, word in enumerate(words):
            r, col = i // 4, i % 4
            wf = ctk.CTkFrame(wg, fg_color=TH.inp, corner_radius=10); wf.grid(row=r, column=col, padx=4, pady=3, sticky="ew")
            wg.columnconfigure(col, weight=1)
            inn = ctk.CTkFrame(wf, fg_color="transparent"); inn.pack(padx=10, pady=8)
            ctk.CTkLabel(inn, text=f"{i+1}", font=ctk.CTkFont(size=10), text_color=TH.t3, width=20).pack(side="left")
            ctk.CTkLabel(inn, text=word, font=ctk.CTkFont(size=14, weight="bold", family="Consolas"),
                         text_color=TH.t1).pack(side="left")
        ctk.CTkButton(sc, text=L("copy_phrase"), fg_color=TH.card2, hover_color=TH.brd2, height=38,
                      corner_radius=10, width=140, command=lambda: self._cp(mn)).pack(pady=8)
        self._bkok = ctk.BooleanVar()
        ctk.CTkCheckBox(sc, text=f"  {L('confirm_backup')}", variable=self._bkok,
                        fg_color=TH.acc, hover_color=TH.acch, border_color=TH.brd,
                        text_color=TH.t1).pack(pady=12)
        self.B(sc, f"  {L('open_wallet')}", lambda: self._main() if self._bkok.get() else self._toast(L("confirm_backup_err"), err=True)).pack(pady=6)

    # ---- IMPORT ----
    def _import_scr(self):
        self._clr()
        sc = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                     scrollbar_button_color=TH.brd, scrollbar_button_hover_color=TH.brd2)
        sc.pack(expand=True, fill="both", padx=50, pady=30)
        try: sc._parent_canvas.configure(yscrollincrement=3)
        except: pass
        hdr = ctk.CTkFrame(sc, fg_color="transparent"); hdr.pack(fill="x", pady=(0,20))
        ctk.CTkButton(hdr, text=L("back"), fg_color="transparent", text_color=TH.t2,
                      hover_color=TH.card2, width=80, corner_radius=8,
                      command=self._welcome if not self.wm.storage.has_wallets() else self._login).pack(side="left")
        ctk.CTkLabel(hdr, text=L("import_wallet"), font=ctk.CTkFont(size=24, weight="bold"),
                     text_color=TH.t1).pack(side="left", padx=20)
        c1 = self._card(sc, "Recovery Phrase")
        self._imn = ctk.CTkTextbox(c1, height=90, fg_color=TH.inp, border_color=TH.brd,
                                    text_color=TH.t1, font=ctk.CTkFont(size=14, family="Consolas"),
                                    corner_radius=10, border_width=1); self._imn.pack(fill="x")
        c2 = self._card(sc, "Setup")
        self._inm = self.E(c2, L("wallet_name")); self._inm.pack(fill="x", pady=(0,6))
        self._ip1 = self.E(c2, L("password"), show=chr(9679)); self._ip1.pack(fill="x", pady=(0,6))
        self._ip2 = self.E(c2, L("confirm_password"), show=chr(9679)); self._ip2.pack(fill="x")
        self._is = ctk.CTkLabel(sc, text="", font=ctk.CTkFont(size=13), text_color=TH.red); self._is.pack(pady=8)
        self.B(sc, f"  {L('import_btn')}", self._do_import, w=340).pack(pady=6)

    def _do_import(self):
        mn = self._imn.get("1.0","end").strip(); nm = self._inm.get().strip() or "Imported"
        pw, pw2 = self._ip1.get(), self._ip2.get()
        if not mn: self._is.configure(text=L("invalid_phrase")); return
        if len(pw) < 8: self._is.configure(text=L("pw_too_short")); return
        if pw != pw2: self._is.configure(text=L("passwords_dont_match")); return
        self._is.configure(text=L("importing"), text_color=TH.teal); self.update()
        ok, msg, _ = self.wm.create_wallet(pw, mnemonic=mn, name=nm)
        if ok: self._main()
        else: self._is.configure(text=str(msg), text_color=TH.red)

    # ---- RESTORE ----
    def _restore_scr(self):
        path = filedialog.askopenfilename(filetypes=[("Nexus Backup","*.nxbk"),("All","*.*")])
        if not path: return
        self._clr()
        sc = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                     scrollbar_button_color=TH.brd, scrollbar_button_hover_color=TH.brd2)
        sc.pack(expand=True, fill="both", padx=50, pady=30)
        try: sc._parent_canvas.configure(yscrollincrement=3)
        except: pass
        hdr = ctk.CTkFrame(sc, fg_color="transparent"); hdr.pack(fill="x", pady=(0,20))
        ctk.CTkButton(hdr, text=L("back"), fg_color="transparent", text_color=TH.t2,
                      hover_color=TH.card2, width=80, corner_radius=8, command=self._welcome).pack(side="left")
        ctk.CTkLabel(hdr, text=L("restore_backup"), font=ctk.CTkFont(size=24, weight="bold"),
                     text_color=TH.t1).pack(side="left", padx=20)
        c1 = self._card(sc, "File"); ctk.CTkLabel(c1, text=os.path.basename(path), text_color=TH.teal).pack(anchor="w")
        c2 = self._card(sc, "Backup Password"); rp = self.E(c2, L("password"), show=chr(9679)); rp.pack(fill="x")
        c3 = self._card(sc, "New Password (optional)")
        np1 = self.E(c3, "New password", show=chr(9679)); np1.pack(fill="x", pady=(0,6))
        np2 = self.E(c3, L("confirm_password"), show=chr(9679)); np2.pack(fill="x")
        st = ctk.CTkLabel(sc, text="", text_color=TH.red); st.pack(pady=8)
        def do_r():
            pw = rp.get()
            if not pw: st.configure(text=L("enter_pw")); return
            wd = self.wm.storage.import_backup(path, pw)
            if not wd: st.configure(text=L("wrong_pw")); return
            npw = np1.get()
            if npw:
                if len(npw)<8: st.configure(text=L("pw_too_short")); return
                if npw!=np2.get(): st.configure(text=L("passwords_dont_match")); return
                fpw = npw
            else: fpw = pw
            ok,_,_ = self.wm.create_wallet(fpw, mnemonic=wd.get("mnemonic",""), name=wd.get("name","Restored"))
            if ok: self._main()
            else: st.configure(text="Failed")
        self.B(sc, f"  {L('restore_btn')}", do_r, w=340).pack(pady=6)

    # ---- LOGIN ----
    def _login(self):
        self._clr()
        f = ctk.CTkFrame(self, fg_color="transparent"); f.pack(expand=True, fill="both")
        c = ctk.CTkFrame(f, fg_color="transparent"); c.place(relx=0.5, rely=0.46, anchor="center")
        lo = ctk.CTkFrame(c, fg_color=TH.accd, corner_radius=18, width=72, height=72)
        lo.pack(pady=(0,16)); lo.pack_propagate(False)
        ctk.CTkLabel(lo, text="N", font=ctk.CTkFont(size=32, weight="bold"),
                     text_color=TH.acc).place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(c, text=L("welcome_back"), font=ctk.CTkFont(size=28, weight="bold"), text_color=TH.t1).pack(pady=(0,4))
        wallets = self.wm.get_wallet_list()
        if len(wallets) > 1:
            self._sel = ctk.StringVar(value=wallets[0]["id"])
            wn = [f"{w['name']}  ({w['id'][:6]}...)" for w in wallets]
            self._wmap = dict(zip(wn, [w["id"] for w in wallets]))
            ctk.CTkOptionMenu(c, variable=ctk.StringVar(value=wn[0]), values=wn,
                              fg_color=TH.inp, button_color=TH.acc, dropdown_fg_color=TH.card,
                              text_color=TH.t1, width=360, height=44, corner_radius=10,
                              command=lambda v: self._sel.set(self._wmap[v])).pack(pady=(12,4))
        else:
            self._sel = ctk.StringVar(value=wallets[0]["id"] if wallets else "")
        self._lp = self.E(c, L("password"), show=chr(9679), w=360, h=48); self._lp.pack(pady=(12,4))
        self._lp.bind("<Return>", lambda e: self._do_login())
        self._ls = ctk.CTkLabel(c, text="", text_color=TH.red); self._ls.pack(pady=4)
        self.B(c, f"  {L('unlock')}", self._do_login, w=360).pack(pady=8)
        bf = ctk.CTkFrame(c, fg_color="transparent"); bf.pack(pady=(16,0))
        for txt, cmd in [("+ Create", self._create_scr), ("Import", self._import_scr), ("Restore", self._restore_scr)]:
            ctk.CTkButton(bf, text=txt, font=ctk.CTkFont(size=12), fg_color="transparent",
                          text_color=TH.acc, hover_color=TH.card2, height=32, corner_radius=8, command=cmd).pack(side="left", padx=6)
        self._lp.focus()

    def _do_login(self):
        pw = self._lp.get(); wid = self._sel.get()
        if not pw: self._ls.configure(text=L("enter_pw")); return
        self._ls.configure(text=L("unlocking"), text_color=TH.teal); self.update()
        if self.wm.unlock_wallet(wid, pw):
            self.api.set_config(self.wm.config); self.tx_engine.set_config(self.wm.config); self._main()
        else: self._ls.configure(text=L("wrong_pw"), text_color=TH.red); self._lp.delete(0,"end")

    # ---- MAIN LAYOUT ----
    def _main(self):
        self._clr()
        mf = ctk.CTkFrame(self, fg_color="transparent"); mf.pack(expand=True, fill="both")
        sb = ctk.CTkFrame(mf, fg_color=TH.bg2, width=200, corner_radius=0)
        sb.pack(side="left", fill="y"); sb.pack_propagate(False)
        sh = ctk.CTkFrame(sb, fg_color="transparent"); sh.pack(fill="x", padx=14, pady=(18,24))
        lo = ctk.CTkFrame(sh, fg_color=TH.acc, corner_radius=10, width=32, height=32)
        lo.pack(side="left"); lo.pack_propagate(False)
        ctk.CTkLabel(lo, text="N", font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="white").place(relx=0.5, rely=0.5, anchor="center")
        wn = self.wm.wallet_data.get("name","Wallet") if self.wm.wallet_data else "Wallet"
        ctk.CTkLabel(sh, text=wn, font=ctk.CTkFont(size=14, weight="bold"), text_color=TH.t1).pack(side="left", padx=10)
        self._nb = {}
        navs = [("dashboard",L("dashboard"),"#"), ("portfolio",L("portfolio"),"="),
                ("paths",L("derivation"),"+"), ("send",L("send"),">"), ("receive",L("receive"),"<"),
                ("history",L("history"),"~"), ("contacts",L("contacts"),"@"),
                ("security",L("security"),"!"), ("settings",L("settings"),"*")]
        for key, label, icon in navs:
            row = ctk.CTkFrame(sb, fg_color="transparent", height=40)
            row.pack(fill="x", padx=4, pady=1); row.pack_propagate(False)
            bar = ctk.CTkFrame(row, fg_color="transparent", width=3, corner_radius=2)
            bar.pack(side="left", fill="y")
            btn = ctk.CTkButton(row, text=f"  {label}", font=ctk.CTkFont(size=13),
                                fg_color="transparent", text_color=TH.t2,
                                hover_color=TH.card2, height=38, corner_radius=10, anchor="w",
                                command=lambda k=key: self._nav(k))
            btn.pack(fill="both", expand=True, padx=(2,6))
            self._nb[key] = {"btn": btn, "bar": bar}
        ctk.CTkFrame(sb, fg_color="transparent").pack(expand=True)
        wc = self.wm.storage.wallet_count()
        if wc > 1:
            ctk.CTkButton(sb, text=f"{L('switch_wallet')} ({wc})", font=ctk.CTkFont(size=11),
                          fg_color="transparent", text_color=TH.teal, hover_color=TH.card2,
                          height=30, command=lambda: [self.wm.lock_wallet(), self._login()]).pack(fill="x", padx=8, pady=1)
        ctk.CTkButton(sb, text=L("lock"), font=ctk.CTkFont(size=11),
                      fg_color="transparent", text_color=TH.t3, hover_color=TH.card2,
                      height=30, command=self._lock).pack(fill="x", padx=8, pady=(1,14))
        self._ct = ctk.CTkFrame(mf, fg_color="transparent")
        self._ct.pack(side="left", expand=True, fill="both")
        self._nav("dashboard")
        self._auto()

    def _nav(self, pg):
        self.page = pg; self.wm.update_activity(); self._dl = {}
        for k, v in self._nb.items():
            active = k == pg
            v["btn"].configure(fg_color=TH.accd if active else "transparent", text_color=TH.acc if active else TH.t2)
            v["bar"].configure(fg_color=TH.acc if active else "transparent")
        for w in self._ct.winfo_children(): w.destroy()
        pages = {"dashboard":self._pg_dash, "portfolio":self._pg_port, "paths":self._pg_paths,
                 "send":self._pg_send, "receive":self._pg_recv, "history":self._pg_hist,
                 "contacts":self._pg_cont, "security":self._pg_sec, "settings":self._pg_set}
        pages.get(pg, lambda: None)()

    def _lock(self): self.wm.lock_wallet(); self._alive = False; self._login()

    # ---- DASHBOARD ----
    def _pg_dash(self):
        sc = self._mk_scroll()
        top = ctk.CTkFrame(sc, fg_color="transparent"); top.pack(fill="x", pady=(0,14))
        ctk.CTkLabel(top, text=L("dashboard"), font=ctk.CTkFont(size=22, weight="bold"), text_color=TH.t1).pack(side="left")
        ctk.CTkButton(top, text=L("refresh"), font=ctk.CTkFont(size=12), fg_color=TH.card2, hover_color=TH.brd2, height=34, corner_radius=8, width=90, command=self._refresh).pack(side="right")
        hero = ctk.CTkFrame(sc, fg_color=TH.card, corner_radius=20, border_color=TH.brd, border_width=1, height=130)
        hero.pack(fill="x", pady=(0,14)); hero.pack_propagate(False)
        hip = ctk.CTkFrame(hero, fg_color="transparent"); hip.pack(fill="both", expand=True, padx=28, pady=22)
        ctk.CTkLabel(hip, text=L("total_balance"), font=ctk.CTkFont(size=11, weight="bold"), text_color=TH.t3).pack(anchor="w")
        self._tl = ctk.CTkLabel(hip, text="$0.00", font=ctk.CTkFont(size=38, weight="bold"), text_color=TH.t1); self._tl.pack(anchor="w", pady=(2,0))
        ctk.CTkLabel(hip, text=f"{len(self._coin_order())} {L('assets_tracked')}", font=ctk.CTkFont(size=12), text_color=TH.t3).pack(anchor="w")
        qa = ctk.CTkFrame(sc, fg_color="transparent"); qa.pack(fill="x", pady=(0,14))
        for txt, pg, fg, hv in [(L("quick_send"),"send",TH.acc,TH.acch),(L("quick_recv"),"receive",TH.teal,"#05b890"),(L("quick_derive"),"paths",TH.card2,TH.brd2)]:
            ctk.CTkButton(qa, text=txt, font=ctk.CTkFont(size=13, weight="bold"), fg_color=fg, hover_color=hv, height=42, corner_radius=12, width=145, command=lambda p=pg: self._nav(p)).pack(side="left", padx=(0,8))
        ctk.CTkLabel(sc, text=L("assets"), font=ctk.CTkFont(size=11, weight="bold"), text_color=TH.t3).pack(anchor="w", pady=(4,8), padx=4)
        self._cf = ctk.CTkFrame(sc, fg_color="transparent"); self._cf.pack(fill="x")
        addrs = self.wm.get_all_active_addresses()
        for sym in self._coin_order():
            if sym in addrs: self._mk_coin_row(sym, addrs[sym])
        self._refresh()

    def _mk_coin_row(self, sym, addr):
        cfg = SUPPORTED_COINS.get(sym, {})
        color = cfg.get("color", CC.get(sym, TH.acc))
        row = ctk.CTkFrame(self._cf, fg_color=TH.card, corner_radius=12, border_color=TH.brd, border_width=1, height=72)
        row.pack(fill="x", pady=2); row.pack_propagate(False)
        strip = ctk.CTkFrame(row, fg_color=color, width=4, corner_radius=2)
        strip.pack(side="left", fill="y", pady=8)
        inn = ctk.CTkFrame(row, fg_color="transparent"); inn.pack(fill="both", expand=True, padx=(14,18), pady=10)
        lf = ctk.CTkFrame(inn, fg_color="transparent"); lf.pack(side="left")
        ic = self._icon(sym, 36)
        ctk.CTkLabel(lf, image=ic, text="").pack(side="left", padx=(0,10))
        nf = ctk.CTkFrame(lf, fg_color="transparent"); nf.pack(side="left")
        nr = ctk.CTkFrame(nf, fg_color="transparent"); nr.pack(anchor="w")
        ctk.CTkLabel(nr, text=cfg.get("name",sym), font=ctk.CTkFont(size=14, weight="bold"), text_color=TH.t1).pack(side="left")
        ctk.CTkLabel(nr, text=f"  {sym}", font=ctk.CTkFont(size=11), text_color=TH.t3).pack(side="left")
        tags = []
        if cfg.get("is_token"): tags.append("ERC-20")
        elif cfg.get("is_evm"): tags.append("EVM")
        if cfg.get("is_custom"): tags.append("Custom")
        if tags: ctk.CTkLabel(nf, text=" | ".join(tags), font=ctk.CTkFont(size=9), text_color=TH.t3).pack(anchor="w")
        pl = ctk.CTkLabel(nf, text="", font=ctk.CTkFont(size=11), text_color=TH.t3); pl.pack(anchor="w")
        rt = ctk.CTkFrame(inn, fg_color="transparent"); rt.pack(side="right")
        bl = ctk.CTkLabel(rt, text="---", font=ctk.CTkFont(size=14, weight="bold"), text_color=TH.t1); bl.pack(anchor="e")
        vl = ctk.CTkLabel(rt, text="$---", font=ctk.CTkFont(size=12), text_color=TH.t2); vl.pack(anchor="e")
        cl = ctk.CTkLabel(rt, text="", font=ctk.CTkFont(size=10), text_color=TH.t3); cl.pack(anchor="e")
        self._dl[sym] = {"b": bl, "v": vl, "c": cl, "p": pl}

    # ---- PORTFOLIO ----
    def _pg_port(self):
        sc = self._mk_scroll()
        ctk.CTkLabel(sc, text=L("portfolio"), font=ctk.CTkFont(size=22, weight="bold"), text_color=TH.t1).pack(anchor="w", pady=(0,14))
        for sym in self._coin_order():
            cfg = SUPPORTED_COINS.get(sym, {})
            has_own = cfg.get("has_own_key", False)
            cd = ctk.CTkFrame(sc, fg_color=TH.card, corner_radius=14, border_color=TH.brd, border_width=1); cd.pack(fill="x", pady=4)
            inn = ctk.CTkFrame(cd, fg_color="transparent"); inn.pack(fill="x", padx=20, pady=14)
            hdr = ctk.CTkFrame(inn, fg_color="transparent"); hdr.pack(fill="x")
            ic = self._icon(sym, 40); ctk.CTkLabel(hdr, image=ic, text="").pack(side="left", padx=(0,12))
            info = ctk.CTkFrame(hdr, fg_color="transparent"); info.pack(side="left", fill="x", expand=True)
            hn = ctk.CTkFrame(info, fg_color="transparent"); hn.pack(anchor="w")
            ctk.CTkLabel(hn, text=cfg.get("name",sym), font=ctk.CTkFont(size=16, weight="bold"), text_color=TH.t1).pack(side="left")
            ctk.CTkLabel(hn, text=f"  {sym}", font=ctk.CTkFont(size=12), text_color=TH.t3).pack(side="left")
            bal = self.bals.get(sym); pr = self.prices.get(sym, 0)
            usd = (bal*pr) if bal and pr else None
            ctk.CTkLabel(info, text=f"{fb(bal, sym)}  |  {fu(usd)}", font=ctk.CTkFont(size=13), text_color=TH.t2).pack(anchor="w")
            if has_own:
                all_f = self.wm.get_all_formats_for_coin(sym)
                sel = self.wm.get_selected_format(sym)
                for fk, fd in all_f.items():
                    if "error" in fd: continue
                    addr = fd.get("address","N/A"); fl = fmt_label(sym, fk); is_sel = fk==sel
                    fco = FC.get(fk, TH.t3)
                    af = ctk.CTkFrame(inn, fg_color=TH.inp if is_sel else "transparent", corner_radius=10, border_color=fco if is_sel else TH.brd, border_width=2 if is_sel else 0)
                    af.pack(fill="x", pady=(6,0))
                    ai = ctk.CTkFrame(af, fg_color="transparent"); ai.pack(fill="x", padx=12, pady=8)
                    trow = ctk.CTkFrame(ai, fg_color="transparent"); trow.pack(fill="x")
                    if fl: ctk.CTkLabel(trow, text=fl, font=ctk.CTkFont(size=11, weight="bold"), text_color=fco).pack(side="left")
                    if is_sel: ctk.CTkLabel(trow, text=f"  Active", font=ctk.CTkFont(size=10), text_color=TH.teal).pack(side="left")
                    ps = fd.get("path","")
                    if ps: ctk.CTkLabel(trow, text=f"  {ps}", font=ctk.CTkFont(size=10, family="Consolas"), text_color=TH.t3).pack(side="left")
                    ctk.CTkLabel(ai, text=addr, font=ctk.CTkFont(size=12, family="Consolas"), text_color=TH.t2).pack(anchor="w", pady=(2,0))
                    bf = ctk.CTkFrame(ai, fg_color="transparent"); bf.pack(anchor="w", pady=(4,0))
                    ctk.CTkButton(bf, text="Copy", width=55, height=24, corner_radius=6, font=ctk.CTkFont(size=10), fg_color=TH.card2, hover_color=TH.brd2, command=lambda a=addr: self._cp(a)).pack(side="left", padx=(0,4))
                    if not is_sel and len(all_f)>1:
                        ctk.CTkButton(bf, text="Set Active", width=70, height=24, corner_radius=6, font=ctk.CTkFont(size=10), fg_color=TH.acc, hover_color=TH.acch, command=lambda s=sym,f=fk: [self.wm.set_selected_format(s,f), self._nav("portfolio")]).pack(side="left")
            else:
                addr = self.wm.get_address(sym) or "N/A"
                parent = cfg.get("shares_address_with", "")
                af = ctk.CTkFrame(inn, fg_color=TH.inp, corner_radius=10); af.pack(fill="x", pady=(6,0))
                ai = ctk.CTkFrame(af, fg_color="transparent"); ai.pack(fill="x", padx=12, pady=8)
                if parent: ctk.CTkLabel(ai, text=L("shared_with", parent=parent), font=ctk.CTkFont(size=10), text_color=TH.t3).pack(anchor="w")
                ctk.CTkLabel(ai, text=addr, font=ctk.CTkFont(size=12, family="Consolas"), text_color=TH.t2).pack(anchor="w", pady=(2,0))
                ctk.CTkButton(ai, text="Copy", width=55, height=24, corner_radius=6, font=ctk.CTkFont(size=10), fg_color=TH.card2, hover_color=TH.brd2, command=lambda a=addr: self._cp(a)).pack(anchor="w", pady=(4,0))

    # ---- DERIVATION ----
    def _pg_paths(self):
        sc = self._mk_scroll()
        ctk.CTkLabel(sc, text=L("derive_title"), font=ctk.CTkFont(size=22, weight="bold"), text_color=TH.t1).pack(anchor="w", pady=(0,6))
        ctk.CTkLabel(sc, text=L("derive_subtitle"), font=ctk.CTkFont(size=12), text_color=TH.t3).pack(anchor="w", pady=(0,10))
        cd = self._card(sc, L("derive_new"))
        own_coins = [s for s in self._coin_order() if SUPPORTED_COINS.get(s,{}).get("has_own_key")]
        r1 = ctk.CTkFrame(cd, fg_color="transparent"); r1.pack(fill="x", pady=4)
        ctk.CTkLabel(r1, text=L("coin"), text_color=TH.t2, width=65).pack(side="left")
        self._dp_c = ctk.StringVar(value="BTC")
        ctk.CTkOptionMenu(r1, variable=self._dp_c, values=own_coins, fg_color=TH.inp, button_color=TH.acc, dropdown_fg_color=TH.card, text_color=TH.t1, width=100, height=38, corner_radius=8, command=self._upd_dp).pack(side="left", padx=4)
        ctk.CTkLabel(r1, text=L("format"), text_color=TH.t2, width=55).pack(side="left", padx=(10,0))
        self._dp_f = ctk.StringVar(value="BIP84")
        self._dp_fm = ctk.CTkOptionMenu(r1, variable=self._dp_f, values=["BIP84"], fg_color=TH.inp, button_color=TH.acc, dropdown_fg_color=TH.card, text_color=TH.t1, width=180, height=38, corner_radius=8)
        self._dp_fm.pack(side="left", padx=4)
        r2 = ctk.CTkFrame(cd, fg_color="transparent"); r2.pack(fill="x", pady=4)
        ctk.CTkLabel(r2, text=L("account"), text_color=TH.t2, width=65).pack(side="left")
        self._dp_a = self.E(r2, "0", w=80, h=36); self._dp_a.pack(side="left", padx=4); self._dp_a.insert(0,"0")
        ctk.CTkLabel(r2, text=L("index"), text_color=TH.t2, width=50).pack(side="left", padx=(10,0))
        self._dp_i = self.E(r2, "0", w=80, h=36); self._dp_i.pack(side="left", padx=4); self._dp_i.insert(0,"0")
        self._dp_pv = ctk.CTkLabel(cd, text="", font=ctk.CTkFont(size=12, family="Consolas"), text_color=TH.t3); self._dp_pv.pack(anchor="w", pady=(6,0))
        self._dp_st = ctk.CTkLabel(cd, text="", font=ctk.CTkFont(size=12)); self._dp_st.pack(anchor="w", pady=2)
        bf = ctk.CTkFrame(cd, fg_color="transparent"); bf.pack(anchor="w", pady=(6,0))
        ctk.CTkButton(bf, text=L("preview"), width=90, height=36, corner_radius=8, fg_color=TH.card2, hover_color=TH.brd2, command=self._pv_path).pack(side="left", padx=(0,6))
        ctk.CTkButton(bf, text=L("add"), width=100, height=36, corner_radius=8, fg_color=TH.acc, hover_color=TH.acch, command=self._add_path).pack(side="left")
        self._upd_dp()
        ctk.CTkLabel(sc, text=L("custom_addresses"), font=ctk.CTkFont(size=11, weight="bold"), text_color=TH.t3).pack(anchor="w", pady=(16,8), padx=4)
        has = False
        for sym in own_coins:
            customs = self.wm.get_custom_addresses(sym)
            if not customs: continue
            has = True
            ctk.CTkLabel(sc, text=SUPPORTED_COINS[sym].get("name",sym), font=ctk.CTkFont(size=14, weight="bold"), text_color=CC.get(sym, TH.acc)).pack(anchor="w", pady=(8,3))
            for ad in customs:
                af = ctk.CTkFrame(sc, fg_color=TH.card, corner_radius=10, border_color=TH.brd, border_width=1); af.pack(fill="x", pady=2)
                ai = ctk.CTkFrame(af, fg_color="transparent"); ai.pack(fill="x", padx=12, pady=8)
                ctk.CTkLabel(ai, text=ad.get("path",""), font=ctk.CTkFont(size=12, family="Consolas"), text_color=TH.t2).pack(anchor="w")
                ctk.CTkLabel(ai, text=ad.get("address",""), font=ctk.CTkFont(size=11, family="Consolas"), text_color=TH.t1).pack(anchor="w", pady=(2,0))
                br = ctk.CTkFrame(ai, fg_color="transparent"); br.pack(anchor="w", pady=(4,0))
                ctk.CTkButton(br, text="Copy", width=50, height=24, corner_radius=6, fg_color=TH.card2, hover_color=TH.brd2, font=ctk.CTkFont(size=10), command=lambda a=ad.get("address",""): self._cp(a)).pack(side="left", padx=(0,4))
                ctk.CTkButton(br, text=L("remove"), width=60, height=24, corner_radius=6, fg_color=TH.red, hover_color="#cc4444", font=ctk.CTkFont(size=10), command=lambda s=sym,p=ad.get("path",""): [self.wm.remove_derived_address(s,p),self._nav("paths")]).pack(side="left")
        if not has: ctk.CTkLabel(sc, text=L("no_custom"), font=ctk.CTkFont(size=13), text_color=TH.t3).pack(anchor="w")

    def _upd_dp(self, *a):
        c = self._dp_c.get()
        fmts = list(_OWN_COINS.get(c, {}).get("formats", {}).keys())
        labels = [f"{f} | {ADDRESS_FORMATS[f]['name']}" if f!="SINGLE" else "Standard" for f in fmts]
        self._dp_fm.configure(values=labels)
        if labels: self._dp_f.set(labels[0])

    def _get_dp(self):
        c = self._dp_c.get(); f = self._dp_f.get().split(" |")[0].strip()
        if f == "Standard": f = "SINGLE"
        try: a = int(self._dp_a.get())
        except: a = 0
        try: i = int(self._dp_i.get())
        except: i = 0
        return c, f, a, i

    def _pv_path(self):
        c, f, a, i = self._get_dp()
        ad = self.wm.derive_custom_address(c, f, a, i)
        if ad: self._dp_pv.configure(text=f"{ad['path']}  ->  {ad['address']}"); self._dp_st.configure(text="")
        else: self._dp_st.configure(text="Failed", text_color=TH.red)

    def _add_path(self):
        c, f, a, i = self._get_dp()
        ad = self.wm.add_derived_address(c, f, a, i)
        if ad: self._dp_st.configure(text="Added!", text_color=TH.teal); self.after(400, lambda: self._nav("paths"))
        else: self._dp_st.configure(text="Failed", text_color=TH.red)

    # ---- SEND ----
    def _pg_send(self):
        sc = self._mk_scroll()
        ctk.CTkLabel(sc, text=L("send"), font=ctk.CTkFont(size=22, weight="bold"), text_color=TH.t1).pack(anchor="w", pady=(0,14))
        cd = self._card(sc)
        ctk.CTkLabel(cd, text=L("coin"), font=ctk.CTkFont(size=12), text_color=TH.t3).pack(anchor="w", pady=(0,4))
        self._sc = ctk.StringVar(value="BTC")
        ctk.CTkOptionMenu(cd, variable=self._sc, values=self._coin_order(), fg_color=TH.inp, button_color=TH.acc, dropdown_fg_color=TH.card, text_color=TH.t1, width=300, height=42, corner_radius=10, command=self._usb).pack(anchor="w", pady=(0,8))
        self._sbl = ctk.CTkLabel(cd, text=f"{L('available')}: ---", font=ctk.CTkFont(size=12), text_color=TH.t3); self._sbl.pack(anchor="w", pady=(0,12))
        ctk.CTkLabel(cd, text=L("recipient"), font=ctk.CTkFont(size=12), text_color=TH.t3).pack(anchor="w", pady=(0,4))
        self._sa = self.E(cd, L("address"), w=500); self._sa.pack(anchor="w", pady=(0,12))
        ctk.CTkLabel(cd, text=L("amount"), font=ctk.CTkFont(size=12), text_color=TH.t3).pack(anchor="w", pady=(0,4))
        af = ctk.CTkFrame(cd, fg_color="transparent"); af.pack(anchor="w", pady=(0,12))
        self._sam = self.E(af, "0.00", w=300); self._sam.pack(side="left", padx=(0,8))
        ctk.CTkButton(af, text="MAX", width=60, height=46, corner_radius=10, fg_color=TH.card2, hover_color=TH.brd2, text_color=TH.teal, command=lambda: [self._sam.delete(0,"end"), self._sam.insert(0,str(self.bals.get(self._sc.get(),0) or 0))]).pack(side="left")
        # Fee speed selector
        ctk.CTkLabel(cd, text=L("fee_speed"), font=ctk.CTkFont(size=12), text_color=TH.t3).pack(anchor="w", pady=(8,4))
        self._sfl = ctk.StringVar(value="medium")
        ff = ctk.CTkFrame(cd, fg_color="transparent"); ff.pack(anchor="w", pady=(0,4))
        for val, lbl, clr in [("low", L("fee_low"), TH.t3), ("medium", L("fee_medium"), TH.teal), ("high", L("fee_high"), TH.gold)]:
            ctk.CTkRadioButton(ff, text=lbl, variable=self._sfl, value=val, text_color=clr, fg_color=TH.acc, border_color=TH.brd, hover_color=TH.acch, command=self._update_fee_preview).pack(side="left", padx=(0,18))
        # Custom fee row
        cf = ctk.CTkFrame(cd, fg_color="transparent"); cf.pack(anchor="w", pady=(2,4))
        ctk.CTkRadioButton(cf, text=L("fee_custom"), variable=self._sfl, value="custom", text_color=TH.t2, fg_color=TH.acc, border_color=TH.brd, hover_color=TH.acch, command=self._update_fee_preview).pack(side="left", padx=(0,8))
        self._cfe = self.E(cf, "", w=100); self._cfe.pack(side="left", padx=(0,6))
        self._cfe_unit = ctk.CTkLabel(cf, text="Gwei / sat/vB", font=ctk.CTkFont(size=11), text_color=TH.t3)
        self._cfe_unit.pack(side="left")
        self._fee_lbl = ctk.CTkLabel(cd, text="", font=ctk.CTkFont(size=11), text_color=TH.t3); self._fee_lbl.pack(anchor="w", pady=(0,8))
        # Warning
        w = ctk.CTkFrame(cd, fg_color=TH.goldd, corner_radius=10); w.pack(fill="x", pady=(0,12))
        ctk.CTkLabel(w, text=L("verify_addr_warn"), font=ctk.CTkFont(size=12), text_color=TH.gold, wraplength=440).pack(padx=14, pady=10)
        self._ss = ctk.CTkLabel(cd, text="", font=ctk.CTkFont(size=13)); self._ss.pack(pady=4)
        self.B(cd, f"  {L('review_tx')}", self._rev_send, w=260).pack(anchor="w")
        self._usb()

    def _usb(self, *a):
        self._sbl.configure(text=f"{L('available')}: {fb(self.bals.get(self._sc.get()), self._sc.get())}")
        # Update custom fee unit label
        co = self._sc.get()
        if co in ("ETH","BNB","MATIC","USDT","USDC"): self._cfe_unit.configure(text="Gwei")
        elif co == "BTC": self._cfe_unit.configure(text="sat/vB")
        elif co == "SOL": self._cfe_unit.configure(text="lamports")
        elif co in ("LTC","DOGE"): self._cfe_unit.configure(text="sat/byte")
        else: self._cfe_unit.configure(text="Gwei")
        self._update_fee_preview()

    def _update_fee_preview(self, *a):
        """Show estimated fee below the speed selector."""
        try:
            co = self._sc.get(); fl = self._sfl.get()
            if fl == "custom":
                cv = self._cfe.get().strip()
                if cv:
                    try: fl = float(cv)
                    except ValueError: self._fee_lbl.configure(text="Invalid custom value"); return
                else:
                    self._fee_lbl.configure(text="Enter custom value"); return
            fee_val, fee_unit = self.tx_engine.estimate_fee(co, 0, fl)
            if fee_val is not None and fee_val > 0:
                self._fee_lbl.configure(text=f"≈ {fee_val:.8f} {fee_unit}")
            else:
                self._fee_lbl.configure(text=f"≈ free / {fee_unit}")
        except Exception:
            self._fee_lbl.configure(text="")

    def _rev_send(self):
        co = self._sc.get(); ad = self._sa.get().strip(); am = self._sam.get().strip()
        fl = self._sfl.get()
        # Handle custom fee
        if fl == "custom":
            cv = self._cfe.get().strip()
            if not cv:
                self._ss.configure(text="Enter custom fee value", text_color=TH.red); return
            try: fl = float(cv)
            except ValueError:
                self._ss.configure(text="Invalid custom fee value", text_color=TH.red); return
        if not ad:
            self._ss.configure(text="Enter recipient address", text_color=TH.red); return
        # Validate address format
        valid, addr_err = self.tx_engine.validate_address(co, ad)
        if not valid:
            self._ss.configure(text=L("invalid_address", coin=co) + f" ({addr_err})", text_color=TH.red); return
        try: a = float(am); assert a > 0
        except: self._ss.configure(text="Invalid amount", text_color=TH.red); return
        # Check balance
        bal = self.bals.get(co, 0) or 0
        if a > bal:
            self._ss.configure(text=L("insufficient_bal") + f" ({bal} {co})", text_color=TH.red); return
        # Check library available
        ok, dep = self.tx_engine.check_deps(co)
        if not ok:
            self._ss.configure(text=f"{L('missing_lib')}: pip install {dep}", text_color=TH.red); return
        # Estimate fee with selected level
        fee_val, fee_unit = self.tx_engine.estimate_fee(co, a, fl)
        fee_txt = f"{fee_val:.8f} {fee_unit}" if fee_val is not None else "~"
        speed_names = {"low": L("fee_low"), "medium": L("fee_medium"), "high": L("fee_high")}
        speed_display = speed_names.get(fl, f"Custom ({fl})" if not isinstance(fl, str) else fl)
        # Dialog
        d = ctk.CTkToplevel(self); d.title(L("confirm_tx")); d.geometry("480x470"); d.configure(fg_color=TH.card)
        d.transient(self); d.grab_set(); d.resizable(False,False)
        d.geometry(f"+{self.winfo_x()+(self.winfo_width()-480)//2}+{self.winfo_y()+(self.winfo_height()-470)//2}")
        ctk.CTkLabel(d, text=L("confirm_tx"), font=ctk.CTkFont(size=18, weight="bold"), text_color=TH.t1).pack(pady=(20,12))
        det = ctk.CTkFrame(d, fg_color=TH.inp, corner_radius=12); det.pack(fill="x", padx=22, pady=4)
        di = ctk.CTkFrame(det, fg_color="transparent"); di.pack(padx=16, pady=12)
        cfg = SUPPORTED_COINS.get(co, {})
        for l,v in [(L("coin"), cfg.get("name",co)), (L("to"), sa(ad,14)), (L("amount"), f"{a} {co}"), (L("network_fee"), fee_txt), (L("fee_speed"), speed_display)]:
            r = ctk.CTkFrame(di, fg_color="transparent"); r.pack(fill="x", pady=2)
            ctk.CTkLabel(r, text=l, text_color=TH.t3, width=100).pack(side="left")
            ctk.CTkLabel(r, text=v, font=ctk.CTkFont(weight="bold"), text_color=TH.t1).pack(side="left")
        # Warning
        wf = ctk.CTkFrame(d, fg_color="#2d1a0e", corner_radius=10); wf.pack(fill="x", padx=22, pady=8)
        ctk.CTkLabel(wf, text=L("tx_real_warning"), font=ctk.CTkFont(size=12, weight="bold"), text_color=TH.gold, wraplength=400).pack(padx=14, pady=8)
        # Password
        ctk.CTkLabel(d, text=L("enter_pw_send"), text_color=TH.t3, font=ctk.CTkFont(size=12)).pack(pady=(4,2))
        pw_e = ctk.CTkEntry(d, show="●", width=300, height=42, fg_color=TH.inp, border_color=TH.brd, text_color=TH.t1, corner_radius=10, placeholder_text=L("password"))
        pw_e.pack(pady=(0,6))
        # Status
        st_lbl = ctk.CTkLabel(d, text="", font=ctk.CTkFont(size=12)); st_lbl.pack(pady=2)
        # Buttons
        bf = ctk.CTkFrame(d, fg_color="transparent"); bf.pack(pady=8)
        ctk.CTkButton(bf, text=L("cancel"), fg_color=TH.card2, hover_color=TH.brd2, width=130, height=40, corner_radius=10, command=d.destroy).pack(side="left", padx=5)
        cbtn = ctk.CTkButton(bf, text=L("confirm"), fg_color=TH.teal, hover_color="#05b890", width=130, height=40, corner_radius=10,
                             command=lambda: self._exec_send(d, co, ad, a, pw_e.get(), st_lbl, cbtn, fl))
        cbtn.pack(side="left", padx=5)

    def _exec_send(self, dlg, coin, to_addr, amount, pw, status, btn, fee_level="medium"):
        if not self.wm.verify_password(pw):
            status.configure(text=L("wrong_pw"), text_color=TH.red); return
        btn.configure(state="disabled", text=L("sending"))
        status.configure(text=L("signing_tx"), text_color=TH.gold)
        self.update_idletasks()
        pk = self.wm.get_private_key(coin)
        if not pk:
            status.configure(text="Key error", text_color=TH.red)
            btn.configure(state="normal", text=L("confirm")); return
        from_addr = self.wm.get_address(coin)
        def do():
            result = self.tx_engine.send(coin, pk, to_addr, amount, fee_level=fee_level, from_address=from_addr)
            self.after(0, lambda: self._send_done(dlg, coin, amount, to_addr, result, status, btn))
        threading.Thread(target=do, daemon=True).start()

    def _send_done(self, dlg, coin, amount, to_addr, result, status, btn):
        if result.success:
            self.wm.add_tx(coin, result.tx_hash, "send", str(amount), to_addr, "confirmed")
            dlg.destroy()
            self._ss.configure(text=f"{L('tx_success')} {result.tx_hash[:24]}...", text_color=TH.teal)
            if result.explorer_url:
                self._show_tx_ok(result)
        else:
            status.configure(text=f"✗ {result.error[:80]}", text_color=TH.red)
            btn.configure(state="normal", text=L("confirm"))

    def _show_tx_ok(self, result):
        d = ctk.CTkToplevel(self); d.title(L("tx_success")); d.geometry("500x240"); d.configure(fg_color=TH.card)
        d.transient(self); d.grab_set(); d.resizable(False,False)
        d.geometry(f"+{self.winfo_x()+(self.winfo_width()-500)//2}+{self.winfo_y()+(self.winfo_height()-240)//2}")
        ctk.CTkLabel(d, text="✓", font=ctk.CTkFont(size=42), text_color=TH.teal).pack(pady=(16,4))
        ctk.CTkLabel(d, text=L("tx_success"), font=ctk.CTkFont(size=16, weight="bold"), text_color=TH.t1).pack(pady=4)
        hf = ctk.CTkFrame(d, fg_color=TH.inp, corner_radius=10); hf.pack(fill="x", padx=20, pady=6)
        ctk.CTkLabel(hf, text=result.tx_hash[:40]+"..." if len(result.tx_hash)>40 else result.tx_hash, text_color=TH.t2, font=ctk.CTkFont(size=11, family="Courier")).pack(padx=12, pady=8)
        bf = ctk.CTkFrame(d, fg_color="transparent"); bf.pack(pady=10)
        ctk.CTkButton(bf, text=L("view_explorer"), fg_color=TH.acc, hover_color=TH.acch, width=150, height=38, corner_radius=10,
                      command=lambda: webbrowser.open(result.explorer_url)).pack(side="left", padx=4)
        ctk.CTkButton(bf, text=L("copy_hash"), fg_color=TH.card2, hover_color=TH.brd2, width=120, height=38, corner_radius=10,
                      command=lambda: [self._cp(result.tx_hash), d.destroy()]).pack(side="left", padx=4)
        ctk.CTkButton(bf, text="OK", fg_color=TH.teal, hover_color="#05b890", width=80, height=38, corner_radius=10, command=d.destroy).pack(side="left", padx=4)

    # ---- RECEIVE ----
    def _pg_recv(self):
        sc = self._mk_scroll()
        ctk.CTkLabel(sc, text=L("receive"), font=ctk.CTkFont(size=22, weight="bold"), text_color=TH.t1).pack(anchor="w", pady=(0,14))
        sf = ctk.CTkFrame(sc, fg_color="transparent"); sf.pack(anchor="w", pady=(0,8))
        ctk.CTkLabel(sf, text=L("coin"), text_color=TH.t3).pack(side="left", padx=(0,8))
        self._rc = ctk.StringVar(value="BTC")
        ctk.CTkOptionMenu(sf, variable=self._rc, values=self._coin_order(), fg_color=TH.inp, button_color=TH.acc, dropdown_fg_color=TH.card, text_color=TH.t1, width=130, height=38, corner_radius=8, command=self._ur).pack(side="left", padx=(0,12))
        ctk.CTkLabel(sf, text=L("format"), text_color=TH.t3).pack(side="left", padx=(0,8))
        self._rf = ctk.StringVar(value="BIP84")
        self._rfm = ctk.CTkOptionMenu(sf, variable=self._rf, values=["BIP84"], fg_color=TH.inp, button_color=TH.acc, dropdown_fg_color=TH.card, text_color=TH.t1, width=200, height=38, corner_radius=8, command=self._ur)
        self._rfm.pack(side="left")
        self._rd = ctk.CTkFrame(sc, fg_color=TH.card, corner_radius=16, border_color=TH.brd, border_width=1); self._rd.pack(fill="x", pady=6)
        self._ur()

    def _ur(self, *a):
        coin = self._rc.get()
        cfg = SUPPORTED_COINS.get(coin, {})
        has_own = cfg.get("has_own_key", False)
        if has_own:
            fmts = list(_OWN_COINS.get(coin, {}).get("formats", {}).keys())
            labels = [f"{f} | {ADDRESS_FORMATS[f]['name']}" if f!="SINGLE" else "Standard" for f in fmts]
        else:
            fmts = ["SINGLE"]; labels = ["Standard"]
        self._rfm.configure(values=labels)
        cur = self._rf.get().split(" |")[0].strip()
        if cur not in fmts: self._rf.set(labels[0])
        fk = self._rf.get().split(" |")[0].strip()
        if fk == "Standard": fk = "SINGLE"
        addr = self.wm.get_address(coin, fk if has_own else None) or "N/A"
        fl = fmt_label(coin, fk) if has_own else ""
        for w in self._rd.winfo_children(): w.destroy()
        inn = ctk.CTkFrame(self._rd, fg_color="transparent"); inn.pack(padx=28, pady=22)
        hdr = ctk.CTkFrame(inn, fg_color="transparent"); hdr.pack(pady=(0,14))
        ic = self._icon(coin, 44); ctk.CTkLabel(hdr, image=ic, text="").pack(side="left", padx=(0,12))
        title = f"{L('receive')} {cfg.get('name', coin)}" + (f" | {fl}" if fl else "")
        ctk.CTkLabel(hdr, text=title, font=ctk.CTkFont(size=18, weight="bold"), text_color=TH.t1).pack(side="left")
        if addr != "N/A":
            qr = make_qr(addr, 200); ctk.CTkLabel(inn, image=qr, text="").pack(pady=6)
        if has_own:
            all_f = self.wm.get_all_formats_for_coin(coin)
            ps = all_f.get(fk, {}).get("path", "")
            if ps: ctk.CTkLabel(inn, text=ps, font=ctk.CTkFont(size=11, family="Consolas"), text_color=TH.t3).pack(pady=(0,4))
        elif cfg.get("shares_address_with"):
            ctk.CTkLabel(inn, text=f"{L('shared_with', parent=cfg['shares_address_with'])} | m/44'/60'/0'/0/0", font=ctk.CTkFont(size=11, family="Consolas"), text_color=TH.t3).pack(pady=(0,4))
        af = ctk.CTkFrame(inn, fg_color=TH.inp, corner_radius=10); af.pack(fill="x", pady=6)
        ctk.CTkLabel(af, text=addr, font=ctk.CTkFont(size=13, family="Consolas"), text_color=TH.t1, wraplength=400).pack(padx=14, pady=10)
        bf = ctk.CTkFrame(inn, fg_color="transparent"); bf.pack(pady=8)
        exp_url = get_coin_explorer(coin, self.wm.config)
        ctk.CTkButton(bf, text=L("copy_address"), fg_color=TH.acc, hover_color=TH.acch, height=40, corner_radius=10, width=150, command=lambda: self._cp(addr)).pack(side="left", padx=4)
        ctk.CTkButton(bf, text=L("explorer"), fg_color=TH.card2, hover_color=TH.brd2, height=40, corner_radius=10, width=150, command=lambda: webbrowser.open(exp_url.format(addr)) if exp_url else None).pack(side="left", padx=4)
        ctk.CTkLabel(inn, text=L("only_send_to", name=cfg.get("name",coin), sym=coin), font=ctk.CTkFont(size=12), text_color=TH.gold).pack(pady=(10,0))

    # ---- HISTORY ----
    def _pg_hist(self):
        sc = self._mk_scroll()
        ctk.CTkLabel(sc, text=L("history"), font=ctk.CTkFont(size=22, weight="bold"), text_color=TH.t1).pack(anchor="w", pady=(0,14))
        hist = self.wm.get_tx_history()
        if not hist:
            e = ctk.CTkFrame(sc, fg_color=TH.card, corner_radius=14, height=160); e.pack(fill="x", pady=14); e.pack_propagate(False)
            ctk.CTkLabel(e, text=L("no_tx"), font=ctk.CTkFont(size=14), text_color=TH.t3).place(relx=0.5, rely=0.5, anchor="center")
            return
        for tx in hist[:50]:
            cd = ctk.CTkFrame(sc, fg_color=TH.card, corner_radius=10, border_color=TH.brd, border_width=1); cd.pack(fill="x", pady=2)
            inn = ctk.CTkFrame(cd, fg_color="transparent"); inn.pack(fill="x", padx=14, pady=10)
            is_s = tx.get("type")=="send"; coin = tx.get("coin","?")
            inf = ctk.CTkFrame(inn, fg_color="transparent"); inf.pack(side="left", expand=True, fill="x")
            ctk.CTkLabel(inf, text=f"{L('sent') if is_s else L('received')} {coin}", font=ctk.CTkFont(size=14, weight="bold"), text_color=TH.t1).pack(anchor="w")
            ts = tx.get("timestamp",0); t_s = datetime.fromtimestamp(ts).strftime("%b %d | %H:%M") if ts else ""
            ctk.CTkLabel(inf, text=f"{sa(tx.get('to',''),8)}  {t_s}", font=ctk.CTkFont(size=11), text_color=TH.t3).pack(anchor="w")
            ctk.CTkLabel(inn, text=f"{'-' if is_s else '+'}{tx.get('amount','0')} {coin}", font=ctk.CTkFont(size=14, weight="bold"), text_color=TH.red if is_s else TH.teal).pack(side="right")

    # ---- CONTACTS ----
    def _pg_cont(self):
        sc = self._mk_scroll()
        top = ctk.CTkFrame(sc, fg_color="transparent"); top.pack(fill="x", pady=(0,14))
        ctk.CTkLabel(top, text=L("contacts"), font=ctk.CTkFont(size=22, weight="bold"), text_color=TH.t1).pack(side="left")
        ctk.CTkButton(top, text=L("add_contact"), fg_color=TH.acc, hover_color=TH.acch, height=34, corner_radius=10, width=120, command=self._add_ct).pack(side="right")
        cts = self.wm.get_contacts()
        if not cts:
            e = ctk.CTkFrame(sc, fg_color=TH.card, corner_radius=14, height=120); e.pack(fill="x", pady=14); e.pack_propagate(False)
            ctk.CTkLabel(e, text=L("no_contacts"), font=ctk.CTkFont(size=14), text_color=TH.t3).place(relx=0.5, rely=0.5, anchor="center"); return
        for ct in cts:
            cd = ctk.CTkFrame(sc, fg_color=TH.card, corner_radius=10, border_color=TH.brd, border_width=1); cd.pack(fill="x", pady=2)
            inn = ctk.CTkFrame(cd, fg_color="transparent"); inn.pack(fill="x", padx=14, pady=10)
            ctk.CTkLabel(inn, text=f"{ct['name']} | {ct.get('coin','')}", font=ctk.CTkFont(size=14, weight="bold"), text_color=TH.t1).pack(anchor="w")
            ctk.CTkLabel(inn, text=sa(ct.get("address",""),12), font=ctk.CTkFont(size=11, family="Consolas"), text_color=TH.t3).pack(anchor="w")
            bf = ctk.CTkFrame(inn, fg_color="transparent"); bf.pack(anchor="w", pady=(4,0))
            ctk.CTkButton(bf, text="Copy", width=50, height=24, corner_radius=6, fg_color=TH.card2, hover_color=TH.brd2, font=ctk.CTkFont(size=10), command=lambda a=ct["address"]: self._cp(a)).pack(side="left", padx=(0,4))
            ctk.CTkButton(bf, text="X", width=28, height=24, corner_radius=6, fg_color=TH.card2, hover_color=TH.red, text_color=TH.red, command=lambda cid=ct["id"]: [self.wm.remove_contact(cid), self._nav("contacts")]).pack(side="left")

    def _add_ct(self):
        d = ctk.CTkToplevel(self); d.title(L("add_contact")); d.geometry("420x280"); d.configure(fg_color=TH.card)
        d.transient(self); d.grab_set(); d.resizable(False,False)
        d.geometry(f"+{self.winfo_x()+(self.winfo_width()-420)//2}+{self.winfo_y()+(self.winfo_height()-280)//2}")
        ctk.CTkLabel(d, text=L("add_contact"), font=ctk.CTkFont(size=18, weight="bold"), text_color=TH.t1).pack(pady=(18,12))
        f = ctk.CTkFrame(d, fg_color="transparent"); f.pack(padx=22, fill="x")
        ne = self.E(f, L("name"), w=370); ne.pack(fill="x", pady=3)
        cv = ctk.StringVar(value="BTC")
        ctk.CTkOptionMenu(f, variable=cv, values=self._coin_order(), fg_color=TH.inp, button_color=TH.acc, dropdown_fg_color=TH.card, text_color=TH.t1, width=370, height=42, corner_radius=10).pack(fill="x", pady=3)
        ae = self.E(f, L("address"), w=370); ae.pack(fill="x", pady=3)
        def sv():
            if ne.get().strip() and ae.get().strip():
                self.wm.add_contact(ne.get().strip(), ae.get().strip(), cv.get()); d.destroy(); self._nav("contacts")
        ctk.CTkButton(d, text=L("save"), fg_color=TH.acc, hover_color=TH.acch, height=40, width=180, corner_radius=10, command=sv).pack(pady=14)

    # ---- SECURITY ----
    def _pg_sec(self):
        sc = self._mk_scroll()
        ctk.CTkLabel(sc, text=L("security"), font=ctk.CTkFont(size=22, weight="bold"), text_color=TH.t1).pack(anchor="w", pady=(0,14))
        c1 = self._card(sc, L("recovery_phrase"))
        ctk.CTkLabel(c1, text=L("pw_required"), font=ctk.CTkFont(size=12), text_color=TH.t3).pack(anchor="w", pady=(0,8))
        self._mn_fr = ctk.CTkFrame(c1, fg_color="transparent")
        ctk.CTkButton(c1, text=L("show_phrase"), fg_color=TH.red, hover_color="#cc4444", height=36, corner_radius=10, width=240, command=self._show_mn).pack(anchor="w")
        c2 = self._card(sc, L("private_keys"))
        ctk.CTkLabel(c2, text=L("never_share"), font=ctk.CTkFont(size=12), text_color=TH.red).pack(anchor="w", pady=(0,6))
        pr = ctk.CTkFrame(c2, fg_color="transparent"); pr.pack(anchor="w", pady=(0,6))
        self._pkc = ctk.StringVar(value="BTC")
        ctk.CTkOptionMenu(pr, variable=self._pkc, values=self._coin_order(), fg_color=TH.inp, button_color=TH.acc, dropdown_fg_color=TH.card, text_color=TH.t1, width=110, height=36, corner_radius=8).pack(side="left", padx=(0,6))
        self._pkl = ctk.CTkLabel(c2, text="****************", font=ctk.CTkFont(size=12, family="Consolas"), text_color=TH.t4); self._pkl.pack(anchor="w", pady=4)
        ctk.CTkButton(c2, text=L("show_key"), fg_color=TH.red, hover_color="#cc4444", height=36, corner_radius=10, width=240, command=self._show_pk).pack(anchor="w")
        c3 = self._card(sc, L("change_password"))
        self._op = self.E(c3, L("current_pw"), show=chr(9679), w=340); self._op.pack(anchor="w", pady=3)
        self._np = self.E(c3, L("new_pw"), show=chr(9679), w=340); self._np.pack(anchor="w", pady=3)
        self._np2 = self.E(c3, L("confirm_new_pw"), show=chr(9679), w=340); self._np2.pack(anchor="w", pady=3)
        self._pst = ctk.CTkLabel(c3, text="", font=ctk.CTkFont(size=12)); self._pst.pack(anchor="w", pady=3)
        ctk.CTkButton(c3, text=L("change_btn"), fg_color=TH.acc, hover_color=TH.acch, height=36, corner_radius=10, width=160, command=self._do_cpw).pack(anchor="w")
        c4 = self._card(sc, L("backup_title"))
        ctk.CTkButton(c4, text=L("export_backup"), fg_color=TH.acc, hover_color=TH.acch, height=36, corner_radius=10, width=280, command=self._export_bk).pack(anchor="w")

    def _show_mn(self):
        def on(pw):
            mn = self.wm.get_mnemonic()
            if not mn: return
            for w in self._mn_fr.winfo_children(): w.destroy()
            wg = ctk.CTkFrame(self._mn_fr, fg_color=TH.inp, corner_radius=10); wg.pack(fill="x", pady=4)
            for i, word in enumerate(mn.split()):
                ctk.CTkLabel(wg, text=f"{i+1}. {word}", font=ctk.CTkFont(size=13, weight="bold", family="Consolas"), text_color=TH.t1, width=115).grid(row=i//4, column=i%4, padx=5, pady=2, sticky="w")
            bf = ctk.CTkFrame(self._mn_fr, fg_color="transparent"); bf.pack(pady=4)
            ctk.CTkButton(bf, text="Copy", fg_color=TH.card2, hover_color=TH.brd2, height=28, width=70, corner_radius=8, command=lambda: self._cp(mn)).pack(side="left", padx=2)
            ctk.CTkButton(bf, text="Hide", fg_color=TH.red, hover_color="#cc4444", height=28, width=70, corner_radius=8, command=lambda: [self._mn_fr.pack_forget(), [w.destroy() for w in self._mn_fr.winfo_children()]]).pack(side="left", padx=2)
            self._mn_fr.pack(fill="x", pady=6)
        self._ask_password(L("verify_identity"), L("enter_pw"), on)

    def _show_pk(self):
        def on(pw):
            pk = self.wm.get_private_key(self._pkc.get())
            if pk:
                self._pkl.configure(text=pk, text_color=TH.t1)
                self.after(30000, lambda: self._pkl.configure(text="****************", text_color=TH.t4) if self._pkl.winfo_exists() else None)
        self._ask_password(L("verify_identity"), L("enter_pw"), on)

    def _do_cpw(self):
        o, n, n2 = self._op.get(), self._np.get(), self._np2.get()
        if len(n)<8: self._pst.configure(text=L("pw_too_short"), text_color=TH.red); return
        if n!=n2: self._pst.configure(text=L("passwords_dont_match"), text_color=TH.red); return
        if self.wm.change_password(o, n):
            self._pst.configure(text=L("pw_changed"), text_color=TH.teal)
            self._op.delete(0,"end"); self._np.delete(0,"end"); self._np2.delete(0,"end")
        else: self._pst.configure(text=L("wrong_pw"), text_color=TH.red)

    def _export_bk(self):
        def on(pw):
            path = filedialog.asksaveasfilename(defaultextension=".nxbk", filetypes=[("Nexus Backup","*.nxbk")], initialfile=f"nexus_{datetime.now().strftime('%Y%m%d_%H%M')}.nxbk")
            if path:
                if self.wm.storage.export_backup(self.wm.active_wallet_id, pw, path): self._toast(L("backup_saved"))
                else: self._toast("Failed", err=True)
        self._ask_password(L("backup_title"), L("enter_pw"), on)

    # ---- SETTINGS ----
    def _pg_set(self):
        sc = self._mk_scroll()
        ctk.CTkLabel(sc, text=L("settings"), font=ctk.CTkFont(size=22, weight="bold"), text_color=TH.t1).pack(anchor="w", pady=(0,14))
        # Language
        c_lang = self._card(sc, L("language"))
        langs = get_available_langs()
        lang_names = {"en": "English"}
        cur_lang = self.wm.config.get("language", "en")
        r = ctk.CTkFrame(c_lang, fg_color="transparent"); r.pack(fill="x")
        ctk.CTkLabel(r, text=L("language"), text_color=TH.t2, width=90).pack(side="left")
        ctk.CTkOptionMenu(r, variable=ctk.StringVar(value=lang_names.get(cur_lang, cur_lang)), values=[lang_names.get(l, l) for l in langs], fg_color=TH.inp, button_color=TH.acc, dropdown_fg_color=TH.card, text_color=TH.t1, width=160, height=36, corner_radius=8, command=lambda v: self._change_lang(v, lang_names, langs)).pack(side="left", padx=8)
        ctk.CTkLabel(c_lang, text="Adding new languages: edit STRINGS dict in wallet_core.py", font=ctk.CTkFont(size=10), text_color=TH.t4).pack(anchor="w", pady=(6,0))
        # Formats
        c0 = self._card(sc, L("active_formats"))
        for sym in self._coin_order():
            cfg = SUPPORTED_COINS.get(sym, {})
            if not cfg.get("has_own_key"): continue
            fmts = list(_OWN_COINS.get(sym, {}).get("formats", {}).keys())
            if len(fmts) <= 1: continue
            row = ctk.CTkFrame(c0, fg_color="transparent"); row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=cfg.get("name",sym), font=ctk.CTkFont(size=13, weight="bold"), text_color=TH.t2, width=85).pack(side="left")
            sel = self.wm.get_selected_format(sym)
            for fmt in fmts:
                is_a = fmt == sel; fco = FC.get(fmt, TH.t3)
                ctk.CTkButton(row, text=ADDRESS_FORMATS[fmt]["name"], font=ctk.CTkFont(size=11), width=100, height=32, corner_radius=8, fg_color=fco if is_a else TH.inp, hover_color=fco, text_color="white" if is_a else TH.t3, command=lambda s=sym,f=fmt: [self.wm.set_selected_format(s,f), self._nav("settings")]).pack(side="left", padx=3)
        # Custom RPC
        c_rpc = self._card(sc, L("custom_rpc"))
        ctk.CTkLabel(c_rpc, text="Override RPC and Explorer for any coin (privacy/custom nodes)", font=ctk.CTkFont(size=11), text_color=TH.t3, wraplength=500).pack(anchor="w", pady=(0,8))
        rpc_coin_var = ctk.StringVar(value="BTC")
        rpc_row = ctk.CTkFrame(c_rpc, fg_color="transparent"); rpc_row.pack(fill="x", pady=4)
        ctk.CTkLabel(rpc_row, text=L("coin"), text_color=TH.t2, width=50).pack(side="left")
        ctk.CTkOptionMenu(rpc_row, variable=rpc_coin_var, values=self._coin_order(), fg_color=TH.inp, button_color=TH.acc, dropdown_fg_color=TH.card, text_color=TH.t1, width=120, height=36, corner_radius=8, command=lambda v: self._load_rpc(v, rpc_e, exp_e)).pack(side="left", padx=6)
        rpc_e = self.E(c_rpc, L("rpc_url"), w=500, h=38); rpc_e.pack(fill="x", pady=3)
        exp_e = self.E(c_rpc, L("explorer_url")+" (use {} for address)", w=500, h=38); exp_e.pack(fill="x", pady=3)
        rpc_btn = ctk.CTkFrame(c_rpc, fg_color="transparent"); rpc_btn.pack(anchor="w", pady=6)
        ctk.CTkButton(rpc_btn, text=L("save_rpc"), fg_color=TH.acc, hover_color=TH.acch, height=34, corner_radius=8, width=100, command=lambda: self._save_rpc(rpc_coin_var.get(), rpc_e.get().strip(), exp_e.get().strip())).pack(side="left", padx=(0,6))
        ctk.CTkButton(rpc_btn, text=L("reset_rpc"), fg_color=TH.card2, hover_color=TH.brd2, height=34, corner_radius=8, width=100, command=lambda: [self.wm.reset_custom_rpc(rpc_coin_var.get()), self._toast("Reset!"), self._load_rpc(rpc_coin_var.get(), rpc_e, exp_e)]).pack(side="left")
        overrides = self.wm.config.get("custom_rpc", {})
        if overrides:
            ctk.CTkLabel(c_rpc, text="Current overrides:", font=ctk.CTkFont(size=11, weight="bold"), text_color=TH.t3).pack(anchor="w", pady=(8,2))
            for sym_o, vals in overrides.items():
                if vals.get("rpc") or vals.get("explorer"):
                    parts = []
                    if vals.get("rpc"): parts.append(f"RPC: {vals['rpc'][:40]}...")
                    if vals.get("explorer"): parts.append(f"Exp: {vals['explorer'][:40]}...")
                    ctk.CTkLabel(c_rpc, text=f"  {sym_o}: {' | '.join(parts)}", font=ctk.CTkFont(size=10, family="Consolas"), text_color=TH.t3).pack(anchor="w")
        # Custom Tokens
        c_tok = self._card(sc, L("custom_tokens"))
        ctk.CTkLabel(c_tok, text="Add EVM coins or ERC-20 tokens sharing the ETH address", font=ctk.CTkFont(size=11), text_color=TH.t3, wraplength=500).pack(anchor="w", pady=(0,8))
        custom = self.wm.config.get("custom_coins", {})
        if custom:
            for sym_c, cfg_c in custom.items():
                tf = ctk.CTkFrame(c_tok, fg_color=TH.inp, corner_radius=8); tf.pack(fill="x", pady=2)
                ti = ctk.CTkFrame(tf, fg_color="transparent"); ti.pack(fill="x", padx=10, pady=6)
                ctk.CTkLabel(ti, text=f"{cfg_c.get('icon','?')} {sym_c} | {cfg_c.get('name',sym_c)} | {cfg_c.get('type','evm')}", font=ctk.CTkFont(size=12, weight="bold"), text_color=TH.t1).pack(side="left")
                ctk.CTkButton(ti, text=L("remove_token"), width=60, height=24, corner_radius=6, fg_color=TH.red, hover_color="#cc4444", font=ctk.CTkFont(size=10), command=lambda s=sym_c: [self.wm.remove_custom_coin(s), self._nav("settings")]).pack(side="right")
        ctk.CTkButton(c_tok, text=L("add_token"), fg_color=TH.acc, hover_color=TH.acch, height=36, corner_radius=10, width=200, command=self._add_token_dlg).pack(anchor="w", pady=(8,0))
        # Display
        c1 = self._card(sc, L("display"))
        r1 = ctk.CTkFrame(c1, fg_color="transparent"); r1.pack(fill="x", pady=3)
        ctk.CTkLabel(r1, text=L("currency"), text_color=TH.t2, width=90).pack(side="left")
        ctk.CTkOptionMenu(r1, variable=ctk.StringVar(value=self.wm.config.get("currency","USD")), values=["USD","EUR","GBP","JPY","CAD","AUD"], fg_color=TH.inp, button_color=TH.acc, dropdown_fg_color=TH.card, text_color=TH.t1, width=130, height=36, corner_radius=8, command=lambda v: self._scfg("currency",v)).pack(side="left")
        # AutoLock
        c2 = self._card(sc, L("auto_lock"))
        r2 = ctk.CTkFrame(c2, fg_color="transparent"); r2.pack(fill="x", pady=3)
        ctk.CTkLabel(r2, text=L("timeout"), text_color=TH.t2, width=90).pack(side="left")
        ctk.CTkOptionMenu(r2, variable=ctk.StringVar(value=str(self.wm.config.get("auto_lock",300))), values=["60","120","300","600","0"], fg_color=TH.inp, button_color=TH.acc, dropdown_fg_color=TH.card, text_color=TH.t1, width=130, height=36, corner_radius=8, command=lambda v: self._scfg("auto_lock",int(v))).pack(side="left")
        ctk.CTkLabel(r2, text=L("sec_never"), font=ctk.CTkFont(size=11), text_color=TH.t3).pack(side="left", padx=8)
        # Wallets
        c3 = self._card(sc, L("wallets"))
        for w_info in self.wm.get_wallet_list():
            wr = ctk.CTkFrame(c3, fg_color=TH.inp, corner_radius=8); wr.pack(fill="x", pady=2)
            wi = ctk.CTkFrame(wr, fg_color="transparent"); wi.pack(fill="x", padx=10, pady=6)
            is_a = w_info["id"] == self.wm.active_wallet_id
            ctk.CTkLabel(wi, text=f"{w_info['name']}" + (f" | {L('active')}" if is_a else ""), font=ctk.CTkFont(size=13, weight="bold" if is_a else "normal"), text_color=TH.teal if is_a else TH.t1).pack(side="left")
            if not is_a:
                ctk.CTkButton(wi, text=L("delete"), width=55, height=24, corner_radius=6, fg_color=TH.red, hover_color="#cc4444", font=ctk.CTkFont(size=10), command=lambda wid=w_info["id"]: [self.wm.storage.delete_wallet(wid), self._nav("settings")]).pack(side="right")
        ctk.CTkButton(c3, text=L("new_wallet"), fg_color=TH.acc, hover_color=TH.acch, height=34, width=150, corner_radius=10, command=self._create_scr).pack(anchor="w", pady=(8,0))
        # About
        c4 = self._card(sc, L("about"))
        ctk.CTkLabel(c4, text=f"Nexus Wallet v{VER}\n{len(self._coin_order())} assets | BIP39/44/49/84/86 HD\nAES-256 | PBKDF2 480K\nOpen Source | MIT License", font=ctk.CTkFont(size=12), text_color=TH.t2, justify="left").pack(anchor="w")

    def _change_lang(self, dn, nm, langs):
        rev = {v: k for k, v in nm.items()}
        code = rev.get(dn, dn)
        set_lang(code)
        self.wm.config["language"] = code; self.wm.save_config()
        self._main()

    def _load_rpc(self, sym, re, ee):
        custom = self.wm.get_custom_rpc(sym)
        re.delete(0, "end"); ee.delete(0, "end")
        if custom.get("rpc"): re.insert(0, custom["rpc"])
        if custom.get("explorer"): ee.insert(0, custom["explorer"])

    def _save_rpc(self, sym, rpc, exp):
        self.wm.set_custom_rpc(sym, rpc, exp)
        self.api.set_config(self.wm.config)
        self._toast(f"{sym} RPC saved!")

    def _add_token_dlg(self):
        d = ctk.CTkToplevel(self); d.title(L("add_token")); d.geometry("480x520"); d.configure(fg_color=TH.card)
        d.transient(self); d.grab_set(); d.resizable(False,False)
        d.geometry(f"+{self.winfo_x()+(self.winfo_width()-480)//2}+{self.winfo_y()+(self.winfo_height()-520)//2}")
        sc = ctk.CTkScrollableFrame(d, fg_color="transparent"); sc.pack(fill="both", expand=True, padx=20, pady=14)
        ctk.CTkLabel(sc, text=L("add_token"), font=ctk.CTkFont(size=18, weight="bold"), text_color=TH.t1).pack(pady=(0,10))
        fields = {}
        for key, ph, w in [("symbol",L("token_symbol"),200),("name",L("token_name"),350),("contract",L("token_contract"),420),("decimals",L("token_decimals"),100),("explorer",L("token_explorer"),420),("rpc",L("token_rpc"),420),("color",L("token_color"),120),("icon",L("token_icon"),80)]:
            ctk.CTkLabel(sc, text=ph, font=ctk.CTkFont(size=11), text_color=TH.t3).pack(anchor="w", pady=(4,1))
            e = self.E(sc, ph, w=w, h=36); e.pack(anchor="w"); fields[key] = e
        ctk.CTkLabel(sc, text=L("token_network"), font=ctk.CTkFont(size=11), text_color=TH.t3).pack(anchor="w", pady=(4,1))
        net_var = ctk.StringVar(value="erc20")
        nf = ctk.CTkFrame(sc, fg_color="transparent"); nf.pack(anchor="w")
        ctk.CTkRadioButton(nf, text="ERC-20 Token", variable=net_var, value="erc20", fg_color=TH.acc, border_color=TH.brd, text_color=TH.t1).pack(side="left", padx=(0,14))
        ctk.CTkRadioButton(nf, text="EVM Chain", variable=net_var, value="evm", fg_color=TH.acc, border_color=TH.brd, text_color=TH.t1).pack(side="left")
        fields["decimals"].insert(0, "18"); fields["color"].insert(0, "#888888"); fields["icon"].insert(0, "?")
        st = ctk.CTkLabel(sc, text="", font=ctk.CTkFont(size=12), text_color=TH.red); st.pack(pady=4)
        def do_add():
            sym = fields["symbol"].get().strip().upper(); name = fields["name"].get().strip()
            if not sym or not name: st.configure(text="Symbol and Name required"); return
            if sym in SUPPORTED_COINS: st.configure(text=f"{sym} already exists"); return
            try: dec = int(fields["decimals"].get().strip())
            except: dec = 18
            self.wm.add_custom_coin(sym=sym, name=name, coin_type=net_var.get(), color=fields["color"].get().strip() or "#888888", icon=fields["icon"].get().strip() or "?", decimals=dec, explorer=fields["explorer"].get().strip(), rpc=fields["rpc"].get().strip(), contract=fields["contract"].get().strip())
            d.destroy(); self._toast(f"Added {sym}!"); self._nav("settings")
        ctk.CTkButton(sc, text=L("add_token_btn"), fg_color=TH.acc, hover_color=TH.acch, height=40, corner_radius=10, width=200, command=do_add).pack(pady=(8,4))

    def _scfg(self, k, v): self.wm.config[k] = v; self.wm.save_config()

    # ---- DATA REFRESH ----
    def _refresh(self):
        addrs = self.wm.get_all_active_addresses()
        syms = self._coin_order()
        self.api.fetch_prices_async(syms, lambda p: self._safe(lambda: self._set_p(p)))
        self.api.fetch_balances_async(addrs, lambda b: self._safe(lambda: self._set_b(b)))

    def _safe(self, fn):
        try: self.after(0, fn)
        except: pass

    def _set_p(self, p): self.prices = p; self._ud()
    def _set_b(self, b): self.bals = b; self._ud()

    def _ud(self):
        total = 0.0
        for sym in self._coin_order():
            bal = self.bals.get(sym); pr = self.prices.get(sym, 0)
            usd = (bal * pr) if bal is not None and pr else None
            dl = self._dl.get(sym)
            if dl:
                try:
                    if dl["b"].winfo_exists(): dl["b"].configure(text=f"{fb(bal)} {sym}" if bal is not None else f"--- {sym}")
                except: pass
                try:
                    if dl["v"].winfo_exists(): dl["v"].configure(text=fu(usd))
                except: pass
                try:
                    if dl["c"].winfo_exists():
                        if bal is not None and bal > 0:
                            ch = self.api.get_24h_change(sym)
                            if ch is not None: dl["c"].configure(text=fch(ch), text_color=TH.teal if ch >= 0 else TH.red)
                            else: dl["c"].configure(text="")
                        else: dl["c"].configure(text="")
                except: pass
                try:
                    if dl["p"].winfo_exists(): dl["p"].configure(text=fprice(pr) if pr else "")
                except: pass
            if usd: total += usd
        try:
            if hasattr(self,'_tl') and self._tl.winfo_exists(): self._tl.configure(text=fu(total) if total > 0 else "$0.00")
        except: pass

    def _auto(self):
        self._alive = True
        def loop():
            if not self._alive or self.wm.is_locked: return
            self._refresh(); self.wm.check_auto_lock()
            if self.wm.is_locked:
                try: self.after(0, self._login)
                except: pass; return
            if self._alive:
                try: self.after(60000, loop)
                except: pass
        self.after(1500, loop)


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    NexusWallet().mainloop()
