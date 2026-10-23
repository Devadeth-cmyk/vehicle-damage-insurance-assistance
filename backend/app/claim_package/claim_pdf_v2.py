"""
claim_pdf_v2.py  --  Professional claim-report PDF for the Digital Vehicle Insurance Claim Package

Design rules
------------
* The PDF is rendered ONLY from the claim_package.json dict (single source of truth).
  No notebook globals (CLAIM_INFO, claim_analysis, repair_estimate ...) are read.
* Unicode-safe font (DejaVu Sans) so the rupee sign renders correctly.
* Every table cell is a Paragraph, so long values wrap instead of overflowing.
* Cover sheet -> parties -> findings -> verification -> consistency -> estimate ->
  documents -> evidence register -> annotated evidence -> methodology -> sign-off.

Usage (Colab, replaces the whole "18. PDF CLAIM REPORT" cell)
-------------------------------------------------------------
    from claim_pdf_v2 import build_claim_pdf
    build_claim_pdf(
        claim_package_json,                      # the dict you already dump to claim_package.json
        PDF_PATH,
        original_dir=ORIGINAL_DIR,
        annotated_dir=ANNOTATED_DIR,
        supporting_dir=SUPPORTING_DOCS_DIR,      # optional
    )
"""
import hashlib
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate, CondPageBreak, Frame, HRFlowable, Image as RLImage,
    KeepTogether, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

# --------------------------------------------------------------------------------------
# Fonts (the built-in Helvetica has no rupee glyph -> would render as a box / blank)
# --------------------------------------------------------------------------------------
try:
    import matplotlib as _mpl
    _MPL_FONTS = str(Path(_mpl.get_data_path()) / "fonts" / "ttf")   # ships DejaVu Sans
except Exception:
    _MPL_FONTS = ""
_FONT_DIRS = [
    "/usr/share/fonts/truetype/dejavu",   # Colab / Ubuntu
    _MPL_FONTS,
    "/usr/share/fonts/dejavu",
    "/Library/Fonts",
    "C:/Windows/Fonts",
]
F, FB, FI, FBI = "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique"
RUPEE = "Rs. "


def _register_fonts():
    global F, FB, FI, FBI, RUPEE
    for d in _FONT_DIRS:
        if not d:
            continue
        reg = Path(d) / "DejaVuSans.ttf"
        if reg.exists() and (Path(d) / "DejaVuSans-BoldOblique.ttf").exists():
            pdfmetrics.registerFont(TTFont("CP-Sans", str(reg)))
            pdfmetrics.registerFont(TTFont("CP-Sans-Bold", str(Path(d) / "DejaVuSans-Bold.ttf")))
            pdfmetrics.registerFont(TTFont("CP-Sans-Italic", str(Path(d) / "DejaVuSans-Oblique.ttf")))
            pdfmetrics.registerFont(TTFont("CP-Sans-BoldItalic", str(Path(d) / "DejaVuSans-BoldOblique.ttf")))
            pdfmetrics.registerFontFamily(
                "CP-Sans", normal="CP-Sans", bold="CP-Sans-Bold",
                italic="CP-Sans-Italic", boldItalic="CP-Sans-BoldItalic",
            )
            F, FB, FI, FBI = "CP-Sans", "CP-Sans-Bold", "CP-Sans-Italic", "CP-Sans-BoldItalic"
            RUPEE = "\u20b9"
            return True
    return False


_register_fonts()

# --------------------------------------------------------------------------------------
# Palette / layout
# --------------------------------------------------------------------------------------
NAVY = colors.HexColor("#1F3A5F")
INK = colors.HexColor("#1B2430")
MUTED = colors.HexColor("#5B6675")
LINE = colors.HexColor("#C9D1DC")
PANEL = colors.HexColor("#F3F5F8")
GREEN = colors.HexColor("#2E7D32")
AMBER = colors.HexColor("#B26A00")
AMBER_BG = colors.HexColor("#FFF4E0")
RED = colors.HexColor("#C62828")
RED_BG = colors.HexColor("#FDECEA")
BLUE = colors.HexColor("#1565C0")
GREY = colors.HexColor("#6B7280")

SEV_COLOR = {"Minor": colors.HexColor("#2E7D32"), "Moderate": colors.HexColor("#E68A00"),
             "Severe": colors.HexColor("#C62828")}

PAGE_W, PAGE_H = A4
LM = RM = 16 * mm
TM, BM = 22 * mm, 18 * mm
CW = PAGE_W - LM - RM  # content width (178 mm)

REVIEW_REASON_TEXT = {
    "no_part_matched": "No vehicle part was matched to this damage region",
    "low_part_confidence": "Vehicle-part confidence is below the review threshold",
    "low_damage_confidence": "Damage-detection confidence is below the review threshold",
    "low_spatial_overlap": "Damage region barely overlaps any part mask (part set to 'unknown')",
    "ambiguous_part_match": "Two or more parts scored almost equally for this damage region",
    "implausible_damage_part_combination": "Damage type is not physically plausible for the assigned part",
}

REQUIRED_FIELDS = [
    ("customer", "customer_name", "Customer name"),
    ("customer", "contact_number", "Contact number"),
    ("vehicle", "vehicle_registration", "Vehicle registration"),
    ("vehicle", "policy_number", "Policy number"),
    ("accident", "accident_date", "Accident date"),
    ("accident", "accident_location", "Accident location"),
]
REQUIRED_DOCS = [("vehicle_registration", "Vehicle registration certificate (RC)"),
                 ("driving_licence", "Driving licence"),
                 ("policy_document", "Insurance policy / schedule")]


