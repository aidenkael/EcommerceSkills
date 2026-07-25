"""
1688 以图搜图 v6.0 — 极简版（零 CDP，零 Playwright）
=================================================
拖图 → 上传 1688 → 自动在 Edge 打开搜索结果
"""
import os, sys, base64, threading, webbrowser, tempfile, json, time
from io import BytesIO
from pathlib import Path
import requests
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
try: from tkinterdnd2 import TkinterDnD, DND_FILES; HAS_DND = True
except: HAS_DND = False

LOG_DIR = Path.home() / "1688搜图_日志"
BG, CARD = "#F5F6FA", "#FFFFFF"
ACCENT, TXT, TXT2 = "#FF6A00", "#2C3E50", "#7F8C8D"
S_OK, S_WARN, S_ERR = "#27AE60", "#E67E22", "#E74C3C"

LOG_FILE = None
def _log(msg, level="INFO"):
    global LOG_FILE; ts = time.strftime("%H:%M:%S"); line = f"[{ts}][{level}] {msg}"
    print(line)
    if LOG_DIR.exists() and LOG_FILE:
        try: open(LOG_FILE,"a",encoding="utf-8").write(line+"\n")
        except: pass

def init_log():
    global LOG_FILE; LOG_DIR.mkdir(parents=True,exist_ok=True)
    LOG_FILE = LOG_DIR / f"v6_{time.strftime('%Y%m%d_%H%M%S')}.txt"
    _log("=== 1688 v6.0 ===")

