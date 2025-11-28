#!/usr/bin/env python3
"""Audit documentation cross-links to ensure all sections are updated."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Set

# Key documents to check
DOCS = {
    "constitution": Path("docs/Constitution.txt"),
    "plan": Path("specs/001-document-llm-ops/plan.md"),
    "spec": Path("specs/001-document-llm-ops/spec.md"),
    "quickstart": Path("specs/001-document-llm-ops/quickstart.md"),
    "research": Path("specs/001-document-llm-ops/research.md"),
    "tasks": Path("specs/001-document-llm-ops/tasks.md"),
}

# Expected cross-references
EXPECTED_REFS = {
    "constitution": ["plan", "spec", "quickstart"],
    "plan": ["constitution", "spec", "quickstart", "research"],
    "spec": ["constitution", "plan"],
    "quickstart": ["constitution", "plan", "research"],
    "research": ["plan", "quickstart"],
    "tasks": ["plan", "spec"],
}

# Key terms that should be cross-referenced
KEY_TERMS = [
    "SDD",
    "Constitution",
    "quickstart",
    "research",
    "plan.md",
    "spec.md",
    "tasks.md",
    "001-document-llm-ops",
]


def find_references(content: str, doc_name: str) -> Set[str]:
    """Find references to other documents in content."""
    found = set()
    content_lower = content.lower()
    
    for term in KEY_TERMS:
        if term.lower() in content_lower:
            # Try to identify which document is referenced
            for ref_doc, path in DOCS.items():
                if ref_doc != doc_name and (ref_doc in content_lower or path.name.lower() in content_lower):
                    found.add(ref_doc)
    
    # Check for explicit file references
    for ref_doc, path in DOCS.items():
        if ref_doc != doc_name:
            if path.name in content or str(path) in content:
                found.add(ref_doc)
    
    return found


def audit_documentation() -> Dict[str, Dict]:
    """Audit all documentation files for cross-references."""
    results = {}
    
    for doc_name, doc_path in DOCS.items():
        if not doc_path.exists():
            results[doc_name] = {
                "status": "missing",
                "expected_refs": EXPECTED_REFS.get(doc_name, []),
                "found_refs": [],
            }
            continue
        
        content = doc_path.read_text(encoding="utf-8")
        found_refs = find_references(content, doc_name)
        expected_refs = EXPECTED_REFS.get(doc_name, [])
        
        missing_refs = set(expected_refs) - found_refs
        unexpected_refs = found_refs - set(expected_refs)
        
        results[doc_name] = {
            "status": "ok" if not missing_refs else "incomplete",
            "path": str(doc_path),
            "expected_refs": expected_refs,
            "found_refs": list(found_refs),
            "missing_refs": list(missing_refs),
            "unexpected_refs": list(unexpected_refs),
        }
    
    return results


def print_report(results: Dict[str, Dict]) -> None:
    """Print audit report."""
    print("=" * 80)
    print("Documentation Cross-Link Audit Report")
    print("=" * 80)
    print()
    
    all_ok = True
    for doc_name, result in results.items():
        status = result["status"]
        if status == "missing":
            print(f"❌ {doc_name.upper()}: File not found")
            print(f"   Expected at: {result.get('expected_refs', [])}")
            all_ok = False
        elif status == "incomplete":
            print(f"⚠️  {doc_name.upper()}: Missing references")
            print(f"   Path: {result['path']}")
            if result["missing_refs"]:
                print(f"   Missing: {', '.join(result['missing_refs'])}")
            if result["found_refs"]:
                print(f"   Found: {', '.join(result['found_refs'])}")
            all_ok = False
        else:
            print(f"✅ {doc_name.upper()}: All references present")
            if result["found_refs"]:
                print(f"   References: {', '.join(result['found_refs'])}")
    
    print()
    print("=" * 80)
    if all_ok:
        print("✅ All documentation cross-links are in place.")
    else:
        print("⚠️  Some documentation cross-links are missing. Please update.")
    print("=" * 80)


if __name__ == "__main__":
    results = audit_documentation()
    print_report(results)
    
    # Exit with error code if issues found
    if any(r["status"] != "ok" for r in results.values()):
        exit(1)