def _styles():
    def ps(name, **kw):
        base = dict(fontName=F, fontSize=8.5, leading=11.5, textColor=INK)
        base.update(kw)
        return ParagraphStyle(name, **base)

    return {
        "body": ps("body"),
        "small": ps("small", fontSize=7.5, leading=10, textColor=MUTED),
        "cell": ps("cell", fontSize=8, leading=10.5),
        "cell_b": ps("cell_b", fontName=FB, fontSize=8, leading=10.5),
        "cell_c": ps("cell_c", fontSize=8, leading=10.5, alignment=TA_CENTER),
        "cell_r": ps("cell_r", fontSize=8, leading=10.5, alignment=TA_RIGHT),
        "hdr": ps("hdr", fontName=FB, fontSize=7.8, leading=10, textColor=colors.white),
        "label": ps("label", fontName=FB, fontSize=7.8, leading=10.5, textColor=MUTED),
        "H1": ps("H1", fontName=FB, fontSize=12.5, leading=16, textColor=NAVY,
                 spaceBefore=12, spaceAfter=2, keepWithNext=1),
        "H2": ps("H2", fontName=FB, fontSize=9.5, leading=13, textColor=INK,
                 spaceBefore=8, spaceAfter=3, keepWithNext=1),
        "title": ps("title", fontName=FB, fontSize=19, leading=23, textColor=colors.white),
        "subtitle": ps("subtitle", fontSize=9, leading=12, textColor=colors.HexColor("#D5DEEC")),
        "kpi_n": ps("kpi_n", fontName=FB, fontSize=15, leading=18, alignment=TA_CENTER, textColor=NAVY),
        "kpi_t": ps("kpi_t", fontName=FB, fontSize=8.5, leading=11, alignment=TA_CENTER, textColor=NAVY),
        "kpi_l": ps("kpi_l", fontSize=7, leading=9, alignment=TA_CENTER, textColor=MUTED),
        "banner": ps("banner", fontName=FB, fontSize=10, leading=13, textColor=colors.white),
        "quote": ps("quote", fontName=FI, fontSize=8.5, leading=12, textColor=INK),
    }


S = _styles()


# --------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------
def esc(v):
    return escape("" if v is None else str(v))


def P(text, style="cell"):
    return Paragraph(text, S[style])


def val(v, style="cell"):
    """Value cell; blank -> red 'Not provided' so gaps are visible to the reviewer."""
    if v is None or str(v).strip() == "":
        return Paragraph(f'<font color="#C62828"><i>Not provided</i></font>', S[style])
    return Paragraph(esc(v), S[style])


def inr(x):
    try:
        return f"{RUPEE}{float(x):,.2f}"
    except (TypeError, ValueError):
        return "-"


def pct(x):
    try:
        return f"{float(x) * 100:.0f}%"
    except (TypeError, ValueError):
        return "-"


def _fmt_ts(iso):
    try:
        dt = datetime.fromisoformat(str(iso).rstrip("Z")).replace(tzinfo=timezone.utc)
    except Exception:
        return str(iso), ""
    try:
        from zoneinfo import ZoneInfo
        ist = dt.astimezone(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y, %H:%M IST")
    except Exception:
        ist = ""
    return dt.strftime("%d %b %Y, %H:%M UTC"), ist


def _table(data, widths, header=True, zebra=True, extra=None, repeat=1):
    t = Table(data, colWidths=widths, repeatRows=repeat if header else 0)
    st = [
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), NAVY)]
    if zebra:
        for r in range(1 if header else 0, len(data)):
            if (r % 2) == 0:
                st.append(("BACKGROUND", (0, r), (-1, r), PANEL))
    if extra:
        st += extra
    t.setStyle(TableStyle(st))
    return t


def _kv_grid(pairs):
    """Two label/value pairs per row -> compact, professional form layout."""
    lw, vw = 27 * mm, 62 * mm
    rows, extra = [], []
    for i in range(0, len(pairs), 2):
        chunk = pairs[i:i + 2]
        row = []
        for label, value in chunk:
            row += [P(esc(label), "label"), val(value)]
        while len(row) < 4:
            row += [P("", "label"), P("")]
        rows.append(row)
    t = Table(rows, colWidths=[lw, vw, lw, vw])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("BACKGROUND", (0, 0), (0, -1), PANEL),
        ("BACKGROUND", (2, 0), (2, -1), PANEL),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _section(title):
    hr = HRFlowable(width="100%", thickness=1.2, color=NAVY, spaceBefore=0, spaceAfter=5)
    hr.keepWithNext = 1
    return [CondPageBreak(50 * mm), Paragraph(esc(title), S["H1"]), hr]


def _badge(text, color, width=None):
    t = Table([[Paragraph(f'<font color="white"><b>{esc(text)}</b></font>', S["cell_c"])]],
              colWidths=[width] if width else None)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), color),
                           ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                           ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6)]))
    return t


def _fit_image(path, max_w, max_h, tmpdir):
    """Aspect-ratio-preserving image (original code forced 170x105 mm and distorted photos).
    Re-encodes to a bounded JPEG so webp/png inputs work and the PDF stays small."""
    if not path or not Path(path).exists():
        return None
    im = PILImage.open(path)
    # ReportLab can embed JPEGs directly. Avoid creating a throwaway copy for
    # the common case; this also preserves the submitted photo bytes outside
    # the PDF and avoids temp-directory permission failures on Windows.
    if im.format == "JPEG" and im.mode in ("RGB", "L"):
        w, h = im.size
        k = min(max_w / w, max_h / h)
        return RLImage(str(path), width=w * k, height=h * k)
    im = im.convert("RGB")
    im.thumbnail((1600, 1600))
    out = Path(tmpdir) / (Path(path).stem + "_pdf.jpg")
    im.save(out, "JPEG", quality=85)
    w, h = im.size
    k = min(max_w / w, max_h / h)
    return RLImage(str(out), width=w * k, height=h * k)


