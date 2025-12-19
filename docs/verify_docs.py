#!/usr/bin/env python3
"""
Verification script for Sphinx documentation.
Checks that all RST files are properly formatted and linked.
"""

import re
from pathlib import Path

def check_rst_file(rst_path):
    """Check an RST file for common issues."""
    issues = []
    content = rst_path.read_text()
    lines = content.splitlines()
    
    # Check for title underline consistency
    title_pattern = re.compile(r'^[=#\-^~_+*<>`]+$')
    prev_line = None
    for i, line in enumerate(lines):
        if title_pattern.match(line) and prev_line:
            # Check if underline matches title length
            if len(line) < len(prev_line.strip()):
                issues.append(f"Line {i+1}: Title underline shorter than title")
        prev_line = line
    
    # Check for broken internal links
    doc_pattern = re.compile(r':doc:`([^`]+)`')
    for match in doc_pattern.finditer(content):
        doc_name = match.group(1)
        # Check if referenced file exists
        doc_file = Path(rst_path.parent) / f"{doc_name}.rst"
        if not doc_file.exists() and doc_name not in ['genindex', 'modindex', 'search']:
            issues.append(f"Broken doc reference: {doc_name}")
    
    # Check for code blocks
    code_block_count = content.count('.. code-block::')
    if code_block_count > 0:
        # Verify code blocks are properly closed
        if content.count('```') % 2 != 0:
            issues.append("Unclosed code block detected")
    
    return issues

def main():
    """Main verification function."""
    docs_dir = Path(__file__).parent
    rst_files = list(docs_dir.glob("*.rst"))
    
    print("=" * 70)
    print("SPHINX DOCUMENTATION VERIFICATION")
    print("=" * 70)
    
    all_issues = []
    for rst_file in sorted(rst_files):
        issues = check_rst_file(rst_file)
        if issues:
            print(f"\n⚠️  {rst_file.name}:")
            for issue in issues:
                print(f"   - {issue}")
            all_issues.extend(issues)
        else:
            print(f"✓ {rst_file.name:30s} - OK")
    
    print("\n" + "=" * 70)
    if all_issues:
        print(f"⚠️  Found {len(all_issues)} issue(s)")
    else:
        print("✅ All documentation files verified successfully!")
    print("=" * 70)
    
    # Check required files
    required = ['index.rst', 'conf.py']
    missing = [f for f in required if not (docs_dir / f).exists()]
    if missing:
        print(f"\n❌ Missing required files: {', '.join(missing)}")
    else:
        print("\n✅ All required files present")
    
    return len(all_issues) == 0

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

