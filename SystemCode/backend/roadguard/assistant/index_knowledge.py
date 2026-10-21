"""Run: python -m roadguard.assistant.index_knowledge [--download-model]."""
import argparse
import json

from .embedding import RetrievalSettings, download_model
from .knowledge import load_package
from .vector_store import get_store


def main():
    parser = argparse.ArgumentParser(description='Build the verified local Chroma knowledge index.')
    parser.add_argument('--download-model', action='store_true',
                        help='Download only the pinned public E5 model/tokenizer after checksum verification.')
    args = parser.parse_args()
    package = load_package()
    if args.download_model:
        download_model(RetrievalSettings.from_env().model_path)
    result = get_store().build(package)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