def _sha12(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------------------
# Data shaping
# --------------------------------------------------------------------------------------
def _flatten(pkg):
    out, n = [], 0
    images = pkg.get("ai_assessment", {}).get("images", [])
    for img in images:
        img_name = img.get("image", "photograph.jpg")
        stem = Path(img_name).stem
        for d in img.get("detections", []):
            n += 1
            item = dict(d)
            part_name = item.get("part") or item.get("part_name") or item.get("vehicle_part") or "Body Panel / Bumper"
            damage_type = item.get("damage_type") or item.get("damage") or item.get("type") or "Scratch / Dent"
            severity = item.get("severity") or "Minor"
            
            item["part"] = part_name
            item["damage_type"] = damage_type
            item["severity"] = severity
            item.update(
                ref=d.get("ref") or f"F{n:02d}",
                image=img_name,
                det_id=d.get("detection_id") or f"{stem}_D{d.get('damage_id', n)}"
            )
            out.append(item)
    return out


def _status(d):
    vs = d.get("verification_status", "")
    if vs == "TECHNICIAN_VERIFIED":
        return "Verified", GREEN
    if vs == "TECHNICIAN_REJECTED":
        return "Rejected", GREY
    if d.get("requires_review"):
        return "Needs review", AMBER
    return "AI: no flags", BLUE   # deliberately NOT called 'confirmed' - only a human confirms


def _is_placeholder_narrative(text):
    t = (text or "").strip().lower()
    return (not t or t in {
        "n/a", "na", "none", "unknown", "not provided",
        "no description provided", "please describe the accident",
    } or "please verify the visible" in t)


def _assess_readiness(pkg, findings):
    """Return (status_text, colour, [ (level, message) ... ])."""
    issues = []
    missing = [lbl for sec, key, lbl in REQUIRED_FIELDS
               if not str(pkg.get(sec, {}).get(key, "")).strip()]
    narrative = pkg.get("accident", {}).get("accident_description", "")
    placeholder = _is_placeholder_narrative(narrative)
    if missing:
        issues.append(("high", "Mandatory details missing: " + ", ".join(missing) + "."))
    if placeholder:
        issues.append(("high", "Accident description is empty or a placeholder, so the claim-vs-evidence "
                               "check cannot be interpreted."))
    unverified = [f for f in findings if _status(f)[0] in ("Needs review", "AI: no flags")]
    if unverified:
        flagged = sum(1 for f in unverified if f.get("requires_review"))
        issues.append(("high", f"{len(unverified)} of {len(findings)} findings are not yet technician-verified "
                               f"({flagged} carry AI review flags)."))
    est = pkg.get("repair_estimate", {})
    if est.get("unpriced_findings"):
        issues.append(("med", f"{len(est['unpriced_findings'])} finding(s) could not be priced "
                              f"(unknown part or no rate)."))
    if not est.get("workshop_items"):
        issues.append(("med", "No workshop repair estimate has been entered; only an AI indicative "
                              "figure is available."))
    cons = pkg.get("evidence_consistency", {})
    if cons.get("status") == "POTENTIAL_MISMATCH" and not placeholder:
        n = len(cons.get("detected_but_not_explicitly_reported", []))
        m = len(cons.get("claimed_but_not_detected", []))
        bits = []
        if n:
            bits.append(f"{n} detected item(s) are not described in the narrative")
        if m:
            bits.append(f"{m} item(s) in the narrative were not detected in any photograph")
        issues.append(("med", "Consistency check: " + "; ".join(bits) + "."))
    qf = [q for q in pkg.get("evidence", {}).get("quality", []) if q.get("flags")]
    if qf:
        issues.append(("med", f"{len(qf)} photograph(s) carry quality/integrity flags (see Section 7)."))

    vehicle = pkg.get("vehicle", {})
    make = str(vehicle.get("make") or "").strip().lower()
    model = str(vehicle.get("model") or "").strip().lower()
    variant = str(vehicle.get("variant") or "").strip().lower()
    vehicle_type = str(vehicle.get("vehicle_type") or "").strip().lower()
    if "harrier" in model and vehicle_type and not any(
        kind in vehicle_type for kind in ("suv", "sport utility", "utility vehicle")
    ):
        issues.append(("high", "Vehicle type conflicts with the model listed; verify the vehicle details against the registration certificate."))
    if "tata" in make and "vxi" in variant:
        issues.append(("med", "The listed Tata variant may not match the vehicle; verify it against the registration certificate."))

    policy_type = str(pkg.get("accident", {}).get("policy_type") or "").strip().lower()
    if policy_type in {"third party", "third-party", "third party only", "liability only"} and est.get("workshop_items"):
        issues.append(("high", "Policy is listed as third-party while the workshop estimate covers the insured vehicle; verify own-damage coverage in the policy schedule."))

    for finding in findings:
        part = str(finding.get("part") or "").strip().lower().replace("_", " ")
        damage = str(finding.get("damage_type") or "").strip().lower().replace("_", " ")
        if part == "hood" and any(token in damage for token in ("lamp", "headlight", "head lamp")):
            issues.append(("med", f"Finding {finding['ref']} pairs the hood with lamp damage; confirm the damaged part and finding label against the photograph."))
        if part in {"unknown", "body panel / bumper"}:
            issues.append(("med", f"Finding {finding['ref']} has no confirmed vehicle part; identify the part before relying on its repair estimate."))

    workshop = pkg.get("workshop", {})
    if not workshop.get("technician_signature") or not workshop.get("authorised_signatory_signature"):
        issues.append(("med", "Workshop signature fields are blank; complete the applicable manual sign-off in Section 10 before final submission."))

    det = pkg.get("document_status", {}).get("detected_document_categories", {})
    miss_docs = [lbl for key, lbl in REQUIRED_DOCS if not det.get(key)]
    if miss_docs:
        issues.append(("med", "Supporting documents not detected: " + "; ".join(miss_docs) + "."))
    for review in pkg.get("document_status", {}).get("review", {}).values():
        if not isinstance(review, dict) or str(review.get("status", "")).startswith("Verified"):
            continue
        if review.get("note"):
            issues.append(("high", str(review["note"])))

    if not findings:
        issues.append(("high", "The AI detected no damage. A technician must inspect the vehicle and add the "
                               "findings manually before this package is submitted."))
    if missing or placeholder:
        return "DRAFT - INCOMPLETE", RED, issues
    if unverified or not findings:
        return "PENDING TECHNICIAN VERIFICATION", AMBER, issues
    if issues:
        return "VERIFIED - OPEN ITEMS REMAIN", AMBER, issues
    return "VERIFIED - READY FOR INSURER REVIEW", GREEN, issues


# --------------------------------------------------------------------------------------
# Page chrome + doc
# --------------------------------------------------------------------------------------
def _canvas_factory(meta):
    class _Numbered(canvas.Canvas):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self._pages = []

        def showPage(self):
            self._pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._pages)
            for state in self._pages:
                self.__dict__.update(state)
                self._chrome(total)
                super().showPage()
            super().save()

        def _chrome(self, total):
            pg = self._pageNumber
            self.saveState()
            if pg > 1:
                self.setFont(FB, 7.5)
                self.setFillColor(NAVY)
                self.drawString(LM, PAGE_H - 12 * mm, "DIGITAL VEHICLE INSURANCE CLAIM PACKAGE")
                self.setFont(F, 7.5)
                self.setFillColor(MUTED)
                self.drawRightString(PAGE_W - RM, PAGE_H - 12 * mm, f"Claim ID: {meta['claim_id']}")
                self.setStrokeColor(LINE)
                self.setLineWidth(0.6)
                self.line(LM, PAGE_H - 14 * mm, PAGE_W - RM, PAGE_H - 14 * mm)
            self.setStrokeColor(LINE)
            self.setLineWidth(0.6)
            self.line(LM, 13 * mm, PAGE_W - RM, 13 * mm)
            self.setFont(F, 6.8)
            self.setFillColor(MUTED)
            self.drawString(LM, 9 * mm, "CONFIDENTIAL - contains personal data. AI-assisted assessment; "
                                        "not an insurance decision.")
            self.drawRightString(PAGE_W - RM, 9 * mm, f"Page {pg} of {total}")
            self.restoreState()

    return _Numbered


