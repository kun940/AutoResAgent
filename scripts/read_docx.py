"""临时脚本：读取申报书.docx 的文本内容"""
import zipfile
import re
from xml.etree import ElementTree as ET

docx_path = r"d:\客诉自动回复出单智能体\docs\reference\申报书.docx"

WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def get_docx_text(path: str) -> str:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    tree = ET.fromstring(xml)
    lines = []
    for para in tree.iter(f"{WORD_NS}p"):
        texts = []
        for t in para.iter(f"{WORD_NS}t"):
            if t.text:
                texts.append(t.text)
        line = "".join(texts)
        lines.append(line)
    return "\n".join(lines)


if __name__ == "__main__":
    text = get_docx_text(docx_path)
    print("=" * 80)
    print("申报书原文内容：")
    print("=" * 80)
    print(text)
    print("=" * 80)
    print(f"总字符数: {len(text)}")
