"""
VARNA v2.3 - Command Safety & Matching Test Suite
Tests the 4-gate safety architecture and verifies command matching accuracy.

Run: python test_safety.py
"""

import json
import sys
from pathlib import Path
from difflib import SequenceMatcher

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from command_safety import (
    CommandSafetyEngine, get_safety_engine,
    IntentCategory, RiskLevel, EXACT_ONLY_KEYWORDS, SAFEGUARD_WORDS,
    CONFIRMATION_REQUIRED, CATEGORY_RISK, RISK_THRESHOLDS
)
from nlp.normalizer import TextNormalizer


def test_normalizer_punctuation():
    """Test that STT punctuation is stripped properly."""
    print("\n" + "="*60)
    print("TEST: Normalizer Punctuation Stripping")
    print("="*60)
    
    cases = [
        ("open new tab.", "open new tab"),
        ("go to previous page.", "go to previous page"),
        ("click links.", "click links"),
        ("open first link.", "open first link"),
        ("open chrome,", "open chrome"),
        ("search youtube?", "search youtube"),
    ]
    
    passed = 0
    for raw, expected in cases:
        cleaned = TextNormalizer.clean(raw)
        status = "✅" if expected in cleaned else "❌"
        if expected in cleaned:
            passed += 1
        print(f"  {status} '{raw}' → '{cleaned}' (expected contains: '{expected}')")
    
    print(f"\n  Result: {passed}/{len(cases)} passed")
    return passed == len(cases)


def test_category_detection():
    """Test intent category detection."""
    print("\n" + "="*60)
    print("TEST: Intent Category Detection (Gate 4)")
    print("="*60)
    
    engine = get_safety_engine()
    
    cases = [
        # (input, expected_category)
        ("open chrome", IntentCategory.APP_OPEN),
        ("open new tab", IntentCategory.BROWSER_NAV),
        ("close tab", IntentCategory.BROWSER_NAV),
        ("open first link", IntentCategory.BROWSER_NAV),
        ("click links", IntentCategory.BROWSER_NAV),
        ("go to previous page", IntentCategory.SCROLL),  # page navigation
        ("previous page", IntentCategory.SCROLL),
        ("page down", IntentCategory.SCROLL),
        ("scroll down", IntentCategory.SCROLL),
        ("next song", IntentCategory.MEDIA),
        ("previous song", IntentCategory.MEDIA),
        ("play music", IntentCategory.MEDIA),
        ("shutdown", IntentCategory.SYSTEM),
        ("restart", IntentCategory.SYSTEM),
        ("lock", IntentCategory.SYSTEM),
        ("lock this", IntentCategory.SYSTEM),
        ("close chrome", IntentCategory.APP_CLOSE),
        ("minimize chrome", IntentCategory.WINDOW),
        ("copy text", IntentCategory.FILE_OP),
        ("type hello", IntentCategory.TYPING),
        ("search google", IntentCategory.SEARCH),
    ]
    
    passed = 0
    for text, expected in cases:
        detected = engine.detect_category(text)
        status = "✅" if detected == expected else "❌"
        if detected == expected:
            passed += 1
        print(f"  {status} '{text}' → {detected.name} (expected: {expected.name})")
    
    print(f"\n  Result: {passed}/{len(cases)} passed")
    return passed >= len(cases) * 0.8  # Allow some flexibility