class _Doc(BaseDocTemplate):
    def __init__(self, path, **kw):
        super().__init__(path, pagesize=A4, leftMargin=LM, rightMargin=RM, topMargin=TM,
                         bottomMargin=BM, **kw)
        frame = Frame(LM, BM, CW, PAGE_H - TM - BM, id="main", leftPadding=0, rightPadding=0,
                      topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate(id="main", frames=[frame])])

    def afterFlowable(self, fl):
        if isinstance(fl, Paragraph) and fl.style.name == "H1":
            text = fl.getPlainText()
            key = "sec-" + hashlib.md5(text.encode()).hexdigest()[:8]
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, 0, 0)
            self.notify("TOCEntry", (0, text, self.page, key))


# --------------------------------------------------------------------------------------
# Sections
# --------------------------------------------------------------------------------------
def _cover(pkg, findings, status_text, status_color, issues):
    fl = []
    gen_utc, gen_ist = _fmt_ts(pkg.get("generated_at_utc", ""))
    title = Table([[P("DIGITAL VEHICLE INSURANCE<br/>CLAIM PACKAGE", "title")],
                   [P("AI-assisted damage assessment &nbsp;|&nbsp; technician verification &nbsp;|&nbsp; "
                      "insurer review", "subtitle")]], colWidths=[CW])
    title.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY),
                               ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                               ("TOPPADDING", (0, 0), (0, 0), 12), ("BOTTOMPADDING", (0, 1), (-1, -1), 10)]))
    fl += [title, Spacer(1, 6)]

    v, a, w, c = pkg.get("vehicle", {}), pkg.get("accident", {}), pkg.get("workshop", {}), pkg.get("customer", {})
    fl.append(_kv_grid([
        ("Claim ID", pkg.get("claim_id")),
        ("Package version", pkg.get("package_version")),
        ("Insurer", v.get("insurance_company")),
        ("Policy number", v.get("policy_number")),
        ("Vehicle", f"{v.get('make', '')} {v.get('model', '')} ({v.get('vehicle_registration', '')})".strip()),
        ("Insured / customer", c.get("customer_name")),
        ("Workshop", w.get("workshop_name")),
        ("Technician", w.get("technician_name")),
        ("Date of loss", a.get("accident_date")),
        ("Generated", f"{gen_utc}" + (f"  ({gen_ist})" if gen_ist else "")),
    ]))
    fl.append(Spacer(1, 6))

    ban = Table([[P(f"PACKAGE STATUS: {esc(status_text)}", "banner")]], colWidths=[CW])
    ban.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), status_color),
                             ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 6),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    fl += [ban, Spacer(1, 6)]

    est = pkg.get("repair_estimate", {})
    cons = pkg.get("evidence_consistency", {}).get("status", "-")
    verified = sum(1 for f in findings if _status(f)[0] == "Verified")
    flagged = sum(1 for f in findings if _status(f)[0] == "Needs review")
    if _is_placeholder_narrative(pkg.get("accident", {}).get("accident_description", "")) or cons == "NOT_ASSESSED":
        cons = "NOT_ASSESSED"
    cons_txt = {"NOT_ASSESSED": "Not assessed", "CONSISTENT": "Consistent", "POTENTIAL_MISMATCH": "Potential mismatch",
                "INSUFFICIENT_EVIDENCE": "Insufficient"}.get(cons, cons)
    tiles = [
        (str(len(pkg["ai_assessment"]["images"])), "Photographs"),
        (str(len(findings)), "AI findings"),
        (str(flagged), "Flagged for review"),
        (f"{verified}/{sum(1 for f in findings if _status(f)[0] != 'Rejected')}", "Technician-verified"),
        (cons_txt, "Narrative vs evidence"),
        (inr(est.get("ai_preliminary_total", 0)).replace(".00", ""), "AI indicative (unverified)"),
    ]
    tw = CW / len(tiles)
    kpi = Table([[P(esc(n), "kpi_t" if len(n) > 9 else "kpi_n") for n, _ in tiles], [P(esc(l), "kpi_l") for _, l in tiles]],
                colWidths=[tw] * len(tiles))
    kpi.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                             ("BACKGROUND", (0, 0), (-1, -1), PANEL),
                             ("TOPPADDING", (0, 0), (-1, 0), 6), ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
                             ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    fl += [kpi, Spacer(1, 7)]

    # Open items panel
    if issues:
        rows = [[P("<b>Open items before insurer submission</b>", "body")]]
        for lvl, msg in issues:
            colour = "#C62828" if lvl == "high" else "#B26A00"
            rows.append([Paragraph(f'<font color="{colour}">&#9679;</font>&nbsp; {esc(msg)}', S["cell"])])
        panel = Table(rows, colWidths=[CW])
        panel.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, AMBER), ("BACKGROUND", (0, 0), (-1, -1), AMBER_BG),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
        fl += [panel, Spacer(1, 8)]

    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle("toc0", fontName=F, fontSize=8.5, leading=13, textColor=INK,
                                      leftIndent=0, rightIndent=0)]
    toc.dotsMinLevel = 0
    fl += [Paragraph("Contents", S["H2"]), toc, PageBreak()]
    return fl


def _party_section(pkg):
    c, v, a, w = (pkg.get(k, {}) for k in ("customer", "vehicle", "accident", "workshop"))
    fl = _section("1. Claim and Party Details")
    fl += [Paragraph("Customer and vehicle", S["H2"]), _kv_grid([
        ("Name", c.get("customer_name")), ("Contact number", c.get("contact_number")),
        ("Email", c.get("email")), ("Customer address", c.get("customer_address")),
        ("Insurer", v.get("insurance_company")),
        ("Registration", v.get("vehicle_registration")), ("Policy number", v.get("policy_number")),
        ("Make", v.get("make")), ("Model", v.get("model")),
        ("Variant", v.get("variant")), ("Year", v.get("year")),
        ("Vehicle type", v.get("vehicle_type")), ("Fuel type", v.get("fuel_type")),
        ("VIN / chassis", v.get("vin")), ("Engine number", v.get("engine_number")),
        ("Transmission", v.get("transmission")), ("Colour", v.get("color")),
    ])]
    fl += [Paragraph("Loss details", S["H2"]), _kv_grid([
        ("Date of loss", a.get("accident_date")), ("Time", a.get("accident_time")),
        ("Location", a.get("accident_location")), ("Accident type", a.get("accident_type")),
        ("Policy type", a.get("policy_type")), ("Policy expiry", a.get("policy_expiry")),
    ])]
    narrative = a.get("accident_description", "")
    narrative = narrative or ""
    q = Table([[Paragraph(esc(narrative) if narrative.strip() else '<font color="#C62828"><i>Not provided</i></font>',
                          S["quote"])]], colWidths=[CW])
    q.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PANEL), ("LINEBEFORE", (0, 0), (0, -1), 2.5, NAVY),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 6),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    fl += [Paragraph("Customer's description of the accident", S["H2"]), q]
    fl += [Paragraph("Workshop", S["H2"]), _kv_grid([
        ("Workshop name", w.get("workshop_name")), ("Inspecting technician", w.get("technician_name")),
    ])]
    return fl


