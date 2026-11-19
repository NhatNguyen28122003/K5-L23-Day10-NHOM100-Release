#!/usr/bin/env python3
"""Dựng PDF hướng dẫn từ file .md đơn giản (tiếng Việt, font Arial/Consolas của Windows).

    py huong-dan/make_pdf.py huong-dan/pha0.md            -> huong-dan/pha0.pdf

Cú pháp hỗ trợ: # / ## / ###, đoạn văn, "- " gạch đầu dòng, "1. " đánh số,
"> " ô ghi chú, ``` khối lệnh ```, bảng | a | b | (dòng |---| bị bỏ qua),
inline **đậm** và `mã`. Công cụ này cần reportlab; validator thì không.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, ListFlowable, ListItem, Paragraph, Preformatted,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

FONTS = Path("C:/Windows/Fonts")
pdfmetrics.registerFont(TTFont("Arial", str(FONTS / "arial.ttf")))
pdfmetrics.registerFont(TTFont("Arial-Bold", str(FONTS / "arialbd.ttf")))
pdfmetrics.registerFont(TTFont("Arial-Italic", str(FONTS / "ariali.ttf")))
pdfmetrics.registerFont(TTFont("Arial-BoldItalic", str(FONTS / "arialbi.ttf")))
pdfmetrics.registerFont(TTFont("Consolas", str(FONTS / "consola.ttf")))
pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="Arial-Bold", italic="Arial-Italic", boldItalic="Arial-BoldItalic")

INK = colors.HexColor("#1f2933")
ACCENT = colors.HexColor("#0b5cad")
MUTED = colors.HexColor("#52606d")
CODE_BG = colors.HexColor("#f2f4f7")
NOTE_BG = colors.HexColor("#fff7e6")
NOTE_BORDER = colors.HexColor("#f0a020")
GRID = colors.HexColor("#cbd2d9")

S = {
    "h1": ParagraphStyle("h1", fontName="Arial-Bold", fontSize=20, leading=25, textColor=ACCENT, spaceAfter=4),
    "sub": ParagraphStyle("sub", fontName="Arial", fontSize=10, leading=14, textColor=MUTED, spaceAfter=10),
    "h2": ParagraphStyle("h2", fontName="Arial-Bold", fontSize=14, leading=18, textColor=ACCENT, spaceBefore=12, spaceAfter=5),
    "h3": ParagraphStyle("h3", fontName="Arial-Bold", fontSize=11.5, leading=15, textColor=INK, spaceBefore=8, spaceAfter=3),
    "body": ParagraphStyle("body", fontName="Arial", fontSize=10, leading=14.5, textColor=INK, spaceAfter=5, alignment=TA_LEFT),
    "cell": ParagraphStyle("cell", fontName="Arial", fontSize=9, leading=12, textColor=INK),
    "cellh": ParagraphStyle("cellh", fontName="Arial-Bold", fontSize=9, leading=12, textColor=colors.white),
    "code": ParagraphStyle("code", fontName="Consolas", fontSize=8.6, leading=11.5, textColor=INK),
    "note": ParagraphStyle("note", fontName="Arial", fontSize=9.6, leading=13.5, textColor=INK),
}


def inline(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"`([^`]+)`", r'<font name="Consolas" color="#9c2a00">\1</font>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    return text


def code_block(lines: list[str]) -> Table:
    longest = max((len(x) for x in lines), default=1)
    size = min(8.6, (170 * mm - 16) / (longest * 0.55))  # Consolas rộng ~0,55 em/ký tự: dòng dài thì thu nhỏ chữ
    style = ParagraphStyle("codefit", parent=S["code"], fontSize=size, leading=size * 1.34)
    pre = Preformatted("\n".join(lines), style)
    t = Table([[pre]], colWidths=[170 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), CODE_BG), ("BOX", (0, 0), (-1, -1), 0.5, GRID),
                           ("LEFTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 5),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return t


def note_block(lines: list[str]) -> Table:
    t = Table([[Paragraph("<br/>".join(inline(x) for x in lines), S["note"])]], colWidths=[170 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NOTE_BG), ("LINEBEFORE", (0, 0), (0, -1), 3, NOTE_BORDER),
                           ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return t


def table_block(rows: list[list[str]]) -> Table:
    ncol = len(rows[0])
    data = [[Paragraph(inline(c), S["cellh" if r == 0 else "cell"]) for c in row + [""] * (ncol - len(row))] for r, row in enumerate(rows)]
    # độ rộng cột theo độ dài chữ, tối thiểu 12%
    lens = [max(len(row[i]) if i < len(row) else 0 for row in rows) for i in range(ncol)]
    total = sum(max(n, 6) for n in lens)
    widths = [170 * mm * max(max(n, 6) / total, 0.12) for n in lens]
    scale = 170 * mm / sum(widths)
    t = Table(data, colWidths=[w * scale for w in widths], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), ACCENT), ("GRID", (0, 0), (-1, -1), 0.4, GRID),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CODE_BG]),
                           ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]))
    return t


def parse(md: str) -> list:
    story: list = []
    lines = md.splitlines()
    i = 0
    para: list[str] = []

    def flush():
        if para:
            story.append(Paragraph(inline(" ".join(para)), S["body"]))
            para.clear()

    first_h1 = True
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s.startswith("```"):
            flush()
            block = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            story.append(code_block(block))
            story.append(Spacer(1, 6))
        elif s.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            story.append(table_block(rows))
            story.append(Spacer(1, 8))
            continue
        elif s.startswith(">"):
            flush()
            block = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                block.append(lines[i].strip()[1:].strip())
                i += 1
            story.append(note_block(block))
            story.append(Spacer(1, 8))
            continue
        elif s.startswith("- ") or re.match(r"\d+\. ", s):
            flush()
            numbered = bool(re.match(r"\d+\. ", s))
            items = []
            while i < len(lines):
                t = lines[i].strip()
                if numbered and re.match(r"\d+\. ", t):
                    items.append(re.sub(r"^\d+\. ", "", t))
                elif not numbered and t.startswith("- "):
                    items.append(t[2:])
                elif t and lines[i].startswith("  ") and items:
                    items[-1] += " " + t
                else:
                    break
                i += 1
            lf = ListFlowable([ListItem(Paragraph(inline(x), S["body"]), leftIndent=14) for x in items],
                              bulletType="1" if numbered else "bullet", start="1" if numbered else None,
                              bulletFontName="Arial", bulletFontSize=9, leftIndent=14)
            story.append(lf)
            continue
        elif s.startswith("### "):
            flush(); story.append(Paragraph(inline(s[4:]), S["h3"]))
        elif s.startswith("## "):
            flush(); story.append(Paragraph(inline(s[3:]), S["h2"]))
        elif s.startswith("# "):
            flush(); story.append(Paragraph(inline(s[2:]), S["h1"]))
            if first_h1 and i + 1 < len(lines) and lines[i + 1].startswith("_"):
                story.append(Paragraph(inline(lines[i + 1].strip("_ ")), S["sub"]))
                i += 1
            first_h1 = False
        elif not s:
            flush()
        else:
            para.append(s)
        i += 1
    flush()
    return story


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Arial", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(20 * mm, 10 * mm, doc.title)
    canvas.drawRightString(190 * mm, 10 * mm, f"Trang {doc.page}")
    canvas.restoreState()


def build(src: Path) -> Path:
    md = src.read_text(encoding="utf-8")
    title = next((l[2:].strip() for l in md.splitlines() if l.startswith("# ")), src.stem)
    out = src.with_suffix(".pdf")
    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm, title=title, author="Nhóm 03 (An Hai)")
    doc.build(parse(md), onFirstPage=footer, onLaterPages=footer)
    return out


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        print("->", build(Path(arg)))
