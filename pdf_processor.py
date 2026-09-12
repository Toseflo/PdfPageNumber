"""
Kernlogik für die PDF-Verarbeitung und Seitennummerierung mit PyMuPDF.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

import pymupdf


@dataclass
class PageNumberStyle:
    """Konfiguration für das Erscheinungsbild und die Platzierung der Seitenzahl."""
    font_name: str = "ArialMT"
    font_size: float = 12.96
    color: tuple[float, float, float] = (0.0, 0.0, 0.0)  # RGB (0.0 - 1.0)

    # Relative Abstände (Bruchteil der jeweiligen Seitendimension)
    relative_margin_right: float = 0.095166    # 9.5166% vom rechten Seitenrand
    relative_baseline_bottom: float = 0.066733  # 6.6733% vom unteren Seitenrand zur Text-Grundlinie
    relative_bbox_bottom: float = 0.063501      # 6.3501% vom unteren Seitenrand zur Unterkante

    # Absolute Abstände in PDF-Punkten (72 pt = 1 Zoll = 25.4 mm)
    margin_right_pt: float = 56.6542            # ca. 19.99 mm (~20 mm Standardrand)
    baseline_bottom_pt: float = 56.1840         # ca. 19.82 mm
    bbox_bottom_pt: float = 53.4624             # ca. 18.86 mm


# Standard-Stil aus der Analyse von Seite.pdf
HARDCODED_STYLE = PageNumberStyle()


def get_system_arial_path() -> str | None:
    """Sucht nach einer installierten TrueType-Datei von Arial auf dem System."""
    potential_paths = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/arial.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in potential_paths:
        if os.path.exists(path):
            return path
    return None


def analyze_reference_pdf(
    pdf_path: str | Path = "Seite.pdf",
    target_number: str = "43"
) -> PageNumberStyle:
    """
    Analysiert eine Referenz-PDF (z. B. 'Seite.pdf') und ermittelt die
    Formatierung und Position der Seitenzahl unten rechts.
    """
    path = Path(pdf_path)
    if not path.exists():
        return HARDCODED_STYLE

    doc = pymupdf.open(path)
    page = doc[0]
    p_width = page.rect.width
    p_height = page.rect.height

    text_dict = page.get_text("dict")
    found_span = None

    for block in text_dict.get("blocks", []):
        if block.get("type") == 0:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("text", "").strip() == target_number:
                        found_span = span
                        break
                if found_span:
                    break
        if found_span:
            break

    if not found_span:
        candidates = []
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        x1, y1, _, _ = span["bbox"]
                        if x1 > p_width * 0.6 and y1 > p_height * 0.7:
                            candidates.append(span)
        if candidates:
            found_span = sorted(candidates, key=lambda s: (s["bbox"][3], s["bbox"][2]))[-1]

    if not found_span:
        doc.close()
        return HARDCODED_STYLE

    bbox = found_span["bbox"]
    origin = found_span.get("origin", (bbox[0], bbox[3]))
    font_name = found_span.get("font", "ArialMT")
    font_size = found_span.get("size", 12.96)

    int_color = found_span.get("color", 0)
    r = ((int_color >> 16) & 255) / 255.0
    g = ((int_color >> 8) & 255) / 255.0
    b = (int_color & 255) / 255.0

    margin_right_pt = p_width - bbox[2]
    margin_bottom_pt = p_height - bbox[3]
    baseline_bottom_pt = p_height - origin[1]

    style = PageNumberStyle(
        font_name=font_name,
        font_size=round(font_size, 4),
        color=(round(r, 4), round(g, 4), round(b, 4)),
        relative_margin_right=round(margin_right_pt / p_width, 6),
        relative_baseline_bottom=round(baseline_bottom_pt / p_height, 6),
        relative_bbox_bottom=round(margin_bottom_pt / p_height, 6),
        margin_right_pt=round(margin_right_pt, 4),
        baseline_bottom_pt=round(baseline_bottom_pt, 4),
        bbox_bottom_pt=round(margin_bottom_pt, 4),
    )

    doc.close()
    return style


def remove_maxqda_logo_from_page(page: pymupdf.Page) -> bool:
    """
    Entfernt das MAXQDA-Logo unten rechts von der Seite (egal ob als Bild,
    Vektorgrafik oder Text eingebettet).
    """
    p_width = page.rect.width
    p_height = page.rect.height
    found = False

    # 1. Bilder im unteren rechten Bereich finden und entfernen
    for img in page.get_images():
        for r in page.get_image_rects(img[0]):
            if r.x0 >= p_width * 0.65 and r.y0 >= p_height * 0.85:
                padded = pymupdf.Rect(r.x0 - 2, r.y0 - 2, r.x1 + 2, r.y1 + 2)
                page.add_redact_annot(padded, fill=(1, 1, 1))
                found = True

    # 2. Falls kein Bild gefunden wurde, typischen Logo-Bereich prüfen
    if not found:
        # Standard-Logo-Bereich (ca. 460-565 x, 770-800 y bei A4)
        candidate_rect = pymupdf.Rect(p_width - 135, p_height - 72, p_width - 35, p_height - 40)
        text_in_rect = page.get_text("text", clip=candidate_rect).strip()
        drawings_in_rect = [d for d in page.get_drawings() if candidate_rect.intersects(d["rect"])]
        if text_in_rect or drawings_in_rect:
            page.add_redact_annot(candidate_rect, fill=(1, 1, 1))
            found = True

    if found:
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_REMOVE)
    return found


def remove_center_pagination_from_page(page: pymupdf.Page) -> bool:
    """
    Entfernt zentrierte Seitenzahlen wie '1/8' unten in der Fußzeilenmitte.
    """
    p_width = page.rect.width
    p_height = page.rect.height
    found = False
    text_dict = page.get_text("dict")

    for block in text_dict.get("blocks", []):
        if block.get("type") == 0:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    bx0, by0, bx1, by1 = span["bbox"]
                    # Liegt in der Mitte unten
                    if abs((bx0 + bx1) / 2.0 - p_width / 2.0) < 65.0 and by0 >= p_height * 0.88:
                        text = span.get("text", "").strip()
                        if re.match(r"^\d+(\s*/\s*\d+)?$", text):
                            padded = pymupdf.Rect(bx0 - 2, by0 - 2, bx1 + 2, by1 + 2)
                            page.add_redact_annot(padded, fill=(1, 1, 1))
                            found = True

    if found:
        page.apply_redactions()
    return found


def replace_anhang_letter_on_page(page: pymupdf.Page, target_letter: str = "C") -> bool:
    """
    Sucht auf der Seite (typischerweise Seite 1) nach einer Kopfzeile wie 'Anhang B4'
    oder 'Anhang B' und ersetzt den Buchstaben durch target_letter (z. B. 'Anhang C4').
    """
    text_dict = page.get_text("dict")
    found_span = None

    for block in text_dict.get("blocks", []):
        if block.get("type") == 0:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    # In der oberen Seitenhälfte suchen
                    if span["bbox"][1] < page.rect.height * 0.35:
                        txt = span.get("text", "").strip()
                        m = re.match(r"^Anhang\s+([A-Za-z])(.*)$", txt, re.IGNORECASE)
                        if m:
                            found_span = (span, m.group(1), m.group(2))
                            break
                if found_span:
                    break
        if found_span:
            break

    if not found_span:
        return False

    span, orig_letter, suffix = found_span
    target_clean = (target_letter or "C").strip().upper()
    new_text = f"Anhang {target_clean}{suffix}"
    origin = span.get("origin", (84.7, 58.14))
    font_size = span.get("size", 11.2)

    bx0, by0, bx1, by1 = span["bbox"]
    cover_rect = pymupdf.Rect(bx0 - 2, by0 - 2, bx1 + 10, by1 + 2)
    page.draw_rect(cover_rect, color=(1, 1, 1), fill=(1, 1, 1))

    bold_paths = [
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\Arialbd.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/arialbd.ttf",
    ]
    bold_found = False
    for bp in bold_paths:
        if os.path.exists(bp):
            try:
                page.insert_font(fontname="ArialBoldAnhang", fontfile=bp)
                page.insert_text(origin, new_text, fontname="ArialBoldAnhang", fontsize=font_size, color=(0, 0, 0))
                bold_found = True
                break
            except Exception:
                pass

    if not bold_found:
        page.insert_text(origin, new_text, fontname="helv", fontsize=font_size, color=(0, 0, 0))

    return True


def stamp_page_number(
    page: pymupdf.Page,
    page_number: int,
    style: PageNumberStyle = HARDCODED_STYLE,
    font_name: str = "helv",
    font_obj: pymupdf.Font | None = None,
    arial_path: str | None = None,
    use_relative: bool = True,
) -> None:
    """Fügt einer einzelnen Seite die Seitenzahl im exakten Stil hinzu."""
    p_width = page.rect.width
    p_height = page.rect.height
    text = str(page_number)

    if font_obj and arial_path:
        page.insert_font(fontname=font_name, fontfile=arial_path)
        text_w = font_obj.text_length(text, fontsize=style.font_size)
    else:
        text_w = pymupdf.get_text_length(text, fontname=font_name, fontsize=style.font_size)

    if use_relative:
        target_right_x = p_width * (1.0 - style.relative_margin_right)
        baseline_y = p_height * (1.0 - style.relative_baseline_bottom)
    else:
        target_right_x = p_width - style.margin_right_pt
        baseline_y = p_height - style.baseline_bottom_pt

    origin_x = target_right_x - text_w

    page.insert_text(
        point=(origin_x, baseline_y),
        text=text,
        fontname=font_name,
        fontsize=style.font_size,
        color=style.color,
    )


def add_page_numbers(
    input_pdf: str | Path,
    output_pdf: str | Path | None = None,
    start_number: int = 1,
    remove_logo: bool = True,
    remove_old_pagination: bool = False,
    replace_anhang: bool = True,
    anhang_letter: str = "C",
    style: PageNumberStyle | None = None,
    use_relative_margins: bool = True,
    pages_to_number: Sequence[int] | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> Path:
    """
    Nummeriert ein PDF-Dokument ab einer wählbaren Startnummer durch und entfernt
    optional das MAXQDA-Logo und/oder alte zentrierte Seitenzahlen.
    """
    input_path = Path(input_pdf)
    if not input_path.exists():
        raise FileNotFoundError(f"Eingabedatei nicht gefunden: {input_path.resolve()}")

    if output_pdf is None:
        output_path = input_path.with_name(f"{input_path.stem}_numbered{input_path.suffix}")
    else:
        output_path = Path(output_pdf)

    if style is None:
        style = HARDCODED_STYLE

    arial_path = get_system_arial_path()
    font_name = "helv"
    font_obj = None

    if arial_path:
        try:
            font_obj = pymupdf.Font(fontfile=arial_path)
            font_name = "ArialCustom"
        except Exception:
            font_obj = None
            font_name = "helv"

    doc = pymupdf.open(input_path)
    total_pages = len(doc)
    page_indices = pages_to_number if pages_to_number is not None else range(total_pages)

    current_num = start_number
    for step, page_idx in enumerate(page_indices):
        if page_idx < 0 or page_idx >= total_pages:
            continue

        page = doc[page_idx]

        # 0. Optionales Korrigieren der Anhang-Kopfzeile auf Seite 1
        if replace_anhang and page_idx == 0:
            replace_anhang_letter_on_page(page, target_letter=anhang_letter)

        # 1. Optionales Entfernen des MAXQDA-Logos
        if remove_logo:
            remove_maxqda_logo_from_page(page)

        # 2. Optionales Entfernen alter zentrierter Seitenzahlen
        if remove_old_pagination:
            remove_center_pagination_from_page(page)

        # 3. Seitenzahl einfügen
        stamp_page_number(
            page=page,
            page_number=current_num,
            style=style,
            font_name=font_name,
            font_obj=font_obj,
            arial_path=arial_path,
            use_relative=use_relative_margins,
        )

        current_num += 1

        if progress_callback:
            progress_callback(step + 1, len(page_indices))

    # Sicher speichern (auch bei Überschreiben derselben Datei)
    if output_path.resolve() == input_path.resolve():
        temp_output = output_path.with_name(f"{output_path.stem}_temp{output_path.suffix}")
        doc.save(str(temp_output), garbage=4, deflate=True)
        doc.close()
        temp_output.replace(output_path)
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path), garbage=4, deflate=True)
        doc.close()

    return output_path


def render_page_preview(
    pdf_path: str | Path,
    page_idx: int = 0,
    start_number: int = 1,
    remove_logo: bool = True,
    remove_old_pagination: bool = False,
    replace_anhang: bool = True,
    anhang_letter: str = "C",
    style: PageNumberStyle = HARDCODED_STYLE,
    footer_only: bool = True,
) -> bytes:
    """
    Rendert eine PNG-Vorschau der Seite (oder der Fußzeile) im Speicher
    mit angewendeter Logo-Entfernung und Seitennummer.
    Gibt die PNG-Rohdaten als Bytes zurück.
    """
    doc = pymupdf.open(pdf_path)
    if page_idx >= len(doc):
        page_idx = 0
    page = doc[page_idx]

    if replace_anhang and page_idx == 0:
        replace_anhang_letter_on_page(page, target_letter=anhang_letter)

    if remove_logo:
        remove_maxqda_logo_from_page(page)

    if remove_old_pagination:
        remove_center_pagination_from_page(page)

    arial_path = get_system_arial_path()
    font_name = "helv"
    font_obj = None
    if arial_path:
        try:
            font_obj = pymupdf.Font(fontfile=arial_path)
            font_name = "ArialCustom"
        except Exception:
            font_obj = None

    stamp_page_number(
        page=page,
        page_number=start_number,
        style=style,
        font_name=font_name,
        font_obj=font_obj,
        arial_path=arial_path,
        use_relative=True,
    )

    if footer_only:
        clip_rect = pymupdf.Rect(0, page.rect.height * 0.80, page.rect.width, page.rect.height)
        pix = page.get_pixmap(clip=clip_rect, dpi=150)
    else:
        pix = page.get_pixmap(dpi=120)

    png_bytes = pix.tobytes("png")
    doc.close()
    return png_bytes