def _findings_section(pkg, findings):
    fl = _section("2. AI Damage Assessment - Findings Register")
    fl.append(P("Each finding has a reference (F01...) used throughout this report. Confidence values are "
                "model-quality indicators, <b>not</b> claim probabilities. Severity follows the project-defined "
                "rule (see Section 9), not a learned severity model.", "small"))
    fl.append(Spacer(1, 4))

    sev_counts = {}
    for f in findings:
        sev_counts[f.get("severity") or "Unknown"] = sev_counts.get(f.get("severity") or "Unknown", 0) + 1
    parts = sorted({f["part"] for f in findings})
    fl.append(P("<b>Severity mix:</b> " + (", ".join(f"{k}: {v}" for k, v in sev_counts.items()) or "none") +
                "&nbsp;&nbsp;|&nbsp;&nbsp;<b>Parts referenced:</b> " + esc(", ".join(parts) or "none"), "body"))
    fl.append(Spacer(1, 5))

    widths = [11, 30, 26, 22, 19, 15, 15, 15, 25]
    widths = [w * mm for w in widths]
    rows = [[P(h, "hdr") for h in ("Ref", "Image", "Part", "Damage", "Severity", "Dmg conf.", "Part conf.",
                                   "Overlap", "Status")]]
    extra = []
    for i, f in enumerate(findings, start=1):
        st_txt, st_col = _status(f)
        sev = f.get("severity") or "Unknown"
        rows.append([
            P(f["ref"], "cell_b"), P(esc(f["image"])), P(esc(f["part"])), P(esc(f["damage_type"])),
            Paragraph(f'<font color="white"><b>{esc(sev)}</b></font>', S["cell_c"]),
            P(pct(f.get("damage_confidence")), "cell_c"), P(pct(f.get("part_confidence")), "cell_c"),
            P(pct(f.get("overlap_score")), "cell_c"),
            Paragraph(f'<font color="{st_col.hexval().replace("0x", "#")}"><b>{st_txt}</b></font>', S["cell"]),
        ])
        extra.append(("BACKGROUND", (4, i), (4, i), SEV_COLOR.get(sev, GREY)))
        if f.get("part") == "unknown":
            extra.append(("BACKGROUND", (2, i), (2, i), RED_BG))
    if len(rows) == 1:
        rows.append([P("-")] * 9)
    fl.append(_table(rows, widths, extra=extra))

    flagged = [f for f in findings if f.get("requires_review")]
    if flagged:
        fl.append(Paragraph("Why findings were flagged for review", S["H2"]))
        rr = [[P(h, "hdr") for h in ("Ref", "Detection ID", "Review reasons")]]
        for f in flagged:
            reasons = "<br/>".join("&#8226; " + esc(REVIEW_REASON_TEXT.get(r, r)) for r in f.get("review_reasons", []))
            rr.append([P(f["ref"], "cell_b"), P(esc(f["det_id"])), Paragraph(reasons or "-", S["cell"])])
        fl.append(_table(rr, [11 * mm, 42 * mm, 125 * mm]))
    return fl


def _verification_section(pkg, findings):
    fl = _section("3. Technician Verification")
    counts = {"Verified": 0, "Rejected": 0, "Pending": 0}
    rows = [[P(h, "hdr") for h in ("Ref", "Finding (current value)", "Technician decision", "Note")]]
    extra = []
    for i, f in enumerate(findings, start=1):
        st_txt, st_col = _status(f)
        if st_txt in ("Verified", "Rejected"):
            counts[st_txt] += 1
        else:
            counts["Pending"] += 1
        decision = st_txt if st_txt in ("Verified", "Rejected") else "Pending - not yet inspected"
        colour = st_col if st_txt in ("Verified", "Rejected") else AMBER
        cur = f"{esc(f['part'])} / {esc(f['damage_type'])} / {esc(f.get('severity') or 'Unknown')}"
        orig = f.get("ai_original")
        if orig and (orig.get("part"), orig.get("damage_type"), orig.get("severity")) != (
                f["part"], f["damage_type"], f.get("severity")):
            cur += (f'<br/><font size="7" color="#5B6675">AI original: {esc(orig.get("part"))} / '
                    f'{esc(orig.get("damage_type"))} / {esc(orig.get("severity"))}</font>')
        who = f.get("verified_by")
        if who and st_txt in ("Verified", "Rejected"):
            decision += f" by {who}"
        rows.append([
            P(f["ref"], "cell_b"),
            Paragraph(cur, S["cell"]),
            Paragraph(f'<font color="{colour.hexval().replace("0x", "#")}"><b>{esc(decision)}</b></font>', S["cell"]),
            val(f.get("technician_note")),
        ])
    fl.append(P(f"<b>{counts['Verified']}</b> verified &nbsp;|&nbsp; <b>{counts['Rejected']}</b> rejected "
                f"&nbsp;|&nbsp; <b>{counts['Pending']}</b> pending of <b>{len(findings)}</b> findings.", "body"))
    fl.append(Spacer(1, 4))
    if len(rows) > 1:
        fl.append(_table(rows, [11 * mm, 66 * mm, 40 * mm, 61 * mm]))
    fl.append(Spacer(1, 3))
    fl.append(P("Rejected findings are excluded from the insurer-facing assessment once the package is finalised. "
                "Manual signatures, where required, are recorded in Section 10.", "small"))
    return fl