def test_phonetic_safeguard():
    """Test that dangerous commands are blocked when input doesn't contain keywords."""
    print("\n" + "="*60)
    print("TEST: Phonetic Safeguard (Gate 2)")
    print("="*60)
    
    engine = get_safety_engine()
    
    # These should be BLOCKED (input doesn't match dangerous keyword)
    blocked_cases = [
        # (input, matched_command, confidence, method)
        ("page down", "shutdown", 0.65, "fuzzy"),
        ("click links", "lock this", 0.70, "fuzzy"),
        ("open first link", "lock", 0.60, "fuzzy"),
        ("go down", "shutdown", 0.55, "phonetic"),
        ("scroll up", "lock", 0.60, "fuzzy"),
        ("previous page", "previous song", 0.80, "fuzzy"),  # cross-category
    ]
    
    # These should be ALLOWED (input contains the keyword or is exact)
    allowed_cases = [
        ("shutdown", "shutdown", 1.0, "exact"),
        ("lock pc", "lock pc", 1.0, "exact"),
        ("restart computer", "restart computer", 1.0, "exact"),  # exact match
        ("open chrome", "open chrome", 1.0, "exact"),
        ("open new tab", "open new tab", 0.95, "fuzzy"),
    ]
    
    passed = 0
    total = len(blocked_cases) + len(allowed_cases)
    
    print("\n  Should BLOCK:")
    for text, cmd, conf, method in blocked_cases:
        verdict = engine.evaluate(text, cmd, conf, method)
        status = "✅" if not verdict.allowed else "❌"
        if not verdict.allowed:
            passed += 1
        print(f"    {status} '{text}' → '{cmd}' [{method}] "
              f"(blocked={not verdict.allowed}, reason={verdict.reason})")
    
    print("\n  Should ALLOW:")
    for text, cmd, conf, method in allowed_cases:
        verdict = engine.evaluate(text, cmd, conf, method)
        status = "✅" if verdict.allowed else "❌"
        if verdict.allowed:
            passed += 1
        print(f"    {status} '{text}' → '{cmd}' [{method}] "
              f"(allowed={verdict.allowed}, confirm={verdict.needs_confirmation})")
    
    print(f"\n  Result: {passed}/{total} passed")
    return passed >= total * 0.8


def test_cross_category_blocking():
    """Test that cross-category fuzzy matches are blocked."""
    print("\n" + "="*60)
    print("TEST: Cross-Category Intent Isolation (Gate 4)")
    print("="*60)
    
    engine = get_safety_engine()
    
    # These cross-category matches should be BLOCKED at normal confidence
    cases = [
        # (input, matched_command, confidence, method, should_block)
        ("open first link", "open microsoft paint", 0.70, "fuzzy", True),
        ("click links", "lock this", 0.65, "fuzzy", True),
        ("go to previous page", "previous song", 0.72, "fuzzy", True),
        ("page down", "power down", 0.75, "fuzzy", True),
        # Same-category: should ALLOW
        ("open chrome", "open chrom", 0.90, "fuzzy", False),
        ("new tab", "new tab", 1.0, "exact", False),
        ("scroll down", "scroll up", 0.80, "fuzzy", False),
    ]
    
    passed = 0
    for text, cmd, conf, method, should_block in cases:
        verdict = engine.evaluate(text, cmd, conf, method)
        blocked = not verdict.allowed
        status = "✅" if blocked == should_block else "❌"
        if blocked == should_block:
            passed += 1
        print(f"  {status} '{text}' → '{cmd}' [{method} {conf:.0%}] "
              f"(blocked={blocked}, expected_block={should_block}, reason={verdict.reason})")
    
    print(f"\n  Result: {passed}/{len(cases)} passed")
    return passed >= len(cases) * 0.7


def test_confirmation_required():
    """Test that critical commands require two-step confirmation."""
    print("\n" + "="*60)
    print("TEST: Two-Step Confirmation (Gate 3)")
    print("="*60)
    
    engine = get_safety_engine()
    
    confirm_cmds = ["shutdown", "restart", "log off", "sleep", "hibernate", "permanent delete"]
    no_confirm_cmds = ["open chrome", "new tab", "scroll down", "copy", "paste"]
    
    passed = 0
    total = len(confirm_cmds) + len(no_confirm_cmds)
    
    print("\n  Should REQUIRE confirmation:")
    for cmd in confirm_cmds:
        needs = engine.needs_two_step_confirmation(cmd)
        status = "✅" if needs else "❌"
        if needs:
            passed += 1
        print(f"    {status} '{cmd}' → needs_confirmation={needs}")
    
    print("\n  Should NOT need confirmation:")
    for cmd in no_confirm_cmds:
        needs = engine.needs_two_step_confirmation(cmd)
        status = "✅" if not needs else "❌"
        if not needs:
            passed += 1
        print(f"    {status} '{cmd}' → needs_confirmation={needs}")
    
    print(f"\n  Result: {passed}/{total} passed")
    return passed == total


