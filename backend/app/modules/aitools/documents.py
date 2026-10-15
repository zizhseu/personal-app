"""简历文本提取；文件仅在内存中处理，提取结果由用户核对后保存。"""
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from fastapi import HTTPException
from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_RESUME_CHARS = 30000


def extract_resume(filename: str, data: bytes) -> dict:
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "简历文件不能超过 5 MB")
    suffix = Path(filename).suffix.lower()
    try:
        if suffix in (".txt", ".md", ".markdown"):
            try:
                content = data.decode("utf-8-sig")
            except UnicodeDecodeError:
                content = data.decode("gb18030")
        elif suffix == ".pdf":
            reader = PdfReader(BytesIO(data))
            if reader.is_encrypted:
                raise HTTPException(422, "请先解除 PDF 的密码保护，或直接粘贴简历文本")
            if len(reader.pages) > 20:
                raise HTTPException(422, "简历 PDF 最多支持 20 页")
            content = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        elif suffix == ".docx":
            # 按文档中的段落顺序读取正文，包含表格中的文字。
            with ZipFile(BytesIO(data)) as archive:
                if sum(item.file_size for item in archive.infolist()) > 20 * 1024 * 1024:
                    raise HTTPException(413, "Word 文档解压后的内容过大")
                root = ElementTree.fromstring(archive.read("word/document.xml"))
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            content = "\n".join(
                "".join(node.text or "" for node in paragraph.findall(".//w:t", ns))
                for paragraph in root.findall(".//w:p", ns)
            )
        else:
            raise HTTPException(422, "支持 PDF、DOCX、TXT 和 Markdown 格式；其他格式可复制文本后粘贴")
    except (UnicodeError, PdfReadError, BadZipFile, ElementTree.ParseError, KeyError, ValueError, OSError) as exc:
        raise HTTPException(422, "无法读取该文件，请检查格式，或直接粘贴简历文本") from exc
    content = content.replace("\x00", "").strip()
    if not content:
        raise HTTPException(422, "未提取到文字；扫描图片版简历请先转为文字，或直接粘贴文本")
    if len(content) > MAX_RESUME_CHARS:
        raise HTTPException(422, "简历文本不能超过 30000 字，请精简后再导入")
    return {"name": Path(filename).stem[:100] or "导入的简历", "content": content}
