"""JSON の仕様から、4分割の学習ノート（A4横の .pptx）を作る。

使い方: python -m app.builders.quad spec.json out.pptx

レイアウト（A4横）:
  左上 = 図解                 右上 = キーコンセプト（赤字）
  左下 = 用語・発音のコツ      右下 = 具体例・たとえ話

文字列の中の **文字** は強調（太字。発音の欄では太字＋下線＝強く読む所）。
各項目の書き方は app/assets/quad_example.json を参照。
"""
import json, re, sys
from pptx import Presentation
from pptx.util import Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn

FONT = "Meiryo UI"
C = {  # 色（明るいテーマ）
    "navy": "1D3557", "ink": "1D2B3A", "text": "111111", "muted": "6B7C8F", "foot": "8A96A3",
    "frame": "A9B6C3", "red": "D1145A", "red_b": "B0002A", "ex_label": "B0124F",
    "term": "1450C8", "pron": "2F6B5A", "pron_b": "0B3D30", "warn": "9A5300",
    "cover_bg": "1D3557", "cover_kicker": "9AD1C7", "cover_sub": "CADCFC",
}
BOX = {  # 図解の箱のスタイル: (塗り, 枠, 文字)
    "navy": ("1D3557", "1D3557", "FFFFFF"), "blue": ("EEF5F8", "CFE0E8", "1D2B3A"),
    "orange": ("FFF3E0", "F7C58A", "1D2B3A"), "gray": ("F3F4F6", "D9DDE3", "1D2B3A"),
    "pink": ("FDE8EF", "F2A7C0", "B0124F"), "teal": ("E3F4F1", "9FD3C8", "1E7F6E"),
    "white": ("FFFFFF", "D9DDE3", "1D2B3A"),
}
# ダークテーマ（既定。仕様で "theme": "light" にすると明るい色のまま）
DARK_C = {
    "bg": "0F1B2D", "navy": "8FB8FF", "ink": "E6EDF5", "text": "E6EDF5", "muted": "9AA8B8", "foot": "7D8B9B",
    "frame": "3A4B60", "red": "FF6B8A", "red_b": "FF9DB2", "ex_label": "FF7FA6",
    "term": "6FB1FF", "pron": "7FD1B9", "pron_b": "B4F2E0", "warn": "FFB454",
    "cover_bg": "0B1424",
}
DARK_BOX = {
    "navy": ("2B5BA8", "2B5BA8", "FFFFFF"), "blue": ("1B2E45", "34506F", "E6EDF5"),
    "orange": ("3A2A14", "8A6230", "FFE2B8"), "gray": ("1E2733", "3A4757", "E6EDF5"),
    "pink": ("3D1726", "8C3A5A", "FF9BBC"), "teal": ("12332E", "2F7A6C", "9DE6D6"),
    "white": ("243042", "3A4757", "E6EDF5"),
}
DARK_TEXT = {"1D2B3A": "E6EDF5", "111111": "E6EDF5", "1D3557": "8FB8FF", "000000": "E6EDF5"}
rgb = lambda h: RGBColor.from_string(h)

# 各区画の位置（ポイント単位）
SLIDE_W, SLIDE_H = 841.7, 595.4
DIAG = (31.0, 74.9, 419.0, 225.4)
CONC = (461.5, 74.9, 349.2, 225.4)
TERMS = [(31.0, 323.3, 240.8, 247.0), (282.6, 323.3, 240.8, 247.0)]
EXAM = (535.0, 323.3, 275.8, 247.0)


def runs(s):
    """'a **b** c' -> [('a',False),('b',True),(' c',False)]。文字としての * は \\* と書く"""
    out, bold = [], False
    for part in re.split(r"(\*\*)", s.replace("\\*", "\ue000")):
        if part == "**":
            bold = not bold
        elif part:
            out.append((part.replace("\ue000", "*"), bold))
    return out


def width_units(s):
    s = s.replace("\\*", "*").replace("**", "")
    return sum(0.55 if ord(ch) < 0x2E80 else 1.0 for ch in s)


