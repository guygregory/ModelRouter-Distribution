import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def select_results_file(results_dir: Path) -> Path:
    matches = sorted(results_dir.glob("results*.jsonl"))

    if not matches:
        print("No files matching results*.jsonl found. Run the batch script first.")
        sys.exit(1)

    if len(matches) == 1:
        return matches[0]

    print("Select a results file to plot:")
    for idx, path in enumerate(matches, start=1):
        print(f"  {idx}. {path.name}")

    while True:
        choice = input(f"Enter choice [1-{len(matches)}] (default 1): ").strip()
        if not choice:
            return matches[0]
        if choice.isdigit():
            index = int(choice)
            if 1 <= index <= len(matches):
                return matches[index - 1]
        print("Invalid selection. Please enter a valid option.")


def main() -> None:
    results_path = select_results_file(Path(__file__).parent)

    if results_path.stat().st_size == 0:
        print(f"{results_path.name} is empty. Nothing to plot yet.")
        sys.exit(0)

    try:
        df = pd.read_json(results_path, lines=True)
    except ValueError:
        print(f"{results_path.name} contains no valid records.")
        sys.exit(0)

    model_counts = df["model"].value_counts().sort_values(ascending=False)

    ax = model_counts.plot(kind="barh")
    ax.set_xlabel("Count")
    ax.set_ylabel("Model")
    stem_parts = results_path.stem.split("_", 1)
    title_suffix = stem_parts[1] if len(stem_parts) > 1 else stem_parts[0]
    formatted_suffix = title_suffix.replace("_", " ").title()
    ax.set_title(f"Model Router (2025-11-18) - {formatted_suffix}")
    ax.invert_yaxis()
    max_count = model_counts.max()
    ax.set_xlim(0, max_count * 1.2)

    for container in ax.containers:
        ax.bar_label(container, label_type="edge", padding=2)

    chart_path = results_path.parent / f"chart_{title_suffix}.png"
    ax.figure.savefig(chart_path, dpi=300, bbox_inches="tight")
    plt.tight_layout()
    plt.show(block=False)
    plt.pause(0.1)

    prompt = "Press any key to quit..."
    print(prompt, flush=True)
    try:
        if sys.platform.startswith("win"):
            import msvcrt

            msvcrt.getch()
        else:
            input()
    except KeyboardInterrupt:
        pass
    finally:
        plt.close("all")


if __name__ == "__main__":
    main()
