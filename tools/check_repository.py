"""Check catalog structure and recorded tool identity; no asset code is executed."""
import argparse
import hashlib
import json
import pathlib
import re
import sys
from urllib.parse import urlsplit


class Invalid(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise Invalid(message)


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, "duplicate JSON key: " + key)
        result[key] = value
    return result


def regular(root, relative):
    need(isinstance(relative, str) and relative.strip(), "file path must be nonempty text")
    path = pathlib.PurePosixPath(relative)
    need("\\" not in relative and ":" not in relative and not path.is_absolute()
         and all(part not in ("", ".", "..") for part in relative.split("/")),
         "unsafe relative file path: " + relative)
    target = root.joinpath(*path.parts)
    for parent in (target, *target.parents):
        if parent == root:
            break
        need(not parent.is_symlink(), "symbolic link is not a submitted regular file: " + relative)
    need(target.resolve().is_relative_to(root), "file escapes repository: " + relative)
    need(target.is_file(), "missing regular file: " + relative)
    return target


def read_json(root, relative):
    try:
        return json.loads(regular(root, relative).read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise Invalid(relative + ": " + str(error)) from error


def text(value):
    return isinstance(value, str) and bool(value.strip())


def https_source(value):
    if not text(value):
        return False
    try:
        parsed = urlsplit(value)
        return (parsed.scheme == "https" and bool(parsed.hostname) and parsed.username is None
                and parsed.password is None and not any(c.isspace() for c in value))
    except ValueError:
        return False


def check(root, trusted):
    expected = read_json(trusted, "catalog.json")
    catalog = read_json(root, "catalog.json")
    need(isinstance(catalog, dict), "catalog must be an object")
    for field in ("schema", "repository", "category", "futureTarget"):
        need(catalog.get(field) == expected.get(field), "catalog identity/target differs from trusted main: " + field)
    items = catalog.get("items")
    need(isinstance(items, list), "items must be an array")
    seen = set()
    for index, item in enumerate(items):
        prefix = f"items[{index}]"
        need(isinstance(item, dict), prefix + " must be an object")
        for key in ("id", "name", "author", "rights", "verification"):
            need(text(item.get(key)), prefix + "." + key + " must be nonempty text")
        need(item["id"] not in seen, prefix + ".id duplicates an earlier item")
        seen.add(item["id"])
        need(https_source(item.get("sourceUrl")), prefix + ".sourceUrl must be a credential-free HTTPS URL")
        files = item.get("files")
        need(isinstance(files, list), prefix + ".files must be an array; use [] for link-only")
        need(len(files) == len(set(f for f in files if isinstance(f, str))), prefix + ".files contains duplicates or non-text paths")
        for relative in files:
            regular(root, relative)
    # A candidate may change both files and its own manifest. Compare the manifest
    # to this trusted checker's checkout before using any candidate hashes.
    baseline = read_json(trusted, "tools/PROVENANCE.json")
    provenance = read_json(root, "tools/PROVENANCE.json")
    need(provenance == baseline, "PROVENANCE differs from trusted main; review tool/source changes separately")
    records = baseline.get("files")
    need(isinstance(records, list) and records, "trusted PROVENANCE files are missing")
    for entry in records:
        need(isinstance(entry, dict), "invalid trusted PROVENANCE record")
        relative, digest = entry.get("path"), entry.get("vendoredSha256")
        need(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest), "invalid recorded SHA256")
        need(hashlib.sha256(regular(root, relative).read_bytes()).hexdigest() == digest,
             "recorded tool bytes differ: " + str(relative))
    return len(items)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=pathlib.Path, help="candidate checkout; default is this script's repository")
    args = parser.parse_args()
    trusted = pathlib.Path(__file__).resolve().parent.parent
    root = (args.root or trusted).resolve()
    try:
        count = check(root, trusted)
    except (Invalid, OSError, TypeError, KeyError, AttributeError) as error:
        print("FAIL: " + str(error), file=sys.stderr)
        return 1
    print(f"PASS: {count} catalog item(s); structure and recorded tool bytes only.")
    print("Not checked: rights validity, link availability, asset safety/quality, or actual verification claims.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
