import pyperclip
from pynput import keyboard
import pyautogui
import tkinter as tk
from tkinter import messagebox
import time
import threading
import requests
import queue


# --- AYARLAR ---
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_ADI = "gemma3:1b"  # Ana model (F8)
TEXT_MODEL_CANDIDATES = [
    MODEL_ADI,
    "gemma3:4b",
    "gemma3:12b",
]

KISAYOL_METIN = keyboard.Key.f8  # Metin secimi icin kisayol


# Global değişkenler
root = None
gui_queue = queue.Queue()
kisayol_basildi = False
menu_acik = False  # BUG 1 FIX: Menü açıkken tekrar tetiklemeyi önlemek için


# --- MENÜ SEÇENEKLERİ VE PROMPT'LAR ---
ISLEMLER = {
    "🐦 X (Twitter) Flood Zincirine Çevir": (
        "Sen deneyimli bir sosyal medya içerik üreticisisin. "
        "Aşağıdaki metni veya fikri, Twitter/X platformu için bir flood zincirine (thread) dönüştür. "
        "Kurallar:\n"
        "- Her tweet 280 karakteri GEÇMEMELİ\n"
        "- İlk tweet dikkat çekici ve merak uyandırıcı olmalı (hook)\n"
        "- Her tweet [1/N], [2/N] şeklinde numaralandırılmalı\n"
        "- Akıcı, sürükleyici ve samimi bir dil kullan\n"
        "- Son tweette güçlü bir kapanış veya harekete geçirici mesaj (CTA) olsun\n"
        "- Uygun yerlerde emoji kullan ama abartma\n"
        "- Türkçe yaz\n"
        "Sadece flood içeriğini ver, açıklama ekleme.\n\nMetin/Fikir:"
    ),
    "📸 YouTube Shorts / TikTok Video Senaryosu Yaz": (
        "Sen viral kısa video içerikleri üreten deneyimli bir içerik stratejistisin. "
        "Aşağıdaki metni veya fikri, YouTube Shorts veya TikTok için bir video senaryosuna dönüştür. "
        "Format:\n"
        "🎬 HOOK (0-3 saniye): [İzleyiciyi anında yakalayan açılış cümlesi]\n"
        "📖 KONU GELİŞİMİ (3-45 saniye): [Bölüm bölüm anlatım, her bölüm için ne söyleneceği ve varsa görsel/efekt önerisi]\n"
        "🔥 KAPANIŞ & CTA (45-60 saniye): [Güçlü kapanış + beğen/takip et/yorum yap yönlendirmesi]\n\n"
        "Ekstra kurallar:\n"
        "- Dil hızlı, enerjik ve sohbet havasında olsun\n"
        "- Her cümle kısa ve net olsun\n"
        "- Türkçe yaz\n"
        "Sadece senaryoyu ver.\n\nMetin/Fikir:"
    ),
    "🧲 Tıklanma Oranı Yüksek Başlıklar Üret": (
        "Sen SEO ve sosyal medya optimizasyonu konusunda uzman bir içerik stratejistisin. "
        "Aşağıdaki metni veya fikri analiz et ve farklı platformlar için yüksek tıklanma oranı sağlayacak başlıklar üret. "
        "ÖNEMLİ: Clickbait OLMAYACAK — vaadi gerçek ve içerikle uyumlu olacak.\n\n"
        "Format:\n"
        "📰 HABER / MAKALE BAŞLIĞI (3 seçenek)\n"
        "▸ [başlık 1]\n"
        "▸ [başlık 2]\n"
        "▸ [başlık 3]\n\n"
        "🐦 TWITTER/X BAŞLIĞI (3 seçenek)\n"
        "▸ [başlık 1]\n"
        "▸ [başlık 2]\n"
        "▸ [başlık 3]\n\n"
        "📸 YOUTUBE / TİKTOK BAŞLIĞI (3 seçenek)\n"
        "▸ [başlık 1]\n"
        "▸ [başlık 2]\n"
        "▸ [başlık 3]\n\n"
        "Her başlık için neden tıklanır? kısmını 1 satırda kısaca açıkla.\n"
        "Türkçe yaz. Sadece başlıkları ve kısa gerekçelerini ver.\n\nMetin/Fikir:"
    ),
}


def get_available_text_model():
    """Metin işlemede kullanılabilir modeli seçer."""
    preferred_models = []
    for model in TEXT_MODEL_CANDIDATES:
        if model and model not in preferred_models:
            preferred_models.append(model)

    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code != 200:
            return MODEL_ADI

        models = response.json().get("models", [])
        installed_lower = {m.get("name", "").lower(): m.get("name", "") for m in models}

        for candidate in preferred_models:
            candidate_lower = candidate.lower()
            if candidate_lower in installed_lower:
                return installed_lower[candidate_lower]

            candidate_base = candidate_lower.split(":")[0]
            for installed_name_lower, installed_name in installed_lower.items():
                if installed_name_lower.startswith(candidate_base + ":"):
                    return installed_name
    except Exception:
        pass

    return MODEL_ADI


