#!/usr/bin/env python3
"""Canonical PDF pre-flight 3-tier quality check — from book-extraction references/ocr-scanned-pdfs.md.

Usage: python3 pdf_preflight.py /tmp/mega_books/
"""
import pymupdf, re, os, sys

LONG_S_WORDS = {
    'fafe','fmall','firft','fuch','fhort','fome','fhip','fmoke','fpark',
    'fleep','fwell','fword','fame','fide','fince','fo','fpirit','frong',
    'frange','fabrick','faid','fail','faith','falt','favages','fubject',
    'fubftance','fuperior','finall','fingle','fir','firname','fituation',
    'fubmitted','fufficient','fuppofed','fatisfied','fcience','fecond',
    'feveral','fhould','fimple','fmaller','fon','fpeak','fpecies','fpeech',
    'fpend','fquare','ftand','ftate','ftill','ftone','ftrong','ftudy',
    'fuccefs','fuffer','fupply','fupport','fyftem','fignifie','fignifies',
    'fudden','fum','fun','fupper','fure','furprize','furround',
}


def quality_score_pdf(path):
    """Score OCR quality 0-100. Samples 16 pages across the book."""
    doc = pymupdf.open(path)
    pages = doc.page_count
    step = max(1, pages // 16)
    sample_pages = list(range(0, pages, step))[:16]
    if pages - 1 not in sample_pages:
        sample_pages.append(pages - 1)

    total_long_s = 0
    garbled_pages = 0

    for pn in sample_pages:
        text = doc[pn].get_text().strip()
        if not text:
            garbled_pages += 1
            continue

        words = set(re.findall(r'\b[a-z]{3,}\b', text.lower()))
        long_s_count = len(words & LONG_S_WORDS)
        total_long_s += long_s_count

        garbled = len(re.findall(r'\b[A-Z][%^@#\d]', text[:300]))
        spaced_letters = len(re.findall(r'\b([A-Z])\s([A-Z])\s([A-Z])', text[:200]))
        noise = len(re.findall(r'[^\w\s.,;:!?\'\"\-()\[\]/&—–\u2013\u2014\u2018\u2019\u201c\u201d]', text))
        noise_ratio = noise / max(len(text), 1)

        if garbled > 2 or spaced_letters > 1 or noise_ratio > 0.03:
            garbled_pages += 1

    doc.close()

    score = 100
    score -= total_long_s * 0.5
    score -= garbled_pages * 5
    score = max(0, score)

    return score, total_long_s, garbled_pages, pages


def sample_readability(path, pages):
    """Sample-read 3 pages (beginning, middle, end) to verify semantic readability."""
    doc = pymupdf.open(path)
    samples = [min(5, pages - 1), pages // 2, max(0, pages - 6)]
    samples = sorted(set(s for s in samples if 0 <= s < pages))

    results = []
    for pn in samples:
        text = doc[pn].get_text().strip()
        preview = text[:500].replace('\n', ' ¶ ')
        words = len(text.split())
        results.append((pn, words, preview))
    doc.close()
    return results


if __name__ == "__main__":
    base = sys.argv[1] if len(sys.argv) > 1 else "."
    pdfs = sorted([f for f in os.listdir(base) if f.endswith('.pdf') and not f.startswith('._')])

    results = []
    for pdf in pdfs:
        path = os.path.join(base, pdf)
        try:
            doc = pymupdf.open(path)
            total_chars = sum(len(doc[i].get_text().strip()) for i in range(doc.page_count))
            doc.close()

            if total_chars < 500:
                print(f"💀 SCANNED | 0 chars | {pdf[:80]}")
                results.append(("SCANNED", 0, 0, 0, os.path.getsize(path) // 1024, pdf))
                continue

            score, long_s, garbled, pages = quality_score_pdf(path)

            if score >= 80:
                v = "✅ CLEAN"
            elif score >= 60:
                v = "🔶 DEGRADED"
            else:
                v = "🔴 BAD"

            print(f"{v} | score={score:.0f}/100 | {pages}p | {total_chars:,} chars | long_s={long_s} | garbled_p={garbled} | {pdf[:80]}")
            results.append((v, score, long_s, garbled, pages, pdf, path))
        except Exception as e:
            print(f"❌ ERROR: {e} | {pdf[:80]}")
            results.append(("ERROR", 0, 0, 0, 0, pdf, None))

    # Readability sampling for CLEAN PDFs
    print("\n" + "=" * 70)
    print("READABILITY SPOT-CHECK (CLEAN PDFs)")
    print("=" * 70)

    for v, score, long_s, garbled, pages, pdf, path in results:
        if v != "✅ CLEAN" or path is None:
            continue
        print(f"\n── {pdf[:80]}")
        try:
            samples = sample_readability(path, pages)
            for pn, words, preview in samples:
                print(f"   Page {pn} ({words} words): {preview[:200]}...")
        except Exception as e:
            print(f"   ⚠️ Readability check failed: {e}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    clean = [(s, sc, ls, g, p, f) for s, sc, ls, g, p, f in results if s == "✅ CLEAN"]
    degraded = [(s, sc, ls, g, p, f) for s, sc, ls, g, p, f in results if s in ("🔶 DEGRADED", "🔴 BAD")]
    scanned = [(s, sc, ls, g, p, f) for s, sc, ls, g, p, f in results if s == "SCANNED"]

    print(f"\n✅ CLEAN: {len(clean)}")
    for s, sc, ls, g, p, f in clean:
        print(f"   [{sc:.0f}] {f[:90]}")

    print(f"\n📥 OCR queue: {len(degraded) + len(scanned)}")
    for s, sc, ls, g, p, f in degraded:
        print(f"   [{s}] score={sc:.0f} | {f[:90]}")
    for s, sc, ls, g, p, f in scanned:
        print(f"   [{s}] {f[:90]}")

    print(f"\n🎫 Ready for tickets: {len(clean)}")
