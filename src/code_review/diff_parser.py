import re


def parse_diff(changed_files):
    entries = []

    for file_data in changed_files:
        filename = file_data.get("filename", "")
        patch = file_data.get("patch", "")
        status = file_data.get("status", "")

        # Skip deleted files and binary files
        if status == "removed" or not patch:
            continue

        # Skip non-code files
        if should_skip_file(filename):
            continue

        chunks = parse_patch(patch)
        if chunks:
            entries.append({
                "path": filename,
                "status": status,
                "chunks": chunks,
            })

    return entries


def parse_patch(patch):
    chunks = []
    current_chunk = None
    current_new_line = 0
    position = 0  # 1-based position in the diff (needed for commit comments API)

    for line in patch.split("\n"):
        # Match hunk header: @@ -old_start,old_count +new_start,new_count @@
        hunk_match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if hunk_match:
            if current_chunk:
                chunks.append(current_chunk)
            current_new_line = int(hunk_match.group(1))
            position += 1
            current_chunk = {
                "lines": [],
                "added_lines": [],
                "changed_lines": {},  # line_number -> diff position
                "annotated_lines": [],  # lines with line numbers for Gemini
            }
            continue

        if current_chunk is None:
            continue

        position += 1
        current_chunk["lines"].append(line)

        if line.startswith("+") and not line.startswith("+++"):
            current_chunk["added_lines"].append(current_new_line)
            current_chunk["changed_lines"][current_new_line] = position
            current_chunk["annotated_lines"].append(f"L{current_new_line}: {line}")
            current_new_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            # Deleted lines: track position for commenting
            current_chunk["annotated_lines"].append(f"     : {line}")
        else:
            # Context line
            current_chunk["changed_lines"][current_new_line] = position
            current_chunk["annotated_lines"].append(f"L{current_new_line}: {line}")
            current_new_line += 1

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def should_skip_file(filename):
    skip_extensions = {
        ".lock", ".sum", ".mod", ".min.js", ".min.css",
        ".map", ".svg", ".png", ".jpg", ".jpeg", ".gif",
        ".ico", ".woff", ".woff2", ".ttf", ".eot",
    }
    skip_files = {
        "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
        "composer.lock", "Gemfile.lock", "Cargo.lock",
        "poetry.lock", "Pipfile.lock",
    }

    if filename in skip_files:
        return True

    lower_name = filename.lower()
    if any(lower_name.endswith(ext) for ext in skip_extensions):
        return True

    return False


def _splitext(filename):
    dot_index = filename.rfind(".")
    if dot_index == -1:
        return filename, ""
    return filename[:dot_index], filename[dot_index:]