def ollama_cevap_al(prompt):
    """Ollama API'den cevap al."""
    try:
        aktif_model = get_available_text_model()
        payload = {
            "model": aktif_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.85,
                "top_p": 0.92,
            },
        }

        response = requests.post(OLLAMA_URL, json=payload, timeout=120)

        if response.status_code == 200:
            result = response.json()
            return result.get("response", "").strip()

        err_msg = (
            f"Ollama API Hatası: {response.status_code}\n"
            f"Model: {aktif_model}\n"
            f"Cevap: {response.text}"
        )
        print(f"❌ {err_msg}")
        gui_queue.put((messagebox.showerror, ("API Hatası", err_msg)))
        return None

    except requests.exceptions.ConnectionError:
        err_msg = (
            "Ollama'ya bağlanılamadı.\n"
            "Programın çalıştığından emin olun!\n"
            "(http://localhost:11434)"
        )
        print(f"❌ {err_msg}")
        gui_queue.put((messagebox.showerror, ("Bağlantı Hatası", err_msg)))
        return None
    except Exception as e:
        err_msg = f"Beklenmeyen Hata: {e}"
        print(f"❌ {err_msg}")
        gui_queue.put((messagebox.showerror, ("Hata", err_msg)))
        return None


def strip_code_fence(text):
    if not text:
        return text
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        lines = lines[1:] if lines else []
        while lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def secili_metni_kopyala(max_deneme=4):
    sentinel = f"__ICERIK_ASISTAN__{time.time_ns()}__"
    try:
        pyperclip.copy(sentinel)
    except Exception:
        pass

    metin = ""
    for _ in range(max_deneme):
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.2)
        metin = pyperclip.paste()
        if metin and metin.strip() and metin != sentinel:
            return metin

    # BUG 3 FIX: Başarısız olursa sentinel panodan temizlenir
    try:
        if pyperclip.paste() == sentinel:
            pyperclip.copy("")
    except Exception:
        pass

    return ""


def sonuc_penceresi_goster(baslik, icerik):
    pencere = tk.Toplevel(root)
    pencere.title(f"✨ {baslik}")
    pencere.geometry("820x580")
    pencere.minsize(600, 400)
    pencere.attributes("-topmost", True)
    pencere.configure(bg="#1a1a2e")

    # Başlık bar
    baslik_frame = tk.Frame(pencere, bg="#16213e", pady=10)
    baslik_frame.pack(fill="x")
    tk.Label(
        baslik_frame,
        text=baslik,
        bg="#16213e",
        fg="#e2b96f",
        font=("Segoe UI", 11, "bold"),
    ).pack(padx=15)

    # İçerik alanı
    frame = tk.Frame(pencere, bg="#1a1a2e")
    frame.pack(fill="both", expand=True, padx=12, pady=10)

    text_alani = tk.Text(
        frame,
        wrap="word",
        bg="#0f3460",
        fg="#e0e0e0",
        insertbackground="white",
        font=("Segoe UI", 10),
        padx=14,
        pady=12,
        relief="flat",
        selectbackground="#e2b96f",
        selectforeground="#1a1a2e",
    )
    kaydirma = tk.Scrollbar(frame, command=text_alani.yview, bg="#16213e", troughcolor="#0f3460")
    text_alani.configure(yscrollcommand=kaydirma.set)

    text_alani.pack(side="left", fill="both", expand=True)
    kaydirma.pack(side="right", fill="y")

    text_alani.insert("1.0", icerik)
    text_alani.config(state="disabled")

    # Alt butonlar
    alt_frame = tk.Frame(pencere, bg="#1a1a2e")
    alt_frame.pack(fill="x", padx=12, pady=(0, 12))

    def panoya_kopyala():
        pyperclip.copy(icerik)
        kopyala_btn.config(text="✅ Kopyalandı!")
        pencere.after(2000, lambda: kopyala_btn.config(text="📋 Panoya Kopyala"))

    kopyala_btn = tk.Button(
        alt_frame,
        text="📋 Panoya Kopyala",
        command=panoya_kopyala,
        bg="#e2b96f",
        fg="#1a1a2e",
        activebackground="#f0c97a",
        activeforeground="#1a1a2e",
        relief="flat",
        font=("Segoe UI", 9, "bold"),
        padx=14,
        pady=7,
        cursor="hand2",
    )
    kopyala_btn.pack(side="left")

    tk.Button(
        alt_frame,
        text="Kapat",
        command=pencere.destroy,
        bg="#2d2d44",
        fg="#aaaaaa",
        activebackground="#3d3d55",
        activeforeground="white",
        relief="flat",
        font=("Segoe UI", 9),
        padx=14,
        pady=7,
        cursor="hand2",
    ).pack(side="right")

    pencere.focus_force()
    pencere.lift()