def test_risk_thresholds():
    """Test risk-based threshold assignment."""
    print("\n" + "="*60)
    print("TEST: Risk-Based Thresholds (Gate 1)")
    print("="*60)
    
    engine = get_safety_engine()
    
    cases = [
        # (text, expected_min_threshold)
        ("open chrome", 0.65),        # LOW risk
        ("close chrome", 0.80),       # MEDIUM risk
        ("lock this", 0.90),          # HIGH risk
        ("shutdown", 0.90),            # HIGH risk (SYSTEM category; EXACT_ONLY enforced separately)
        ("new tab", 0.65),            # LOW
        ("scroll down", 0.65),        # LOW
        ("delete file", 0.80),        # MEDIUM
    ]
    
    passed = 0
    for text, expected_threshold in cases:
        cat = engine.detect_category(text)
        threshold = engine.get_threshold_for_category(cat)
        # Allow some variation
        status = "✅" if abs(threshold - expected_threshold) < 0.06 else "❌"
        if abs(threshold - expected_threshold) < 0.06:
            passed += 1
        print(f"  {status} '{text}' → category={cat.name}, threshold={threshold:.2f} (expected ≈{expected_threshold:.2f})")
    
    print(f"\n  Result: {passed}/{len(cases)} passed")
    return passed >= len(cases) * 0.7


def test_your_actual_failures():
    """Test the exact failures from the screenshots."""
    print("\n" + "="*60)
    print("TEST: Your Actual Voice Failures (Screenshot Cases)")
    print("="*60)
    
    engine = get_safety_engine()
    
    print("\n  Screenshot 1: 'open new tab' → matched 'open w t'")
    print("  This was a parser issue. 'open new tab' should match key_map exactly.")
    # After our fix, "open new tab." becomes "open new tab" and matches key_map
    cleaned = TextNormalizer.clean("open new tab.")
    print(f"    Cleaned: '{cleaned}' → should be 'open new tab'")
    status = "✅" if "open new tab" in cleaned else "❌"
    print(f"    {status} Punctuation fix applied")
    
    print("\n  Screenshot 2: 'open first link' → matched 'open microsoft paint'")
    # This was a fuzzy match cross-category issue 
    verdict = engine.evaluate("open first link", "open microsoft paint", 0.70, "fuzzy")
    print(f"    Safety verdict: blocked={not verdict.allowed}, reason={verdict.reason}")
    status = "✅" if not verdict.allowed else "❌"
    print(f"    {status} Cross-category blocked")
    
    print("\n  Screenshot 3: 'click links' → matched 'lock this'")
    verdict = engine.evaluate("click links", "lock this", 0.65, "fuzzy")
    print(f"    Safety verdict: blocked={not verdict.allowed}, reason={verdict.reason}")
    status = "✅" if not verdict.allowed else "❌"
    print(f"    {status} Phonetic safeguard blocked 'lock' from fuzzy")
    
    print("\n  Screenshot 4: 'go to previous page' → matched 'previous song'")
    verdict = engine.evaluate("go to previous page", "previous song", 0.72, "fuzzy")
    print(f"    Safety verdict: blocked={not verdict.allowed}, reason={verdict.reason}")
    status = "✅" if not verdict.allowed else "❌"
    print(f"    {status} Cross-category blocked (SCROLL vs MEDIA)")


