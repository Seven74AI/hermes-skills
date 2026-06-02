#!/usr/bin/env python3
"""Inline lazy-loaded route components for React Router 7 SSR.

Usage:
  python3 inline-lazy-routes.py <route_file> <lazy_file>

Example:
  python3 scripts/inline-lazy-routes.py \
    app/routes/admin+/cache.tsx \
    app/routes/admin+/__cache.lazy.tsx

What it does:
  1. Removes 'export const lazy' and the preceding comment from the route file
  2. Extracts ONLY 'export default function' and 'export function ErrorBoundary'
     blocks from the lazy file (not helper functions like CategorySelect,
     RoleCheckbox, StarRatingInput — those are already in the route file)
  3. Appends the extracted exports to the route file
  4. Verifies: no line-number prefixes, no duplicate exports

Why this exists:
  NEVER use head -n -3 + awk for inlining. It introduces literal line-number
  prefixes (    1|,     2|, etc.) into the source and can truncate files mid-JSX.
"""

import os
import re
import sys


def extract_exports(text: str) -> list[str]:
    """Extract only export default/function ErrorBoundary blocks from lazy file."""
    lines = text.split('\n')
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r'^export (default |function ErrorBoundary)', line):
            result.append(line)
            i += 1
            depth = line.count('{') - line.count('}')
            while i < len(lines) and depth > 0:
                l = lines[i]
                depth += l.count('{') - l.count('}')
                result.append(l)
                i += 1
        else:
            i += 1
    return result


def inline_route(route_path: str, lazy_path: str) -> bool:
    """Inline the lazy component into the route file. Returns True on success."""
    if not os.path.exists(route_path):
        print(f"ERROR: Route file not found: {route_path}", file=sys.stderr)
        return False
    if not os.path.exists(lazy_path):
        print(f"ERROR: Lazy file not found: {lazy_path}", file=sys.stderr)
        return False

    with open(route_path) as f:
        route_lines = f.readlines()

    # Remove '// Lazy-load...' comment and 'export const lazy' line
    cleaned = []
    skip = 0
    for line in route_lines:
        s = line.strip()
        if s.startswith('// Lazy-load'):
            skip = 2  # skip comment + export line
            continue
        if skip > 0:
            skip -= 1
            continue
        cleaned.append(line)

    while cleaned and cleaned[-1].strip() == '':
        cleaned.pop()
    cleaned.append('\n')
    cleaned.append('\n')

    # Read lazy file and extract exports
    with open(lazy_path) as f:
        lazy_text = f.read()

    exports = extract_exports(lazy_text)
    if not exports:
        print(f"WARNING: No exports found in {lazy_path}", file=sys.stderr)
        return False

    for exp_line in exports:
        cleaned.append(exp_line + '\n')

    # Write back
    with open(route_path, 'w') as f:
        f.writelines(cleaned)

    # Verify
    with open(route_path) as f:
        content = f.read()

    has_prefix = bool(re.search(r'^ *\d+\|', content, re.MULTILINE))
    if has_prefix:
        print(f"ERROR: Line-number prefix found in {route_path}!", file=sys.stderr)
        print("  Restore from git and re-run this script.", file=sys.stderr)
        return False

    # Check duplicate exports
    export_names = re.findall(r'^export default function (\w+)', content, re.MULTILINE)
    dupes = [n for n in set(export_names) if export_names.count(n) > 1]
    if dupes:
        print(f"ERROR: Duplicate exports in {route_path}: {dupes}", file=sys.stderr)
        print("  Remove the duplicate 'export default' or 'export function ErrorBoundary'.", file=sys.stderr)
        return False

    # Check for missing imports from the lazy file
    # Scan the inlined component body for react-router hooks and common imports
    HOOKS_TO_CHECK = [
        'useLoaderData', 'useActionData', 'useFetcher', 'useNavigation',
        'Outlet', 'useTranslation', 'useNavigate', 'useSubmit',
        'useSearchParams', 'useParams', 'useLocation', 'useRouteLoaderData',
    ]
    # Extract the component body (everything after the last export)
    component_start = max(
        (m.end() for m in re.finditer(
            r'^(?:export (?:default |async )?(?:function|const) )',
            content, re.MULTILINE)),
        default=0,
    )
    if component_start > 0:
        body = content[component_start:]
        # Find what's used in the body but NOT imported in the header
        header = content[:component_start]
        missing = []
        for hook in HOOKS_TO_CHECK:
            if re.search(rf'\b{re.escape(hook)}\b', body) and hook not in header:
                missing.append(hook)
        if missing:
            print(
                f"WARNING: {route_path} — inlined component uses {missing} "
                f"but they may not be imported! Add them to the import block "
                f"before rebuilding.",
                file=sys.stderr,
            )

    print(f"OK: {route_path} ({len(cleaned)} lines)")
    return True


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <route_file> <lazy_file>", file=sys.stderr)
        sys.exit(1)

    success = inline_route(sys.argv[1], sys.argv[2])
    sys.exit(0 if success else 1)