def islemi_yap(komut_adi, secili_metin):
    prompt_emri = ISLEMLER[komut_adi]
    full_prompt = f"{prompt_emri}\n\n{secili_metin}"

    print(f"✍️  İşlem: {komut_adi}")
    print("⏳ Ollama ile içerik üretiliyor...")

    sonuc = ollama_cevap_al(full_prompt)
    if not sonuc:
        print("❌ Sonuç alınamadı.")
        return

    sonuc = strip_code_fence(sonuc)

    gui_queue.put((sonuc_penceresi_goster, (komut_adi, sonuc)))
    print("✅ İçerik üretildi, pencerede gösteriliyor.")


def process_queue():
    """Kuyruktaki GUI işlemlerini ana thread'de çalıştırır."""
    try:
        while True:
            try:
                task = gui_queue.get_nowait()
            except queue.Empty:
                break
            # BUG 2 FIX: GUI görevlerindeki hatalar artık yakalanıp loglanıyor
            try:
                func, args = task
                func(*args)
            except Exception as e:
                print(f"❌ GUI görev hatası: {e}")
    finally:
        if root:
            root.after(100, process_queue)


def menu_goster():
    """Metni kopyalar ve menüyü gösterir (ana thread)."""
    global menu_acik

    # BUG 1 FIX: Menü zaten açıksa tekrar açma
    if menu_acik:
        return

    secili_metin = secili_metni_kopyala()
    if not secili_metin.strip():
        gui_queue.put(
            (
                messagebox.showwarning,
                (
                    "Seçim Bulunamadı",
                    "Lütfen önce bir metin veya fikir seçin, sonra F8 ile menüyü açın.",
                ),
            )
        )
        return

    menu_acik = True

    menu = tk.Menu(
        root,
        tearoff=0,
        bg="#16213e",
        fg="#e0e0e0",
        activebackground="#e2b96f",
        activeforeground="#1a1a2e",
        font=("Segoe UI", 10),
    )

    # Başlık (tıklanamaz)
    menu.add_command(label="✨ İçerik Üretim Asistanı", state="disabled",
                     font=("Segoe UI", 9, "bold"))
    menu.add_separator()

    def komut_olustur(k_adi, s_metin):
        def komut_calistir():
            threading.Thread(
                target=islemi_yap, args=(k_adi, s_metin), daemon=True
            ).start()
        return komut_calistir

    for baslik in ISLEMLER.keys():
        menu.add_command(label=baslik, command=komut_olustur(baslik, secili_metin))

    menu.add_separator()
    menu.add_command(label="❌ İptal", command=lambda: None)

    # BUG 1 FIX: Menü kapanınca flag sıfırlanır
    def on_menu_unpost():
        global menu_acik
        menu_acik = False

    menu.bind("<Unmap>", lambda e: on_menu_unpost())

    try:
        x, y = pyautogui.position()
        menu.tk_popup(x, y)
    finally:
        menu.grab_release()
        menu_acik = False  # tk_popup bloklamadığı durumlarda da sıfırla


def on_press(key):
    global kisayol_basildi
    if key == KISAYOL_METIN and not kisayol_basildi:
        kisayol_basildi = True
        gui_queue.put((menu_goster, ()))


def on_release(key):
    global kisayol_basildi
    if key == KISAYOL_METIN:
        kisayol_basildi = False


if __name__ == "__main__":
    print("=" * 60)
    print("✨ Sosyal Medya & İçerik Üretim Asistanı")
    print("=" * 60)
    aktif_text_model = get_available_text_model()
    print(f"📦 Aktif Model (F8): {aktif_text_model}")
    print()
    print("🔧 Kullanım:")
    print("   1) Herhangi bir metni veya fikri seçin")
    print("   2) F8 tuşuna basın")
    print("   3) Üretmek istediğiniz içerik türünü seçin")
    print()
    print("📋 Mevcut İşlemler:")
    for islem in ISLEMLER.keys():
        print(f"   {islem}")
    print()
    print("⚠️  Programı kapatmak için bu pencereyi kapatın veya Ctrl+C yapın.")
    print("=" * 60)

    try:
        test_response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if test_response.status_code == 200:
            print("✅ Ollama bağlantısı başarılı!")
        else:
            print("⚠️  Ollama'ya bağlanılamadı, servisi kontrol edin!")
    except Exception:
        print("⚠️  Ollama çalışmıyor olabilir! 'ollama serve' ile başlatın.")

    print()

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    root = tk.Tk()
    root.withdraw()
    root.after(100, process_queue)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("Kapatılıyor...")
