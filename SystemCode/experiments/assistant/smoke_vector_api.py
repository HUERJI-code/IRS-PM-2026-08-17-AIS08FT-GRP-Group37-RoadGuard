"""Real local embeddings/Chroma through authenticated HTTP; GPT is an explicit double."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'SystemCode/backend'))
from fastapi.testclient import TestClient
from roadguard.assistant.query_models import ModelSelection
from roadguard.config import load_settings
from roadguard.main import create_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows = []
    with tempfile.TemporaryDirectory(prefix='roadguard-rag-http-') as directory:
        settings = load_settings({'ROADGUARD_DB_PATH': str(Path(directory) / 'business.sqlite3'),
                                  'ROADGUARD_VISION_MANIFEST_PATH': 'disabled',
                                  'ROADGUARD_TRAVEL_MATRIX_PROVIDER': 'simulated'})
        with TestClient(create_app(settings)) as client:
            password = 'isolated-synthetic-rag-smoke-password'
            client.app.state.auth_service.create_user('rag-smoke', 'Synthetic dispatcher', 'dispatcher', None, password)
            login = client.post('/api/v1/auth/login', json={'username': 'rag-smoke', 'password': password})
            assert login.status_code == 200
            client.headers['X-CSRF-Token'] = login.json()['csrf_token']
            with client.app.state.database.connect() as connection:
                before = list(connection.iterdump())
            for question, expected in [
                ('How does the genetic optimizer create and improve its population?', 'rg-kb-routing#routing-ga'),
                ('\u6df1\u5751\u6d1e\u9700\u8981\u5b89\u6392\u591a\u5c11\u7ef4\u4fee\u65f6\u95f4\uff1f', 'rg-kb-demo-rules#demo-rule-table'),
            ]:
                response = client.post('/api/v1/assistant/knowledge/search', json={'query': question, 'limit': 5})
                assert response.status_code == 200, response.text
                data = response.json()
                assert data['retrieval_method'] == 'chroma-e5-cosine-v1'
                assert expected in {h['citation_id'] for h in data['hits']}
                rows.append({'question': question, 'status': response.status_code, 'response': data})
            def select(config, user_id, question, scope, sources):
                source = next(s for s in sources if s['citation_id'] == 'rg-kb-demo-rules#demo-rule-table')
                return ModelSelection(supported=True, selections=[{
                    'citation_id': source['citation_id'], 'quote': source['content'][:500]}])
            with patch('roadguard.assistant.provider.select_evidence', side_effect=select), \
                 patch('roadguard.assistant.provider.build_opener', side_effect=AssertionError('No external provider calls')):
                response = client.post('/api/v1/assistant/query', json={
                    'question': 'How long does a deep pothole repair take?', 'scope': 'knowledge'})
            assert response.status_code == 200, response.text
            assert response.json()['supported'] and not response.json()['business_changes_applied']
            rows.append({'scope': 'answer_with_provider_double', 'status': response.status_code, 'response': response.json()})
            with client.app.state.database.connect() as connection:
                assert list(connection.iterdump()) == before
    report = {'is_synthetic': True, 'real_embeddings': True, 'real_chroma': True,
              'real_gpt_called': False, 'business_database_unchanged': True, 'cases': rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print('Three authenticated HTTP checks passed with real local E5/Chroma; GPT was a double.')


if __name__ == '__main__':
    main()
