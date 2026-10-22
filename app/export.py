"""PowerPoint（入っている場合）で PDF に書き出す。PowerPoint が無いときは何もせずに飛ばす。"""
import os, shutil, tempfile


def to_pdf(pptx_path, log=print):
    try:
        import comtypes.client
    except ImportError:
        log("PDF を作りませんでした（comtypes が入っていません）")
        return None
    # PowerPoint は長いパスで失敗するので、短い一時フォルダで作業する
    tmp = tempfile.mkdtemp(prefix="sn_")
    src = os.path.join(tmp, "deck.pptx")
    shutil.copy(pptx_path, src)
    pdf_tmp = os.path.join(tmp, "deck.pdf")
    app = None
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except ImportError:
        pass
    try:
        app = comtypes.client.CreateObject("PowerPoint.Application")
        pres = app.Presentations.Open(src, True, False, False)
        pres.SaveAs(pdf_tmp, 32)
        pres.Close()
        out = os.path.splitext(pptx_path)[0] + ".pdf"
        shutil.copy(pdf_tmp, out)
        return out
    except Exception as e:
        log(f"PDF を作りませんでした（PowerPoint を使えません: {e}）")
        return None
    finally:
        if app is not None:
            try:
                app.Quit()
            except Exception:
                pass
        shutil.rmtree(tmp, ignore_errors=True)
