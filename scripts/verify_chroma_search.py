import sys
import os

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
from agent.rag.retriever import SopRetriever


def main():
    vs = VectorStore()
    print(f"Collection count: {vs.collection.count()}")

    retriever = SopRetriever(vs)

    test_cases = [
        ("设备冒烟", None, "设备过热/冒烟紧急处置"),
        ("频繁重启", None, "设备频繁重启排查指引"),
        ("缺少螺丝包", None, "配件缺失补发流程"),
        ("软件崩溃", None, "软件崩溃恢复操作"),
        ("漏电", None, "漏电紧急处置SOP"),
        ("批量缺陷", None, "疑似批次缺陷上报流程"),
        ("冒烟", "High_Priority", "设备过热/冒烟紧急处置"),
        ("缺件", "Low_Priority", "配件缺失补发流程"),
    ]

    passed = 0
    failed = 0
    for query, urgency, expected_title in test_cases:
        result = retriever.get_best_sop(query, urgency_level=urgency)
        if result:
            actual_title = result.get("metadata", {}).get("title", "")
            if expected_title in actual_title:
                print(f"  PASS: query='{query}' urgency={urgency} -> {actual_title}")
                passed += 1
            else:
                print(f"  FAIL: query='{query}' urgency={urgency} -> expected '{expected_title}', got '{actual_title}'")
                failed += 1
        else:
            print(f"  FAIL: query='{query}' urgency={urgency} -> no result")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed, {passed + failed} total")


if __name__ == "__main__":
    main()
