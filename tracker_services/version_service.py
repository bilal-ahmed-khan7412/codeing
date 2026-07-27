from pathlib import Path
import re

class VersionService:
    @staticmethod
    def next_version_path(input_path: str, output_dir: str | None = None) -> str:
        p = Path(input_path)
        out_dir = Path(output_dir) if output_dir else p.parent
        stem = p.stem
        # If already ends in _vN, increment. Otherwise append _v1.
        m = re.search(r"_v(\d+)$", stem)
        if m:
            base = stem[:m.start()]
            n = int(m.group(1)) + 1
        else:
            base = stem
            n = 1
        candidate = out_dir / f"{base}_v{n}{p.suffix or '.xlsx'}"
        while candidate.exists():
            n += 1
            candidate = out_dir / f"{base}_v{n}{p.suffix or '.xlsx'}"
        return str(candidate)
