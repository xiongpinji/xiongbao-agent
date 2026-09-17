"""
Stage 1 batch conversion runner — converts all 246 WorkBuddy experts
and writes them into the Octop v1.0.0 expert library.

NOTE: This is a one-shot data migration. In production it would live
under octop/contrib/workbuddy/cli.py as `octop-wb-convert`. For now it
lives here so it's easy to invoke directly.
"""
import json
import sys
import time
from pathlib import Path

PROJECT = Path(r"D:\AI编程库\项目库\进行中的项目\xiongbao agent")
sys.path.insert(0, str(PROJECT))

from octop.contrib.workbuddy import WorkBuddyConverter  # noqa


def main():
    vendor = PROJECT / "vendor"
    out = PROJECT / "octop" / "src" / "octop" / "infra" / "agents" / "experts" / "library"
    print(f"vendor : {vendor}")
    print(f"output : {out}")

    cvt = WorkBuddyConverter(
        vendor_root=vendor,
        octop_root=out,
        skip_missing=True,
    )

    t0 = time.time()
    report = cvt.batch_convert()
    dt = time.time() - t0

    print(report.summary())
    print(f"elapsed: {dt:.2f}s")
    print()

    # By kind breakdown
    by_kind = {"agent": 0, "team": 0, "plugin": 0, "unknown": 0}
    for r in report.results:
        by_kind[r.kind] = by_kind.get(r.kind, 0) + 1
    print("by_kind:", by_kind)

    # Sample outputs
    samples = [r for r in report.results if r.success and r.dst_path and r.dst_path.exists()][:3]
    for r in samples:
        print(f"\n--- {r.expert_id} [{r.kind}] ---")
        manifest_path = r.dst_path / "manifest.json"
        if manifest_path.exists():
            m = json.loads(manifest_path.read_text(encoding="utf-8"))
            print(f"  label: {m['label']}")
            print(f"  quick_prompts: {len(m.get('quick_prompts', []))} prompts")
            print(f"  prompt_files: {m.get('prompt_files', [])}")

    print(f"\nFirst 10 skipped (no source prompt file):")
    skips = [r for r in report.results if r.skipped][:10]
    for r in skips:
        print(f"  {r.expert_id} [{r.kind}] src={r.src_path}")


if __name__ == "__main__":
    main()
