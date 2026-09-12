# PDF Seitennummerierer & Transkript-Styler

Eine performante, serverlose Web-App zur einheitlichen Seitennummerierung und Formatierung von PDF-Dokumenten (speziell für qualitative Interview-Transkripte, Seminar- und Abschlussarbeiten) mit automatischer Entfernung des **MAXQDA-Logos** und direkter Anhang-Korrektur.

🌐 **Live Web-App:** [https://toseflo.github.io/PdfPageNumber/](https://toseflo.github.io/PdfPageNumber/)

---

## ✨ Features

- **Exakter Layout-Stil:** Platziert Seitenzahlen in `Arial` (12.96 pt), schwarz, rechtsbündig mit exaktem Randabstand unten rechts.
- **Kopfzeile Anhang-Korrektur:** Ändert fehlerhafte Bezeichnungen (z. B. `Anhang B4` ➔ `Anhang C4`) direkt im internen PDF-Content-Stream – **ohne überdeckende weiße Box**.
- **MAXQDA-Logo herausschneiden:** Überdeckt das Bild-Logo unten rechts millimetergenau, ohne den Text darüber anzuschneiden.
- **Alte Fußzeilen-Seitenzahlen entfernen:** Löscht alte zentrierte Paginierungen (z. B. `1/8`).
- **Interaktive Live-Vorschau mit Tabs:** Umschaltbar zwischen `⬇️ Fußzeile` und `⬆️ Kopfzeile (Anhang)` mit automatischem Fokus beim Anpassen von Einstellungen.
- **Frei wählbare Startnummer:** Beginn bei Seite 1, 43 oder einer beliebigen Startzahl.
- **100 % Datenschutz & Offline-fähig:** Läuft komplett lokal im Browser via `pdf-lib` und `PDF.js`. Es werden **keinerlei Daten** übertragen.

- **Zwei Nutzungsweisen:** Direkt im Browser via GitHub Pages oder als lokale Python Desktop-App (PyQt6).

---

## 🚀 Nutzung

### 1. Web-App (GitHub Pages)
Einfach die URL [https://toseflo.github.io/PdfPageNumber/](https://toseflo.github.io/PdfPageNumber/) öffnen:
1. PDF-Datei per Drag & Drop hineinziehen.
2. Start-Seitenzahl und gewünschten Anhang-Buchstaben festlegen.
3. Ergebnis in der Live-Vorschau prüfen.
4. Auf **PDF nummerieren & herunterladen** klicken.

### 2. Lokale Python Desktop-App
```bash
# Grafische Oberfläche starten
python gui.py
```
