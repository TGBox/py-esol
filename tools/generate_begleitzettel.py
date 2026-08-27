"""
Module for generating Begleitzettel PDF documents for ESOL invoicing/corrections.
Matches the exact layout, font sizing, line positioning, and labels of BegleitzettelBsp.pdf.
"""

from typing import Dict, Any, Optional
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def generate_begleitzettel_pdf(data: Dict[str, Any], output_path: str) -> str:
    """
    Generates a Begleitzettel PDF file according to the specifications in BegleitzettelBsp.pdf.

    :param data: Dictionary containing form values for header, address, and invoice fields.
    :param output_path: File path where the PDF will be saved.
    :return: Absolute path to the generated PDF.
    """
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4  # 595.27559 x 841.88976 points

    # --- 1. Top Left Header Title ---
    c.setFont("Helvetica-Bold", 11)
    c.drawString(60, height - 70, "Begleitzettel für Urbelege zur")
    c.drawString(60, height - 84, "Abrechnung nach § 301a/§302 SGB V")

    # --- 2. Top Right Sender Info Block ---
    c.setFont("Helvetica", 10)
    sender_y = height - 60
    sender_x = 330
    line_gap = 13.5

    sender_lines = [
        data.get("absender_name", ""),
        data.get("absender_strasse", ""),
        data.get("absender_plz_ort", ""),
        data.get("absender_telefon", ""),
        data.get("absender_email", ""),
    ]
    for line in sender_lines:
        if line:
            c.drawString(sender_x, sender_y, str(line))
        sender_y -= line_gap

    # --- 3. Fold Marks (Falzmarken) on Left Edge ---
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0.4, 0.4, 0.4)
    c.line(20, height - 238, 35, height - 238)  # Top fold mark (~y=604 pt from bottom)
    c.line(20, height - 535, 35, height - 535)  # Bottom fold mark (~y=306 pt from bottom)

    # --- 4. Sender Line above Address Window (Fensterzeile) ---
    c.setFont("Helvetica", 8)
    fensterzeile = data.get("absender_fensterzeile", "").strip()
    if fensterzeile:
        c.drawString(60, height - 150, fensterzeile)

    # --- 5. Address Window Recipient (Empfänger) ---
    c.setFont("Helvetica", 10.5)
    recipient_y = height - 170
    recipient_x = 60
    recipient_gap = 14

    recipient_lines = [
        data.get("empfaenger_zeile1", ""),
        data.get("empfaenger_zeile2", ""),
        data.get("empfaenger_zeile3", ""),
    ]
    for line in recipient_lines:
        if line:
            c.drawString(recipient_x, recipient_y, str(line))
        recipient_y -= recipient_gap

    # --- 6. Main Data Key-Value Fields ---
    # Field definitions: (Label text, dictionary key)
    fields = [
        ("IK Kostenträger:", "ik_kostentraeger"),
        ("Name der Krankenkasse:", "name_krankenkasse"),
        ("IK Rechnungssteller:", "ik_rechnungssteller"),
        ("Name d. Rechnungsstellers:", "name_rechnungssteller"),
        ("Rechnungsnummer:", "rechnungsnummer"),
        ("Rechnungsdatum:", "rechnungsdatum"),
        ("erste Belegnummer:", "erste_belegnummer"),
        ("letzte Belegnummer:", "letzte_belegnummer"),
        ("Anzahl Urbelege:", "anzahl_urbelege"),
    ]

    label_x = 65
    val_x = 230
    start_y = height - 425
    field_gap = 28.5

    c.setFont("Helvetica", 10.5)
    curr_y = start_y

    for label, key in fields:
        val = str(data.get(key, ""))
        c.drawString(label_x, curr_y, label)
        c.drawString(val_x, curr_y, val)
        curr_y -= field_gap

    c.showPage()
    c.save()
    return output_path