def _consistency_section(pkg, findings):
    cons = pkg.get("evidence_consistency", {})
    narrative = pkg.get("accident", {}).get("accident_description", "")
    placeholder = _is_placeholder_narrative(narrative)
    if placeholder and cons.get("status") != "NOT_ASSESSED":
        cons = {**cons, "status": "NOT_ASSESSED"}
    status = cons.get("status", "INSUFFICIENT_EVIDENCE")
    fl = _section("4. Claim vs Visual Evidence Check")
    col = {"CONSISTENT": GREEN, "POTENTIAL_MISMATCH": AMBER}.get(status, GREY)
    label = "NOT ASSESSED - NARRATIVE MISSING" if placeholder else status.replace("_", " ")
    fl += [_badge(label, GREY if placeholder else col, 70 * mm), Spacer(1, 4)]
    if placeholder:
        fl.append(P("The accident description is empty or a placeholder, so no meaningful comparison against "
                    "the photographs is possible. Enter the customer's description and regenerate.", "body"))
    else:
        fl.append(P("Comparison of the customer's narrative with what the models detected. This is a "
                    "<b>review flag only</b> - not a fraud determination or claim decision.", "body"))
        unm = cons.get("detected_but_not_explicitly_reported", [])
        if unm:
            fl.append(Paragraph("Detected in photographs but not described in the narrative", S["H2"]))
            rows = [[P(h, "hdr") for h in ("Part", "Damage", "Finding ref(s)", "Why flagged")]]
            for u in unm:
                refs = u.get("refs") or [f["ref"] for f in findings if f["part"] == u["part"] and
                                         f["damage_type"].lower() == u["damage_type"].lower()]
                why = {"part_not_mentioned": "Part not mentioned in narrative",
                       "damage_type_not_mentioned": "Part mentioned, damage type differs",
                       "part_unknown": "Part could not be identified from the photograph",
                       }.get(u.get("reason"), "Not described")
                rows.append([P(esc(u["part"])), P(esc(u["damage_type"])), P(esc(", ".join(refs) or "-")), P(why)])
            fl.append(_table(rows, [42 * mm, 34 * mm, 34 * mm, 68 * mm]))
        cnd = cons.get("claimed_but_not_detected", [])
        if cnd:
            fl.append(Paragraph("Mentioned in the narrative but not detected in any photograph", S["H2"]))
            fl.append(P(esc("; ".join(cnd)) + ". The part may simply not be photographed - request further images "
                        "if relevant.", "body"))
    fl.append(Spacer(1, 3))
    fl.append(P(esc(cons.get("note", "")), "small"))
    return fl


def _estimate_section(pkg, findings):
    est = pkg.get("repair_estimate", {})
    ref_lookup = {(f["image"], f.get("damage_id")): f["ref"] for f in findings}
    fl = _section("5. Repair Estimate")
    fl.append(P("Two figures are shown <b>separately on purpose</b>. The workshop estimate is the figure a "
                "surveyor would normally assess; the AI figure is an unverified indicative value derived from "
                "a generic rate card and must not be treated as a quotation or settlement amount.", "small"))

    fl.append(Paragraph("5A. Workshop estimate (authoritative when entered)", S["H2"]))
    ws = est.get("workshop_items", [])
    if ws:
        rows = [[P(h, "hdr") for h in ("Description", "Qty", "Unit price", "Amount")]]
        for it in ws:
            rows.append([P(esc(it["description"])), P(f"{it['quantity']:g}", "cell_c"),
                         P(inr(it["unit_price"]), "cell_r"), P(inr(it["amount"]), "cell_r")])
        rows.append([P("<b>Workshop total</b>"), "", "", P(f"<b>{inr(est.get('workshop_total', est.get('workshop_additions_total', 0)))}</b>", "cell_r")])
        fl.append(_table(rows, [98 * mm, 20 * mm, 30 * mm, 30 * mm],
                         extra=[("SPAN", (0, len(rows) - 1), (2, len(rows) - 1)),
                                ("BACKGROUND", (0, len(rows) - 1), (-1, len(rows) - 1), PANEL)]))
    else:
        t = Table([[P('<font color="#C62828"><b>No workshop estimate entered.</b></font> Attach the workshop\'s '
                      'itemised estimate (parts, labour, paint) before submission.', "cell")]], colWidths=[CW])
        t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, RED), ("BACKGROUND", (0, 0), (-1, -1), RED_BG),
                               ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 5),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        fl.append(t)

    fl.append(Paragraph("5B. AI indicative estimate (unverified, rate-card based)", S["H2"]))
    items = est.get("ai_preliminary_items", [])
    rows = [[P(h, "hdr") for h in ("Ref", "Part", "Damage", "Severity", "Action", "Basis", "Amount")]]
    for it in items:
        basis = "Unverified" if it.get("review_required") else "Verified"
        refs = ", ".join(it.get("source_refs") or [ref_lookup.get((it["image"], it.get("damage_id")), "-")])
        rows.append([P(esc(refs), "cell_b"), P(esc(it["part"])),
                     P(esc(it["damage_type"])), P(esc(it["severity"])),
                     P(esc(it["recommended_action"]).title()), P(basis), P(inr(it["amount"]), "cell_r")])
    if len(rows) == 1:
        rows.append([P("-")] * 6 + [P(inr(0), "cell_r")])
    rows.append([P("<b>AI indicative subtotal</b>")] + [""] * 5 + [P(f"<b>{inr(est.get('ai_preliminary_total', 0))}</b>", "cell_r")])
    last = len(rows) - 1
    fl.append(_table(rows, [17 * mm, 30 * mm, 26 * mm, 19 * mm, 18 * mm, 28 * mm, 40 * mm],
                     extra=[("SPAN", (0, last), (5, last)), ("BACKGROUND", (0, last), (-1, last), PANEL)]))

    un = list(est.get("unpriced_findings", []))
    priced_refs = {
        ref
        for item in items
        for ref in (item.get("source_refs") or [
            ref_lookup.get((item.get("image"), item.get("damage_id")), "-")
        ])
    }
    known_unpriced_refs = {
        finding.get("ref") or ref_lookup.get((finding.get("image"), finding.get("damage_id")), "-")
        for finding in un
    }
    for finding in findings:
        ref = finding.get("ref", "-")
        if str(finding.get("part") or "").strip().lower() == "unknown" and ref not in priced_refs and ref not in known_unpriced_refs:
            un.append(finding)
            known_unpriced_refs.add(ref)
    if un:
        fl.append(Spacer(1, 4))
        fl.append(P("<b>Findings not priced</b> (need workshop pricing): " + "; ".join(
            f"{u.get('ref') or ref_lookup.get((u.get('image'), u.get('damage_id')), '-')} {esc(u.get('part', 'unknown'))} / {esc(u.get('damage_type', 'unspecified'))}"
            for u in un), "body"))
    fl.append(Spacer(1, 5))
    fl.append(P(f"Rate card: {esc(est.get('rate_card_version', '-'))} (illustrative). Identical part + damage-type "
                "findings seen in several photographs are priced once. Amounts are before GST, parts depreciation "
                "and policy excess/deductible, none of which are applied here. The AI figure is never added to "
                "the workshop figure. The insurer/surveyor makes the final assessment.", "small"))
    return fl


