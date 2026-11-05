"""Step 1: turn the markdown file into a topic tree (topics.json).

# heading   -> chapter
## heading  -> subchapter
### heading -> example (or "section" if it is not an example)
"""
import json, re, sys
from pathlib import Path

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "chapter_5_clean.md")
OUT = Path("topics.json")

PAGE_COMMENT = re.compile(r"<!--.*?-->", re.S)
HEADING = re.compile(r"^(#{1,3})\s+(.*\S)\s*$")


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:48]


def main():
    raw = PAGE_COMMENT.sub("", SRC.read_text(encoding="utf-8"))
    nodes, stack, used = [], [], set()

    for line in raw.splitlines():
        m = HEADING.match(line)
        if m:
            level, title = len(m.group(1)), m.group(2).strip()
            while stack and stack[-1]["level"] >= level:
                stack.pop()
            parent = stack[-1] if stack else None
            nid = slug(title) or f"node-{len(nodes)}"
            while nid in used:
                nid += "-x"
            used.add(nid)
            if level == 1:
                ntype = "chapter"
            elif level == 2:
                ntype = "exercises" if "REVIEW" in title.upper() else "subchapter"
            else:
                is_ex = "EXAMPLE" in title.upper() or (parent and "example" in parent["title"].lower())
                ntype = "example" if is_ex else "section"
            node = dict(id=nid, level=level, type=ntype, title=title,
                        parent=parent["id"] if parent else None, children=[], _lines=[], _full=[f"{'#'*level} {title}"])
            nodes.append(node)
            if parent:
                parent["children"].append(nid)
            stack.append(node)
        elif stack:
            stack[-1]["_lines"].append(line)
            for n in stack:                      # text also belongs to every ancestor's full_text
                n["_full"].append(line)

    for n in nodes:
        n["text"] = re.sub(r"\n{3,}", "\n\n", "\n".join(n.pop("_lines"))).strip()
        n["full_text"] = re.sub(r"\n{3,}", "\n\n", "\n".join(n.pop("_full"))).strip()

    OUT.write_text(json.dumps(nodes, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(nodes)} topics -> {OUT}")
    for n in nodes:
        print("  " * (n["level"] - 1) + f"[{n['type']}] {n['title']}  ({len(n['full_text'])} chars)")


if __name__ == "__main__":
    main()