def img_to_b64(path, max_px=1280):
    img = Image.open(path)
    if max(img.size) > max_px: r=max_px/max(img.size); img=img.resize((int(img.size[0]*r),int(img.size[1]*r)),Image.LANCZOS)
    if img.mode in ("RGBA","P","LA"): img=img.convert("RGB")
    s=max(img.size); bg=Image.new("RGB",(s,s),"white"); bg.paste(img,((s-img.width)//2,(s-img.height)//2))
    b=BytesIO(); bg.save(b,format="JPEG",quality=85)
    return base64.b64encode(b.getvalue()).decode()

def make_thumb(path, size=(280,280)):
    """裁剪缩略图（始终填满正方形）"""
    img=Image.open(path).convert("RGB")
    # 裁剪中心区域成正方形
    w,h=img.size
    s=min(w,h)
    left=(w-s)//2; top=(h-s)//2
    img=img.crop((left, top, left+s, top+s))
    img=img.resize(size, Image.LANCZOS)
    return img

class App:
    def __init__(self):
        init_log()
        self.root = (TkinterDnD.Tk() if HAS_DND else tk.Tk())
        self.root.title("1688 以图搜图 v6.0"); self.root.geometry("650x550"); self.root.configure(bg=BG); self.root.minsize(500,400)
        self.root.update_idletasks(); sw,sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"+{(sw-650)//2}+{(sh-550)//2}")
        self._path=None; self._searching=False; self._imgref=None; self._history=[]
        self._build()
        if HAS_DND:
            try: self.root.drop_target_register(DND_FILES); self.root.dnd_bind("<<Drop>>",self._drop)
            except: pass
        self.root.bind("<Control-v>",self._paste)

    def _build(self):
        h = tk.Frame(self.root,bg=BG); h.pack(fill="x",padx=20,pady=(15,5))
        tk.Label(h,text="🔍 1688 以图搜图 v6.0",font=("Microsoft YaHei",18,"bold"),bg=BG,fg=ACCENT).pack(side="left")
        tk.Label(h,text="拖图 → 一秒找到 1688 同款",font=("Microsoft YaHei",10),bg=BG,fg=TXT2).pack(side="left",padx=10,pady=3)

        m = tk.Frame(self.root,bg=BG); m.pack(fill="both",expand=True,padx=20,pady=10)

        # 左侧拖放区
        self.df = tk.Frame(m,bg="#FFF9F2",relief="solid",bd=2,highlightbackground=ACCENT,highlightthickness=2)
        self.df.pack(side="top",pady=(0,10)); self.df.configure(height=260); self.df.pack_propagate(False)
        self.dh = tk.Label(self.df,text="📁  拖拽图片到此处\n或 Ctrl+V 粘贴\n或点击下方按钮选择文件",font=("Microsoft YaHei",12),bg="#FFF9F2",fg=TXT2,justify="center")
        self.dh.pack(expand=True)
        self.il = tk.Label(self.df,bg="#FFF9F2")

        # 按钮
        bf = tk.Frame(m,bg=BG); bf.pack(fill="x",pady=5)
        ttk.Button(bf,text="选择图片",command=self._upload,width=12).pack(side="left")
        ttk.Button(bf,text="清除",command=self._clear,width=8).pack(side="left",padx=5)
        self.sb = ttk.Button(bf,text="🔍 搜索 1688 同款",command=self._search,width=18); self.sb.pack(side="right")
        self.sb.state(["disabled"])

        # 状态
        self.sl = tk.Label(m,text="📌 等待拖入图片...",font=("Microsoft YaHei",10),bg=BG,fg=TXT2,wraplength=550,justify="left")
        self.sl.pack(fill="x",pady=5)

        # 历史记录
        hf = tk.Frame(m,bg=BG); hf.pack(fill="both",expand=True)
        tk.Label(hf,text="搜索历史",font=("Microsoft YaHei",10,"bold"),bg=BG,fg=TXT).pack(anchor="w")
        self.hist_frame = tk.Frame(hf,bg=CARD,relief="solid",bd=1,highlightbackground="#E0E0E0",highlightthickness=1)
        self.hist_frame.pack(fill="both",expand=True,pady=5)

    def _load(self,path):
        try:
            thumb=make_thumb(path,(300,240));photo=ImageTk.PhotoImage(thumb);self._imgref=photo;self._path=path
            self.dh.pack_forget(); self.il.configure(image=photo); self.il.image=photo; self.il.pack(expand=True)
            size_kb=os.path.getsize(path)/1024
            self.sl.configure(text=f"✅ {os.path.basename(path)} ({size_kb:.0f}KB) — 点击搜索",fg=S_OK)
            self.sb.state(["!disabled"])
        except Exception as e: messagebox.showerror("Error",str(e))

    def _drop(self,e):
        p=e.data.strip()
        if p.startswith("{") and p.endswith("}"): p=p[1:-1]
        if os.path.isfile(p): self._load(p)

    def _paste(self,_):
        try: from PIL import ImageGrab; img=ImageGrab.grabclipboard()
        except: return
        if img is None: return
        tmp=tempfile.NamedTemporaryFile(suffix=".png",delete=False); img.save(tmp.name); self._load(tmp.name)

    def _upload(self):
        p=filedialog.askopenfilename(title="选择图片",filetypes=[("图片","*.jpg *.jpeg *.png *.webp *.bmp *.gif")])
        if p: self._load(p)

    def _clear(self):
        self._path=None; self.il.configure(image="",text=""); self.il.image=None; self.il.pack_forget()
        self.dh.pack(expand=True); self.sl.configure(text="📌 等待拖入图片...",fg=TXT2); self.sb.state(["disabled"])

    def _search(self):
        if self._searching or not self._path: return
        self._searching=True; self.sb.configure(text="搜索中..."); self.sb.state(["disabled"])
        self.sl.configure(text="⏳ 上传图片到 1688...",fg=S_WARN)
        threading.Thread(target=self._do_search,daemon=True).start()

    def _do_search(self):
        _log("=== SEARCH ===")
        try:
            b64=img_to_b64(self._path); _log(f"b64: {len(b64)} chars")
            r=requests.post("https://search.1688.com/service/uploadErpImgSearch",
                json={"imgBase64":b64,"searchType":"imageSearch","appName":"pcErpImage","urlType":"main"},
                headers={"Content-Type":"application/json"},timeout=30)
            d=r.json(); iid=d.get('data',{}).get('imageId','')
            url=f"https://air.1688.com/kapp/1688-search/pc-image-search/?tab=imageSearch&showP4P=false&odTab=consign&showBid=false&imageId={iid}"
            _log(f"imageId={iid} code={d.get('code')}")

            if d.get("code")!=0: raise Exception(d.get("errMsg","upload failed"))

            # 1. 自动在 Edge 打开结果
            webbrowser.open(url)
            _log("Opened in browser")

            # 2. 在软件里显示链接
            self.root.after(0,lambda: self._show_result(url, iid))

        except Exception as e:
            _log(f"Error: {e}","ERROR")
            self.root.after(0,lambda: self._err(str(e)))
        _log("=== END ===")

    def _show_result(self, url, image_id):
        self._searching=False; self.sb.configure(text="🔍 搜索 1688 同款"); self.sb.state(["!disabled"])
        self.sl.configure(text=f"✅ 已打开搜图结果 (imageId: {image_id[:12]}...)",fg=S_OK)

        # 添加历史记录
        row = tk.Frame(self.hist_frame, bg="#FAFAFA", relief="groove", bd=1)
        row.pack(fill="x", padx=4, pady=2)

        ts = time.strftime("%H:%M:%S")
        fname = os.path.basename(self._path) if self._path else "unknown"

        tk.Label(row, text=f"[{ts}] {fname}", font=("Microsoft YaHei",9), bg="#FAFAFA", fg=TXT, anchor="w").pack(side="left", padx=5)

        link = tk.Label(row, text="→ 打开结果页", font=("Microsoft YaHei",9,"underline"), bg="#FAFAFA", fg="#2980B9", cursor="hand2")
        link.pack(side="right", padx=5)
        link.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))

        link2 = tk.Label(row, text="复制链接", font=("Microsoft YaHei",9,"underline"), bg="#FAFAFA", fg="#7F8C8D", cursor="hand2")
        link2.pack(side="right", padx=2)
        link2.bind("<Button-1>", lambda e, u=url: self.root.clipboard_append(u))

        self._history.append(row)
        # 限制 10 条
        if len(self._history) > 10:
            self._history[0].destroy(); self._history.pop(0)

    def _err(self,msg):
        self._searching=False; self.sb.configure(text="🔍 搜索 1688 同款"); self.sb.state(["!disabled"])
        self.sl.configure(text=f"❌ {msg[:120]}",fg=S_ERR)

    def run(self): self.root.mainloop()

if __name__=="__main__": App().run()
