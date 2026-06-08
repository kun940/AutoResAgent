import asyncio
import sys
import os
import time

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"

import huggingface_hub.file_download
_orig = huggingface_hub.file_download._create_symlink
def _patch(src, dst, new_blob=False):
    try:
        _orig(src, dst, new_blob=new_blob)
    except OSError:
        if not os.path.exists(dst):
            import shutil
            shutil.copy2(src, dst)
huggingface_hub.file_download._create_symlink = _patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.rag.vector_store import VectorStore
from agent.rag.sop_indexer import SopIndexer


async def main():
    start = time.time()

    vs = VectorStore()
    print(f"Current collection count: {vs.collection.count()}")

    if vs.collection.count() > 0:
        print("Collection not empty, rebuilding...")
        vs.rebuild_collection()

    indexer = SopIndexer(vs)
    count = await indexer.build_index_from_db()
    elapsed = time.time() - start

    print(f"Indexed {count} SOPs")
    print(f"Final collection count: {vs.collection.count()}")
    print(f"Build time: {elapsed:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
