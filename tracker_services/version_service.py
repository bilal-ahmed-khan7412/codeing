from pathlib import Path
import re

class VersionService:
    # Kept intentionally small - these are full workbook copies, one per
    # edit, with nothing else ever cleaning them up.
    MAX_VERSIONS = 10

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
        suffix = p.suffix or '.xlsx'
        candidate = out_dir / f"{base}_v{n}{suffix}"
        while candidate.exists():
            n += 1
            candidate = out_dir / f"{base}_v{n}{suffix}"
        VersionService._prune_old_versions(out_dir, base, suffix)
        return str(candidate)

    @staticmethod
    def _prune_old_versions(out_dir: Path, base: str, suffix: str):
        """Keep only the most recent MAX_VERSIONS copies of base_vN.suffix in
        out_dir. next_version_path never deleted anything on its own, so a
        workbook edited repeatedly accumulated a full copy per edit forever."""
        if not out_dir.exists():
            return
        pattern = re.compile(rf"^{re.escape(base)}_v(\d+){re.escape(suffix)}$")
        versions = []
        for f in out_dir.iterdir():
            m = pattern.match(f.name)
            if m:
                versions.append((int(m.group(1)), f))
        versions.sort(key=lambda x: x[0], reverse=True)
        for _, f in versions[VersionService.MAX_VERSIONS:]:
            try:
                f.unlink()
            except OSError:
                pass
