import pandas as pd
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parents[1]
BRONZE_DIR = BASE_DIR / "data" / "bronze"
LOG_DIR = BASE_DIR / "artifacts" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

FILES = {
    "tiktok_videos": "tiktok_videos_clean.csv",
    "tiktok_comments": "tiktok_comments_clean.csv",
    "facebook_posts": "facebook_posts_clean.csv",
    "facebook_comments": "facebook_comments_clean.csv",
}

def read_csv_safely(path: Path):
    encodings = ["utf-8-sig", "utf-8", "cp1258", "cp1252", "latin1"]
    last_error = None

    for enc in encodings:
        try:
            df = pd.read_csv(path, encoding=enc, low_memory=False)
            return df, enc
        except Exception as e:
            last_error = e

    raise RuntimeError(f"Cannot read {path}. Last error: {last_error}")

def main():
    lines = []
    lines.append("# Input Data Check Log")
    lines.append(f"Run at: {datetime.now().isoformat()}")
    lines.append("")

    all_ok = True

    for name, filename in FILES.items():
        path = BRONZE_DIR / filename
        lines.append(f"## {name}")
        lines.append(f"File: {filename}")

        if not path.exists():
            all_ok = False
            lines.append("Status: MISSING")
            lines.append("")
            continue

        try:
            df, enc = read_csv_safely(path)
            lines.append("Status: OK")
            lines.append(f"Encoding detected: {enc}")
            lines.append(f"Rows: {len(df):,}")
            lines.append(f"Columns: {len(df.columns):,}")
            lines.append("Column names:")

            for col in df.columns:
                lines.append(f"- {col}")

            sample_text_cols = [
                c for c in df.columns
                if any(k in c.lower() for k in ["text", "caption", "comment", "content", "description", "message"])
            ]

            if sample_text_cols:
                col = sample_text_cols[0]
                sample = df[col].dropna().astype(str).head(3).tolist()
                lines.append(f"Sample text column: {col}")

                for idx, value in enumerate(sample, start=1):
                    value = value.replace("\n", " ")[:250]
                    lines.append(f"  {idx}. {value}")

        except Exception as e:
            all_ok = False
            lines.append("Status: ERROR")
            lines.append(f"Error: {e}")

        lines.append("")

    lines.append("## Final Status")
    lines.append("PASS" if all_ok else "FAIL")

    log_text = "\n".join(lines)
    log_path = LOG_DIR / "phase1_input_data_check.md"
    log_path.write_text(log_text, encoding="utf-8")

    print(log_text)
    print(f"\nSaved log to: {log_path}")

if __name__ == "__main__":
    main()