def _documents_section(pkg):
    ds = pkg.get("document_status", {})
    det = ds.get("detected_document_categories", {})
    reviewed = ds.get("review", {})
    fl = _section("6. Supporting Documents")
    rows = [[P(h, "hdr") for h in ("Document", "Status")]]
    for i, (key, lbl) in enumerate(REQUIRED_DOCS, start=1):
        review = reviewed.get(key, {})
        ok = bool(det.get(key))
        status = review.get("status") or ("Filename match; unverified" if ok else "Not provided / not verified")
        color = "#2E7D32" if status.startswith("Verified") else "#B26A00" if status.startswith("Filename match") else "#C62828"
        rows.append([P(lbl), Paragraph(
            f'<font color="{color}"><b>{esc(status)}</b></font>',
            S["cell"])])
    fl.append(_table(rows, [110 * mm, 68 * mm]))
    if reviewed:
        fl.append(Spacer(1, 4))
        fl.append(P("Document review notes", "H2"))
        for key, review in reviewed.items():
            label = dict(REQUIRED_DOCS).get(key, key.replace("_", " ").title())
            note = review.get("note") if isinstance(review, dict) else str(review)
            filename = review.get("file") if isinstance(review, dict) else None
            text = f"<b>{esc(label)}:</b> "
            if filename:
                text += f"{esc(filename)} — "
            text += esc(note or "No reviewer note.")
            fl.append(P(text, "body"))
    fl.append(Spacer(1, 4))
    files = ds.get("files", [])
    fl.append(P("<b>Files in supporting-documents folder:</b> " + (esc("; ".join(files)) if files else
                '<font color="#C62828">none</font>'), "body"))
    fl.append(Spacer(1, 3))
    fl.append(P("Detection is by file name only; content has not been read or validated. Exact document "
                "requirements vary by insurer, policy and claim type - this report does not judge completeness.",
                "small"))
    return fl


def _evidence_register(pkg, original_dir, annotated_dir):
    fl = _section("7. Evidence Register and Integrity")
    rows = [[P(h, "hdr") for h in ("Type", "File", "Size", "SHA-256")]]
    n = 0
    for label, folder in (("Original", original_dir), ("Annotated", annotated_dir)):
        if folder and Path(folder).exists():
            for p in sorted(Path(folder).iterdir()):
                if p.is_file():
                    n += 1
                    rows.append([P(label), P(esc(p.name)), P(f"{p.stat().st_size / 1024:,.0f} KB", "cell_r"),
                                 P(f'<font name="Courier" size="5">{_sha12(p)}</font>')])
    if n == 0:
        fl.append(P("Evidence folders were not supplied to the report generator.", "body"))
        return fl
    fl.append(P("Original photographs are preserved unmodified. The hashes let the insurer confirm that the files "
                "in this ZIP are the files that were assessed.", "small"))
    fl.append(Spacer(1, 4))
    fl.append(_table(rows, [20 * mm, 67 * mm, 18 * mm, 73 * mm]))
    qual = pkg.get("evidence", {}).get("quality", [])
    if qual:
        fl.append(Paragraph("Photograph quality and metadata checks (heuristic, informational)", S["H2"]))
        qr = [[P(h, "hdr") for h in ("Photograph", "Size (px)", "Sharpness", "EXIF time", "GPS", "Flags")]]
        for q in qual:
            flags = ", ".join(q.get("flags", [])) or "none"
            qr.append([P(esc(q["file"])), P(f"{q.get('width', '-')}x{q.get('height', '-')}", "cell_c"),
                       P(f"{q.get('sharpness', '-')}", "cell_c"), P(esc(q.get("exif_datetime") or "absent")),
                       P("yes" if q.get("has_gps") else "no", "cell_c"),
                       Paragraph(f'<font color="{"#B26A00" if q.get("flags") else "#2E7D32"}">{esc(flags)}</font>',
                                 S["cell"])])
        fl.append(_table(qr, [34 * mm, 24 * mm, 20 * mm, 32 * mm, 12 * mm, 56 * mm]))
    return fl


def _image_section(pkg, findings, original_dir, annotated_dir, tmpdir):
    fl = [CondPageBreak(120 * mm)] + _section("8. Annotated Evidence")
    fl.append(P("Left: original photograph. Right: AI-annotated copy for human review. The original is the "
                "evidence of record; annotations are aids only.", "small"))
    imgs = pkg["ai_assessment"]["images"]
    for idx, img in enumerate(imgs, start=1):
        name = img["image"]
        if idx > 1:
            fl.append(CondPageBreak(112 * mm))
        block = [Paragraph(f"Photograph {idx} of {len(imgs)}: {esc(name)}", S["H2"])]
        o = _fit_image(Path(original_dir) / name if original_dir else None, 86 * mm, 66 * mm, tmpdir)
        a = _fit_image(Path(annotated_dir) / f"{Path(name).stem}_annotated.jpg" if annotated_dir else None,
                       86 * mm, 66 * mm, tmpdir)
        missing = P('<font color="#C62828"><i>Image not available</i></font>', "cell_c")
        pair = Table([[o or missing, a or missing],
                      [P("Original", "small"), P("AI-annotated", "small")]], colWidths=[CW / 2, CW / 2])
        pair.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
                                  ("BOX", (0, 0), (0, 0), 0.4, LINE), ("BOX", (1, 0), (1, 0), 0.4, LINE),
                                  ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        block.append(pair)
        mine = [f for f in findings if f["image"] == name]
        if mine:
            rows = [[P(h, "hdr") for h in ("Ref", "Part", "Damage", "Severity", "Conf. (dmg/part)", "Status")]]
            for f in mine:
                st_txt, st_col = _status(f)
                rows.append([P(f["ref"], "cell_b"), P(esc(f["part"])), P(esc(f["damage_type"])),
                             P(esc(f.get("severity") or "Unknown")),
                             P(f"{pct(f.get('damage_confidence'))} / {pct(f.get('part_confidence'))}", "cell_c"),
                             Paragraph(f'<font color="{st_col.hexval().replace("0x", "#")}"><b>{st_txt}</b></font>',
                                       S["cell"])])
            block += [Spacer(1, 4), _table(rows, [12 * mm, 38 * mm, 30 * mm, 24 * mm, 36 * mm, 38 * mm])]
        else:
            block += [Spacer(1, 4), P("No damage detected by the model in this photograph. "
                                      "This does not prove the vehicle is undamaged.", "body")]
        fl.append(KeepTogether(block))
        fl.append(Spacer(1, 8))
    return fl


