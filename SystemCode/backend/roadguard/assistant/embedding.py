"""Pinned multilingual E5 embeddings, computed locally without PyTorch or API calls."""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import os
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np

from roadguard.errors import AppError
from .knowledge import ROOT

MODEL_ID = 'intfloat/multilingual-e5-small'
MODEL_REVISION = '614241f622f53c4eeff9890bdc4f31cfecc418b3'
EMBEDDING_ID = f'{MODEL_ID}@{MODEL_REVISION}:onnx-mean-l2-v1'
DIMENSIONS = 384
MAX_TOKENS = 512
FILES = {
    'model.onnx': ('onnx/model.onnx', 470268510, 'ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665'),
    'tokenizer.json': ('tokenizer.json', 17082730, '0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39'),
}


@dataclass(frozen=True)
class RetrievalSettings:
    database_path: Path
    model_path: Path
    min_similarity: float = 0.78

    @classmethod
    def from_env(cls):
        def path(key, default):
            value = Path(os.environ.get(key, default)).expanduser()
            return (ROOT / value).resolve() if not value.is_absolute() else value.resolve()
        try:
            minimum = float(os.environ.get('ROADGUARD_RAG_MIN_SIMILARITY', '0.78'))
            if not 0 <= minimum <= 1:
                raise ValueError()
            return cls(path('ROADGUARD_CHROMA_PATH', 'SystemCode/backend/data/rag/chroma'),
                       path('ROADGUARD_EMBEDDING_PATH', 'SystemCode/backend/data/rag/models/multilingual-e5-small'),
                       minimum)
        except (ValueError, OSError):
            raise AppError('retrieval_configuration_error', 'The retrieval configuration is invalid.', 503) from None


def valid_artifact(path: Path, size: int, sha256: str) -> bool:
    if not path.is_file() or path.stat().st_size != size:
        return False
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest() == sha256


def download_model(directory: Path, progress=print):
    """Explicit setup only. Verify official pinned LFS hashes before publishing files."""
    directory.mkdir(parents=True, exist_ok=True)
    for name, (remote, size, digest) in FILES.items():
        target = directory / name
        if valid_artifact(target, size, digest):
            progress(f'{name}: verified cached file')
            continue
        progress(f'Downloading {name} ({size / 1_000_000:.1f} MB)')
        temporary = target.with_suffix(target.suffix + '.part')
        request = Request(f'https://huggingface.co/{MODEL_ID}/resolve/{MODEL_REVISION}/{remote}',
                          headers={'User-Agent': 'RoadGuard-embedding-setup'})
        with urlopen(request, timeout=60) as response, temporary.open('wb') as output:
            total = 0
            while data := response.read(1024 * 1024):
                total += len(data)
                if total > size:
                    raise ValueError('Embedding artifact exceeds the pinned size.')
                output.write(data)
        if not valid_artifact(temporary, size, digest):
            raise ValueError('Embedding artifact failed its pinned checksum.')
        temporary.replace(target)
        progress(f'{name}: checksum verified')


class LocalE5Encoder:
    identity = EMBEDDING_ID
    dimensions = DIMENSIONS

    def __init__(self, directory: Path):
        for name, (_, size, digest) in FILES.items():
            if not valid_artifact(directory / name, size, digest):
                raise AppError('embedding_model_unavailable',
                               'Run the knowledge indexing setup to install the verified embedding model.', 503)
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.tokenizer = Tokenizer.from_file(str(directory / 'tokenizer.json'))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        self.batch_tokenizer = Tokenizer.from_file(str(directory / 'tokenizer.json'))
        self.batch_tokenizer.no_truncation()
        self.batch_tokenizer.enable_padding(pad_id=1, pad_token='<pad>')
        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        options.inter_op_num_threads = 1
        options.log_severity_level = 3
        self.session = ort.InferenceSession(str(directory / 'model.onnx'), sess_options=options,
                                            providers=['CPUExecutionProvider'])

    def spans(self, text: str, size=320, overlap=48) -> list[tuple[int, int]]:
        """Token-aware character spans preserve exact source substrings, including Unicode."""
        if not 0 <= overlap < size:
            raise ValueError('Invalid passage overlap.')
        offsets = self.tokenizer.encode(text, add_special_tokens=False).offsets
        if not offsets:
            return []
        result = []
        for start in range(0, len(offsets), size - overlap):
            end = min(start + size, len(offsets))
            result.append((0 if start == 0 else offsets[start][0],
                           len(text) if end == len(offsets) else offsets[end - 1][1]))
            if end == len(offsets):
                break
        return result

    def encode(self, texts: list[str], *, query=False) -> list[list[float]]:
        output = []
        for start in range(0, len(texts), 8):
            inputs = [('query: ' if query else 'passage: ') + value for value in texts[start:start + 8]]
            encoded = self.batch_tokenizer.encode_batch(inputs)
            if any(len(item.ids) > MAX_TOKENS for item in encoded):
                raise AppError('retrieval_input_too_long', 'Text exceeds the embedding token limit.', 422)
            ids = np.asarray([item.ids for item in encoded], dtype=np.int64)
            mask = np.asarray([item.attention_mask for item in encoded], dtype=np.int64)
            feed = {'input_ids': ids, 'attention_mask': mask, 'token_type_ids': np.zeros_like(ids)}
            hidden = self.session.run(None, {i.name: feed[i.name] for i in self.session.get_inputs()})[0]
            pooled = (hidden * mask[..., None]).sum(axis=1) / mask.sum(axis=1)[:, None]
            normalized = pooled / np.linalg.norm(pooled, axis=1, keepdims=True)
            if normalized.shape != (len(inputs), DIMENSIONS) or not np.isfinite(normalized).all():
                raise ValueError('Invalid embedding output.')
            output.extend(normalized.astype(np.float32).tolist())
        return output


@lru_cache(maxsize=2)
def get_encoder(directory: Path) -> LocalE5Encoder:
    return LocalE5Encoder(directory)
