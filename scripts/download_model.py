import os
import sys

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import huggingface_hub.file_download

_orig_create_symlink = huggingface_hub.file_download._create_symlink

def _patched_create_symlink(src, dst, new_blob=False):
    try:
        _orig_create_symlink(src, dst, new_blob=new_blob)
    except OSError:
        if not os.path.exists(dst):
            import shutil
            shutil.copy2(src, dst)

huggingface_hub.file_download._create_symlink = _patched_create_symlink

from sentence_transformers import SentenceTransformer

print("正在下载text2vec-base-chinese...")
model = SentenceTransformer("shibing624/text2vec-base-chinese")
print("模型下载成功!")

test_embedding = model.encode(["测试文本"])
print(f"Embedding dimension: {test_embedding.shape[1]}")
print("Ready for ChromaDB indexing!")