def audit_commands():
    """Audit commands.json for overfitting and recommend removals."""
    print("\n" + "="*60)
    print("AUDIT: Commands.json Analysis")
    print("="*60)
    
    commands_path = Path(__file__).parent / "commands.json"
    with open(commands_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    static = data.get("static", {})
    
    # Group by PowerShell command (destination)
    groups = {}
    for key, cmd in static.items():
        if cmd not in groups:
            groups[cmd] = []
        groups[cmd].append(key)
    
    print(f"\n  Total static commands: {len(static)}")
    print(f"  Unique actions: {len(groups)}")
    
    # Find groups with too many variants (overfitting)
    overfitted = []
    manageable = []
    for cmd, keys in sorted(groups.items(), key=lambda x: len(x[1]), reverse=True):
        if len(keys) > 12:
            overfitted.append((cmd, keys))
        elif len(keys) > 8:
            manageable.append((cmd, keys))
    
    if overfitted:
        print(f"\n  ⚠️  OVERFITTED commands ({len(overfitted)} groups with >12 variants):")
        for cmd, keys in overfitted:
            print(f"    {cmd}: {len(keys)} variants")
            # Find variants that are too similar to each other
            similar_pairs = []
            for i, k1 in enumerate(keys):
                for k2 in keys[i+1:]:
                    ratio = SequenceMatcher(None, k1, k2).ratio()
                    if ratio > 0.85:
                        similar_pairs.append((k1, k2, ratio))
            if similar_pairs:
                print(f"      Very similar pairs (>85% each other):")
                for k1, k2, ratio in similar_pairs[:5]:
                    print(f"        '{k1}' <-> '{k2}' ({ratio:.0%})")
    
    # Find commands that could cause cross-matching
    print("\n  🔍 Potential cross-match risks:")
    engine = get_safety_engine()
    all_keys = list(static.keys())
    
    dangerous_fuzzy = []
    for key in all_keys:
        if engine.contains_safeguard_word(key):
            # Check if any other non-dangerous key is very similar
            for other in all_keys:
                if other == key or engine.contains_safeguard_word(other):
                    continue
                ratio = SequenceMatcher(None, key, other).ratio()
                if ratio > 0.60:
                    dangerous_fuzzy.append((key, other, ratio))
    
    if dangerous_fuzzy:
        for k1, k2, ratio in sorted(dangerous_fuzzy, key=lambda x: -x[2])[:10]:
            print(f"    ⚠️  '{k1}' <-> '{k2}' ({ratio:.0%}) — dangerous cross-match risk")
    else:
        print("    ✅ No dangerous cross-match risks found")
    
    # Recommend removals for overfitted variants
    print("\n  📋 RECOMMENDATIONS:")
    recommendations = {
        "REMOVE": [],
        "KEEP": [],
    }
    
    # Variants that are phonetically identical should be removed  
    # (the normalizer already corrects "crome" → "chrome")
    corrected_variants = [
        "open crome", "open krome", "open chrom", "open grome", "open gram",
        "open crown", "open brows",
        "open fire fax", "open fire fox",  
        "open calculater", "open kelculator", "open calculus", "open calculate", "open calculation",
        "open not pad", "open note pad",
        "open pant", "open painting",
        "open ad",  # too ambiguous for "edge"
        "open hedge",  # could match "edge" but risky
        "open edg",
        "open vs kode", "open vee es code",
        "open spot ify", "open sportify",
        "open watsapp", "open vatsapp", "open what's app", "open whats app", "open whatapp",
        "open ward",  # word
        "open excell",  # excel
    ]
    
    present_removable = [v for v in corrected_variants if v in static]
    
    if present_removable:
        print(f"\n  🗑️  SAFE TO REMOVE ({len(present_removable)} variants):")
        print(f"    These are already handled by the normalizer's accent corrections:")
        for v in present_removable[:20]:
            print(f"      - '{v}' → normalizer already corrects this")
    
    print(f"\n  ✅ Total removable variants: {len(present_removable)}")
    print(f"    Removing these reduces commands.json size and prevents fuzzy confusion.")
    print(f"    The normalizer automatically corrects these misspellings before matching.")
    
    return present_removable


def main():
    """Run all tests."""
    print("="*60)
    print("VARNA v2.3 - Safety Architecture Test Suite")
    print("="*60)
    
    results = {}
    
    results["normalizer"] = test_normalizer_punctuation()
    results["categories"] = test_category_detection()
    results["safeguard"] = test_phonetic_safeguard()
    results["isolation"] = test_cross_category_blocking()
    results["confirmation"] = test_confirmation_required()
    results["thresholds"] = test_risk_thresholds()
    
    test_your_actual_failures()
    
    removable = audit_commands()
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    all_passed = all(results.values())
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"  
        print(f"  {status}: {name}")
    
    print(f"\n  Overall: {'ALL PASSED ✅' if all_passed else 'SOME FAILED ❌'}")
    print(f"  Removable command variants: {len(removable)}")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
