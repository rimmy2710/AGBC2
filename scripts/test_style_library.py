from __future__ import annotations

import os
from news_agent.pipeline.style_library import load_style_examples, resolve_style_dir

def main() -> None:
    style_name = os.getenv("STYLE_NAME", "telegram_casual")
    style_dir = resolve_style_dir(None)
    examples = load_style_examples(style_dir, style_name, max_examples=10)
    print("style_dir=", style_dir)
    print("style_name=", style_name)
    print("examples_count=", len(examples))
    if examples:
        print("example_1_preview=", examples[0][:120].replace("\n", "\\n"))

if __name__ == "__main__":
    main()