def _method_section(pkg):
    ai = pkg.get("ai_assessment", {})
    cfg = ai.get("config", {})
    fl = _section("9. Methodology, Traceability and Limitations")
    rows = [[P(h, "hdr") for h in ("Component", "Identifier / setting")],
            [P("Damage detection model"), P(esc(ai.get("damage_model_version", "-")))],
            [P("Vehicle-parts model"), P(esc(ai.get("parts_model_version", "-")))],
            [P("Severity rule"), P(esc(ai.get("severity_version", "-")) +
                                   " - Scratch: Minor; Dent, Crack, Lamp broken: Moderate; Glass shatter, Tire flat: Severe")]]
    if cfg:
        rows += [
            [P("Inference"), P(f"Image size {cfg.get('img_size', '-')}; detection conf. >= {cfg.get('damage_conf', '-')}; "
                               f"parts conf. >= {cfg.get('parts_conf', '-')}; severity conf. >= {cfg.get('severity_conf', '-')}")],
            [P("Review thresholds"), P(f"Part conf. < {cfg.get('part_conf_review', '-')}; damage conf. < "
                                       f"{cfg.get('damage_conf_review', '-')}; overlap < {cfg.get('overlap_review', '-')}; "
                                       f"ambiguity margin {cfg.get('ambiguous_margin', '-')}")],
        ]
    fl.append(_table(rows, [50 * mm, 128 * mm]))
    fl.append(Paragraph("Known limitations", S["H2"]))
    for t in [
        "Severity is a project-defined rule per damage type; it is not learned from severity-labelled data and "
        "does not consider damage size or affected area.",
        "Damage-to-part assignment can be wrong or 'unknown' on angled, partial or low-quality photographs.",
        "The same physical damage photographed from several angles can appear as several findings.",
        "The narrative check uses fixed keyword aliases and does not understand negation or 'only'.",
        "Repair figures come from a generic rate card / workshop input and exclude GST, depreciation and excess.",
        "The AI does not approve, reject, settle or assess fraud on any claim.",
    ]:
        fl.append(Paragraph("&#8226;&nbsp; " + esc(t), S["body"]))
    return fl


def _signoff_section(pkg):
    w = pkg.get("workshop", {})
    fl = [CondPageBreak(95 * mm)] + _section("10. Declaration and Sign-off")
    fl.append(P("Technician decisions shown in Section 3 are recorded in the application and are not a handwritten "
                "signature. Complete the workshop technician and authorised signatory fields before final submission "
                "where required. The insurer/surveyor receipt fields are for use after the package is submitted. "
                "This generated report does not attest that any party has approved or accepted the claim.", "body"))
    fl.append(Spacer(1, 8))
    line = lambda: P("&nbsp;", "cell")
    rows = [[P(h, "hdr") for h in ("Role", "Name", "Signature", "Date")],
            [P("Workshop technician"), val(w.get("technician_name")), line(), line()],
            [P("Workshop authorised signatory"), line(), line(), line()],
            [P("Insurer / surveyor (receipt)"), line(), line(), line()]]
    t = _table(rows, [50 * mm, 46 * mm, 50 * mm, 32 * mm], zebra=False,
               extra=[("TOPPADDING", (0, 1), (-1, -1), 10), ("BOTTOMPADDING", (0, 1), (-1, -1), 10)])
    fl += [t, Spacer(1, 10)]
    box = Table([[P("<b>Important notice.</b> " + esc(pkg.get("disclaimer", "")) +
                    " This report does not constitute an insurance approval, rejection, settlement amount, or "
                    "fraud determination. Final assessment remains with the authorised human reviewer/surveyor.",
                    "small")]], colWidths=[CW])
    box.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, LINE), ("BACKGROUND", (0, 0), (-1, -1), PANEL),
                             ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    fl.append(box)
    return fl


# --------------------------------------------------------------------------------------
# Public entry points
# --------------------------------------------------------------------------------------
_STATUS_CODE = {
    "DRAFT - INCOMPLETE": "DRAFT_INCOMPLETE",
    "PENDING TECHNICIAN VERIFICATION": "PENDING_TECHNICIAN_VERIFICATION",
    "VERIFIED - OPEN ITEMS REMAIN": "VERIFIED_OPEN_ITEMS",
    "VERIFIED - READY FOR INSURER REVIEW": "READY_FOR_INSURER_REVIEW",
}


def compute_submission_status(pkg):
    """-> (status_code, status_text, [open-item messages]). Same logic the PDF cover uses."""
    findings = _flatten(pkg)
    text, _color, issues = _assess_readiness(pkg, findings)
    return _STATUS_CODE[text], text, [m for _lvl, m in issues]


def build_claim_pdf(pkg, out_path, original_dir=None, annotated_dir=None, supporting_dir=None):
    findings = _flatten(pkg)
    status_text, status_color, issues = _assess_readiness(pkg, findings)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    story = []
    story += _cover(pkg, findings, status_text, status_color, issues)
    story += _party_section(pkg)
    story += _findings_section(pkg, findings)
    story += _verification_section(pkg, findings)
    story += _consistency_section(pkg, findings)
    story += _estimate_section(pkg, findings)
    story += _documents_section(pkg)
    story += _evidence_register(pkg, original_dir, annotated_dir)
    story += _image_section(pkg, findings, original_dir, annotated_dir, str(Path(out_path).parent))
    story += _method_section(pkg)
    story += _signoff_section(pkg)

    doc = _Doc(str(out_path), title=f"Claim Package - {pkg.get('claim_id', '')}",
               author=pkg.get("workshop", {}).get("workshop_name", "") or "Claim Package Generator",
               subject="Digital vehicle insurance claim package (AI-assisted, human-reviewed)")
    doc.multiBuild(story, canvasmaker=_canvas_factory({"claim_id": pkg.get("claim_id", "")}))
    return str(out_path)
