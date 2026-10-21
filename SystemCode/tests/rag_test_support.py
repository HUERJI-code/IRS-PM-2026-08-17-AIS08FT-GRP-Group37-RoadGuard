"""Deterministic embedding doubles for control-flow tests, never semantic-quality evidence."""
import numpy as np
from roadguard.assistant.content import clean_text


class FixtureEncoder:
    identity = 'test-only-section-vectors-v1'

    def __init__(self, package):
        self.dimensions = len(package.chunks) + 1
        self.texts = {clean_text(c.text): i for i, c in enumerate(package.chunks)}
        self.citations = {c.citation_id: i for i, c in enumerate(package.chunks)}
        self.document_calls = 0

    def spans(self, text):
        return [(0, len(text))]

    def encode(self, texts, *, query=False):
        output = []
        for text in texts:
            if not query:
                self.document_calls += 1
                index = self.texts[text]
            else:
                lower = text.lower()
                citation = None
                if 'nus-iss' in lower:
                    citation = 'rg-kb-scope#depot-crews'
                elif any(word in lower for word in ['pothole', '\u5751\u6d1e', '\u89c4\u5219']):
                    citation = 'rg-kb-demo-rules#demo-rule-table'
                elif any(word in lower for word in ['account', '\u8d26\u53f7']):
                    citation = 'rg-kb-workflow#workflow-account-roles'
                elif 'mutation' in lower:
                    citation = 'rg-kb-routing#routing-ga'
                elif 'greedy' in lower:
                    citation = 'rg-kb-demo-rules#routing-demo-settings'
                elif '\u671f\u9650' in lower:
                    citation = 'rg-kb-demo-rules#demo-null-provenance'
                index = self.citations.get(citation, self.dimensions - 1)
            vector = np.zeros(self.dimensions, dtype=np.float32)
            vector[index] = 1
            output.append(vector.tolist())
        return output
