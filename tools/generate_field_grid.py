#!/usr/bin/env python3
"""
Generiert ein aktualisiertes Kalibrierungsbild für Muster 13 mit Zuzahlung/Unfall/BVG
auf der linken Seite (x=150) und Heilmittelbereich 14-18 nach links/oben verschoben.
"""

import os
from PIL import Image, ImageDraw, ImageFont

def generate_numbered_calibration_image():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(base_dir)
    asset_path = os.path.join(project_root, "assets", "Muster13_1280x1280.jpg")

    img = Image.open(asset_path).convert("RGB")
    draw = ImageDraw.Draw(img)

    try:
        font_box = ImageFont.truetype("consolab.ttf", 22)
        font_label = ImageFont.truetype("consola.ttf", 15)
    except IOError:
        font_box = font_label = ImageFont.load_default()

    # Nach User-Korrektur angepasste Boxen
    field_boxes = [
        # Checkboxen Zuzahlungsfrei, Zuzahlungspflicht, Unfallfolgen, BVG (oben links x=150)
        (10, 150, 25, 30, 25, "Zuzahlung gebührenfrei [X]"),
        (11, 150, 55, 30, 25, "Zuzahlung gebührenpflichtig [X]"),

        # Personalienfeld oben links
        (1, 245, 55, 330, 35, "Krankenkasse / IK (GUT)"),
        (2, 245, 115, 330, 35, "Name, Vorname des Versicherten (GUT)"),
        (3, 610, 175, 130, 30, "geb. am"),
        (4, 245, 235, 160, 30, "Kostenträgerkennung IK (GUT)"),
        (5, 430, 235, 160, 30, "Versicherten-Nr."),
        (6, 610, 235, 100, 30, "Status"),
        (7, 245, 295, 160, 30, "Betriebsstätten-Nr. BSNR (GUT)"),
        (8, 430, 295, 160, 30, "Arzt-Nr. LANR"),
        (9, 610, 295, 130, 30, "Datum Verordnungsdatum"),

        # Verordnungsart
        (12, 770, 25, 30, 25, "Verordnungsart Erst [X]"),
        (13, 770, 55, 30, 25, "Verordnungsart Folge [X]"),

        # Heilmittelbereich (14-18 nach oben/links verschoben x=610)
        (14, 610, 140, 30, 30, "Bereich Physiotherapie [X]"),
        (15, 610, 180, 30, 30, "Bereich Podologie [X]"),
        (16, 610, 220, 30, 30, "Bereich Logopädie [X]"),
        (17, 610, 260, 30, 30, "Bereich Ergotherapie [X]"),
        (18, 610, 300, 30, 30, "Bereich Ernährungstherapie [X]"),

        # Diagnosefeld
        (19, 245, 405, 520, 35, "Behandlungsrelevante Diagnose(n)"),
        (20, 245, 515, 100, 30, "Diagnosegruppe"),
        (21, 360, 515, 110, 30, "ICD-10 Code"),
        (22, 510, 515, 90, 30, "Leitsymptomatik Code"),
        (23, 245, 575, 540, 35, "Leitsymptomatik Freitext"),

        # Heilmittel-Tabelle
        (24, 245, 745, 480, 35, "Heilmittel Pos 1 Bezeichnung"),
        (25, 970, 745, 70, 35, "Heilmittel Pos 1 Einheiten"),
        (26, 245, 795, 480, 35, "Heilmittel Pos 2 Bezeichnung"),
        (27, 970, 795, 70, 35, "Heilmittel Pos 2 Einheiten"),
    ]

    box_color = (230, 30, 30)      # Roter Rahmen
    num_bg = (0, 100, 200)         # Blaue Badge für Nummer
    num_fg = (255, 255, 255)       # Weißer Text

    for num, x, y, w, h, name in field_boxes:
        draw.rectangle([x, y, x + w, y + h], outline=box_color, width=3)
        badge_w, badge_h = 28, 24
        draw.rectangle([x, y - badge_h, x + badge_w, y], fill=num_bg, outline=box_color)
        draw.text((x + 4, y - badge_h + 2), str(num), fill=num_fg, font=font_box)
        draw.text((x + badge_w + 4, y - badge_h + 4), name[:22], fill=(0, 0, 120), font=font_label)

    out_asset = os.path.join(project_root, "assets", "muster13_feld_nummerierung.jpg")
    img.save(out_asset)

    artifact_dir = r"C:\Users\DaniBani\.gemini\antigravity-ide\brain\d5b333fd-e7e2-488d-bfa9-ccff44aba9e9"
    if os.path.exists(artifact_dir):
        img.save(os.path.join(artifact_dir, "muster13_feld_nummerierung.jpg"))

if __name__ == "__main__":
    generate_numbered_calibration_image()