def est_lines(s, size, box_w):
    per_line = box_w / size  # 1行に入る全角文字数
    return sum(max(1, -(-int(width_units(p) * 1.04) // max(1, int(per_line)))) for p in s.split("\n"))


def tb(slide, x, y, w, h, name=None):
    shp = slide.shapes.add_textbox(Pt(x), Pt(y), Pt(w), Pt(h))
    tf = shp.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    if name:
        shp.name = name
    return shp, tf


def add_run(p, text, size, color, bold=False, underline=False):
    r = p.add_run()
    r.text = text
    f = r.font
    f.name = FONT
    f.size = Pt(size)
    f.bold = bold
    f.underline = underline
    f.color.rgb = rgb(color)
    # 日本語の文字にも同じフォントを使う
    rpr = r._r.get_or_add_rPr()
    for tag in ("a:ea", "a:cs"):
        el = rpr.find(qn(tag))
        if el is None:
            el = rpr.makeelement(qn(tag), {})
            rpr.append(el)
        el.set("typeface", FONT)
    return r


def para(tf, first):
    return tf.paragraphs[0] if first else tf.add_paragraph()


def line(slide, x1, y1, x2, y2, color, w=1.0):
    ln = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Pt(x1), Pt(y1), Pt(x2), Pt(y2))
    ln.line.color.rgb = rgb(color)
    ln.line.width = Pt(w)
    return ln


def label(slide, x, y, w, text, size=7.5, color=C["muted"], spaced=True):
    _, tf = tb(slide, x, y, w, 14.4)
    r = add_run(tf.paragraphs[0], text, size, color, bold=spaced)
    if spaced:
        r._r.get_or_add_rPr().set("spc", "100")  # 区画の見出しは字間を少し空ける


# ---------------------------------------------------------------- 表紙
def cover(prs, spec):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bg = s.background.fill
    bg.solid(); bg.fore_color.rgb = rgb(C["cover_bg"])
    cv = spec.get("cover", {})
    _, tf = tb(s, 43.2, 39.6, 756, 43.2); add_run(tf.paragraphs[0], cv.get("kicker", spec.get("course", "")), 20, C["cover_kicker"], True)
    _, tf = tb(s, 43.2, 79.2, 756, 57.6); add_run(tf.paragraphs[0], cv.get("title", "学習ノート"), 34, "FFFFFF", True)
    _, tf = tb(s, 43.2, 136.8, 756, 36)
    add_run(tf.paragraphs[0], cv.get("subtitle", "左上＝図解／右上＝キーコンセプト／左下＝用語・発音のコツ／右下＝具体例"), 11, C["cover_sub"])
    topics = [f'{i + 1:02d}  {(n.get("title") or n.get("title_ja", ""))}' for i, n in enumerate(spec["notes"])]
    per = max(10, -(-len(topics) // 3))
    for col in range(3):
        chunk = topics[col * per:(col + 1) * per]
        if not chunk:
            continue
        _, tf = tb(s, 43.2 + col * 259.2, 198, 248.4, 360)
        for i, t in enumerate(chunk):
            p = para(tf, i == 0); p.space_after = Pt(4)
            add_run(p, t, 12, "FFFFFF")


# ---------------------------------------------------------------- 図解（PowerPoint の図形で描く）
def diagram(s, d):
    x0, y0, w0, h0 = DIAG
    top = y0 + 4
    if d.get("title"):
        _, tf = tb(s, x0 + 20, top, w0 - 20, 22)
        p = tf.paragraphs[0]
        add_run(p, d["title"], 13, C["navy"], True)
        if d.get("subtitle"):
            add_run(p, "  " + d["subtitle"], 8, C["muted"])
        top += 26
    # グリッド: 残りの領域を 24列 x 12行 に分ける
    gx, gy, gw, gh = x0 + 20, top, w0 - 28, (y0 + h0) - top - 6
    cw, rh = gw / 24, gh / 12
    pos = lambda c, r: (gx + c * cw, gy + r * rh)
    # 矢印を先に描き、箱が矢印の上に重なるようにする
    for a in d.get("arrows", []):
        (c1, r1), (c2, r2) = a["from"], a["to"]
        x1, y1 = pos(c1, r1); x2, y2 = pos(c2, r2)
        cn = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Pt(x1), Pt(y1), Pt(x2), Pt(y2))
        cn.line.color.rgb = rgb(a.get("color", "2A9D8F")); cn.line.width = Pt(a.get("width", 2))
        ln = cn.line._get_or_add_ln()
        tail = ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
        ln.append(tail)
    for b in d.get("boxes", []):
        fill, border, txt = BOX.get(b.get("style", "blue"), BOX["blue"])
        x, y = pos(b["c"], b["r"])
        w, h = b["w"] * cw - 3, b["h"] * rh - 3
        shp = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Pt(x), Pt(y), Pt(w), Pt(h))
        shp.adjustments[0] = min(0.5, 4 / max(1, min(w, h)))
        shp.fill.solid(); shp.fill.fore_color.rgb = rgb(fill)
        shp.line.color.rgb = rgb(border); shp.line.width = Pt(1)
        shp.shadow.inherit = False
        tf = shp.text_frame
        tf.word_wrap = True
        for m in ("margin_left", "margin_right"): setattr(tf, m, Pt(4))
        tf.margin_top = tf.margin_bottom = Pt(2)
        tf.vertical_anchor = MSO_ANCHOR.TOP if b.get("align_top") else MSO_ANCHOR.MIDDLE
        al = PP_ALIGN.LEFT if b.get("left") else PP_ALIGN.CENTER
        lines = b["text"].split("\n")
        for i, t in enumerate(lines):
            p = para(tf, i == 0); p.alignment = al
            main = i == 0 or b.get("same_lines")  # same_lines: すべての行を1行目と同じ書式にする
            size = b.get("size", 8.5) if main else b.get("sub_size", 7)
            col = txt if main else (C["muted"] if b.get("style") != "navy" else "CADCFC")
            for t_, bold in runs(t):
                add_run(p, t_, size, col, bold or (main and b.get("bold", True)))
    for t in d.get("labels", []):
        x, y = pos(t["c"], t["r"])
        _, tf = tb(s, x, y, t.get("w", 6) * cw, t.get("h", 1) * rh)
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER if t.get("center") else PP_ALIGN.LEFT
        for t_, bold in runs(t["text"]):
            col = t.get("color", C["ink"])
            add_run(p, t_, t.get("size", 8), DARK_TEXT.get(col, col) if "bg" in C else col, bold)


# ---------------------------------------------------------------- 各区画
def fit(items_text, sizes, box):
    """区画に収まる一番大きい文字サイズを選ぶ"""
    for size in sizes:
        lines = sum(est_lines(t, size, box[2]) for t in items_text)
        if lines * size * 1.32 + len(items_text) * 5 <= box[3]:
            return size
    return sizes[-1]


def concepts(s, items):
    size = fit(items, [13.5, 12.5, 11.5, 10.5], CONC)
    _, tf = tb(s, *CONC, name="concepts")
    for i, t in enumerate(items):
        p = para(tf, i == 0); p.space_after = Pt(5)
        add_run(p, "★ ", size * 0.8, C["red"])
        for t_, bold in runs(t):
            add_run(p, t_, size, C["red_b"] if bold else C["red"], bold)


def term_height(t, size, w):
    h = est_lines(f'{t["term"]}：{t["def"]}', size, w) * size * 1.3 + 4
    if t.get("pron"):
        h += est_lines("　発音 " + t["pron"] + "  " + t.get("tip", ""), size * 0.86, w) * size * 1.15
    if t.get("warn"):
        h += est_lines("　注意 " + t["warn"], size * 0.86, w) * size * 1.15
    return h


def terms(s, items):
    size = 10.5
    for size in (10.5, 10, 9.5, 9):
        hs = [term_height(t, size, TERMS[0][2]) for t in items]
        # 順番を保ったまま、高さが同じくらいの2列に分ける
        total, acc, cut = sum(hs), 0, len(items)
        for i, h in enumerate(hs):
            if acc + h / 2 > total / 2:
                cut = i if acc >= total / 2 - h / 2 else i + 1
                break
            acc += h
        cols = [items[:cut], items[cut:]]
        if max(sum(hs[:cut]), sum(hs[cut:])) <= TERMS[0][3]:
            break
    for ci, col in enumerate(cols):
        _, tf = tb(s, *TERMS[ci], name=f"terms{ci}")
        first = True
        for t in col:
            p = para(tf, first); first = False
            p.space_before = Pt(4)
            add_run(p, t["term"], size, C["term"], True)
            add_run(p, "：", size, C["term"])
            if t.get("tag"):  # 例: 英単語 / Idiom
                add_run(p, f' [{t["tag"]}] ', size * 0.76, C["term"])
            for t_, bold in runs(t["def"]):
                add_run(p, t_, size, C["text"], bold)
            if t.get("pron"):
                p = tf.add_paragraph()
                add_run(p, "　発音 ", size * 0.81, C["pron"], True)
                for t_, bold in runs(t["pron"]):
                    add_run(p, t_, size * 0.86, C["pron_b"] if bold else C["pron"], bold, underline=bold)
                if t.get("tip"):
                    add_run(p, "　" + t["tip"], size * 0.86, C["pron"])
            if t.get("warn"):
                p = tf.add_paragraph()
                add_run(p, "　注意 ", size * 0.81, C["warn"], True)
                add_run(p, t["warn"], size * 0.86, C["warn"])


def examples(s, items):
    texts = [f'【{e["label"]}】{e["text"]}' for e in items]
    size = fit(texts, [13, 12, 11, 10.5], EXAM)
    _, tf = tb(s, *EXAM, name="examples")
    for i, e in enumerate(items):
        p = para(tf, i == 0); p.space_before = Pt(0 if i == 0 else 7)
        add_run(p, f'【{e["label"]}】', size * 0.85, C["ex_label"], True)
        for t_, bold in runs(e["text"]):
            add_run(p, t_, size, C["navy"] if bold else C["ink"], bold)


def note(prs, spec, n, idx, page):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    if "bg" in C:
        s.background.fill.solid(); s.background.fill.fore_color.rgb = rgb(C["bg"])
    # 枠線
    fx, fy, fw, fh = 25.2, 57.6, 791.3, 518.4
    for x1, y1, x2, y2 in [(fx, fy, fx + fw, fy), (fx, fy + fh, fx + fw, fy + fh), (fx, fy, fx, fy + fh),
                           (fx + fw, fy, fx + fw, fy + fh), (fx, 306.0, fx + fw, 306.0),
                           (455.8, fy, 455.8, 306.0), (529.2, 306.0, 529.2, fy + fh)]:
        line(s, x1, y1, x2, y2, C["frame"])
    label(s, 31.0, 59.8, 419, "DIAGRAM ・ 図解")
    label(s, 461.5, 59.8, 349, "KEY CONCEPTS ・ キーコンセプト")
    label(s, 31.0, 308.2, 492, "TECHNICAL TERMS ・ 用語と発音のコツ（太字＋下線＝強く読む）")
    label(s, 535.0, 308.2, 276, "EXAMPLES ・ 具体例とたとえ話")
    label(s, 25.2, 577.4, 432, spec.get("footer", spec.get("course", "")), 7, C["foot"], spaced=False)
    _, tf = tb(s, 748.8, 577.4, 67.7, 14.4); tf.paragraphs[0].alignment = PP_ALIGN.RIGHT
    add_run(tf.paragraphs[0], str(page), 7, C["foot"])
    # タイトル
    _, tf = tb(s, 25.2, 15.8, 791.3, 36, name="Title"); tf.vertical_anchor = MSO_ANCHOR.BOTTOM
    p = tf.paragraphs[0]
    add_run(p, f'{n.get("num", idx)}. {(n.get("title") or n.get("title_ja", ""))}', 20, C["navy"], True)
    if n.get("title_en"):
        add_run(p, "   " + n["title_en"], 11, C["muted"])
    diagram(s, n.get("diagram", {}))
    concepts(s, n.get("concepts", []))
    terms(s, n.get("terms", []))
    examples(s, n.get("examples", []))


def main(spec_path, out):
    build(json.load(open(spec_path, encoding="utf-8")), out)


def build(spec, out):
    if spec.get("theme", "dark") != "light":
        C.update(DARK_C); BOX.update(DARK_BOX)
    prs = Presentation()
    prs.slide_width, prs.slide_height = Pt(SLIDE_W), Pt(SLIDE_H)
    page = 1
    if spec.get("cover", True) is not False and len(spec["notes"]) > 1:
        cover(prs, spec); page += 1
    for i, n in enumerate(spec["notes"], 1):
        note(prs, spec, n, i, page); page += 1
    prs.core_properties.title = spec.get("cover", {}).get("title", spec.get("course", "学習ノート")) if isinstance(spec.get("cover"), dict) else spec.get("course", "学習ノート")
    prs.save(out)
    print("保存しました:", out, "ページ数:", len(prs.slides))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
