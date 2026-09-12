"""
Automatisches Analysieren und Durchnummerieren von PDF-Dokumenten mit PyMuPDF.

Starten:
- Ohne Argumente (`python main.py`): Öffnet die grafische Benutzeroberfläche (GUI) mit Drag & Drop.
- Mit Argumenten (`python main.py <datei.pdf> --start 43`): Führt die Nummerierung direkt im Terminal aus.
"""

from __future__ import annotations

import argparse
from pathlib import Path

# Re-Export aller Kernfunktionen für maximale Kompatibilität
from pdf_processor import (
    HARDCODED_STYLE,
    PageNumberStyle,
    add_page_numbers,
    analyze_reference_pdf,
    remove_center_pagination_from_page,
    remove_maxqda_logo_from_page,
    render_page_preview,
)


def print_style_summary(style: PageNumberStyle, source_name: str = "Seite.pdf") -> None:
    """Gibt eine detaillierte Zusammenfassung des analysierten Stils aus."""
    pt_to_mm = 25.4 / 72.0
    print("=" * 65)
    print(f"  SEITENZAHLEN-STILANALYSE ({source_name})")
    print("=" * 65)
    print(f"  Schriftart:          {style.font_name}")
    print(f"  Schriftgröße:        {style.font_size:.2f} pt")
    print(f"  Textfarbe:           RGB {style.color}")
    print("-" * 65)
    print(f"  Rechter Rand:")
    print(f"    - Relativ:         {style.relative_margin_right * 100:.2f}% der Seitenbreite")
    print(f"    - Absolut (A4):    {style.margin_right_pt:.2f} pt ({style.margin_right_pt * pt_to_mm:.2f} mm)")
    print(f"  Unterer Rand (Grundlinie/Baseline):")
    print(f"    - Relativ:         {style.relative_baseline_bottom * 100:.2f}% der Seitenhöhe")
    print(f"    - Absolut (A4):    {style.baseline_bottom_pt:.2f} pt ({style.baseline_bottom_pt * pt_to_mm:.2f} mm)")
    print(f"  Unterer Rand (Bounding-Box Unterkante):")
    print(f"    - Relativ:         {style.relative_bbox_bottom * 100:.2f}% der Seitenhöhe")
    print(f"    - Absolut (A4):    {style.bbox_bottom_pt:.2f} pt ({style.bbox_bottom_pt * pt_to_mm:.2f} mm)")
    print("=" * 65)


def main() -> None:
    """Kommandozeilenschnittstelle und Ausführung."""
    parser = argparse.ArgumentParser(
        description="PDF-Seitennummerierung im exakten Stil aus Seite.pdf (mit Logo-Entfernung und Drag & Drop UI)."
    )
    parser.add_argument(
        "input_pdf",
        nargs="?",
        default=None,
        help="Pfad zur PDF-Datei. Wenn weggelassen, startet die grafische Oberfläche (GUI).",
    )
    parser.add_argument(
        "-s", "--start",
        type=int,
        default=1,
        help="Startnummer für die erste Seite (Standard: 1).",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Pfad für die nummerierte Ausgabe-PDF (Standard: <Name>_numbered.pdf).",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Grafische Benutzeroberfläche erzwingen.",
    )
    parser.add_argument(
        "--no-remove-logo",
        action="store_true",
        help="MAXQDA-Logo unten rechts NICHT entfernen.",
    )
    parser.add_argument(
        "--remove-old-pagination",
        action="store_true",
        help="Bestehende zentrierte Seitenzahlen (z. B. '1/8') in der Fußzeile entfernen.",
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Nur 'Seite.pdf' analysieren und Werte anzeigen, keine Datei nummerieren.",
    )

    args = parser.parse_args()

    # Falls keine PDF übergeben wurde und keine reine Analyse gewünscht ist -> GUI starten
    if (args.input_pdf is None and not args.analyze_only) or args.gui:
        try:
            from gui import run_gui
            run_gui()
            return
        except ImportError as e:
            print(f"[Fehler] GUI konnte nicht gestartet werden: {e}")
            print("Führe stattdessen die Terminal-Version aus...")

    # 1. Automatische Analyse von 'Seite.pdf' durchführen, falls vorhanden
    ref_file = Path("Seite.pdf")
    if ref_file.exists():
        analyzed_style = analyze_reference_pdf(ref_file, target_number="43")
        print_style_summary(analyzed_style, source_name="Seite.pdf (Live analysiert)")
    else:
        print_style_summary(HARDCODED_STYLE, source_name="Hardcoded-Default (Seite.pdf bereits gelöscht)")

    # 2. Wenn eine Eingabedatei übergeben wurde, diese nummerieren
    if args.input_pdf:
        output_file = add_page_numbers(
            input_pdf=args.input_pdf,
            output_pdf=args.output,
            start_number=args.start,
            remove_logo=not args.no_remove_logo,
            remove_old_pagination=args.remove_old_pagination,
            style=HARDCODED_STYLE,
        )
        print(f"\n[Erfolg] Nummerierte PDF erfolgreich gespeichert unter:\n  -> {output_file.resolve()}\n")


if __name__ == "__main__":
    main()

