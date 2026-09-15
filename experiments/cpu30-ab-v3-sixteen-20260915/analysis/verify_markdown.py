"""Check rendered Markdown structure. Requires markdown-it-py in this Python environment."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import re

from markdown_it import MarkdownIt

O = Path(__file__).resolve().parent
P = O.parent
MAIN = P / 'CPU30_COMPLETED_AB_DEEP_ANALYSIS_2026-09-06.md'
paths = [MAIN, P / 'CPU30_PROJECT_PROGRESS_AND_CAPABILITY_REPORT.md',
         P / 'README.md', P / 'CPU30_REPRODUCTION_EVIDENCE_REPORT.md',
         O / 'report_overview.md', O / 'report_synthesis.md',
         O / 'trajectory/trajectory_analysis.md', O / 'trajectory/B_SKILL_USAGE_AUDIT.md']
paths += sorted((O / 'papers').glob('*.md')) + sorted((O / 'ledgers').glob('*.md'))
parser = MarkdownIt('commonmark').enable('table')
results = []
for path in paths:
    text = path.read_text()
    lines = text.splitlines()
    tokens = parser.parse(text)
    counts = Counter(t.type for t in tokens)
    assert ':codex-file-citation{' not in text, path
    previous_heading = 0
    for token in tokens:
        if token.type == 'heading_open':
            level = int(token.tag[1:])
            if previous_heading:
                assert level <= previous_heading + 1, (path, token.map, 'heading skip')
            previous_heading = level
        if token.type == 'fence':
            assert re.fullmatch(r'\s*' + re.escape(token.markup[0]) +
                                '{' + str(len(token.markup)) + r',}\s*',
                                lines[token.map[1] - 1]), (path, token.map, 'unclosed fence')
            if token.info == 'json':
                json.loads(token.content)
        if token.type == 'table_open':
            rows = lines[token.map[0]:token.map[1]]
            widths = [len(re.split(r'(?<!\\)\|', line)) for line in rows]
            assert len(set(widths)) == 1, (path, token.map, 'table width')
        for child in token.children or []:
            if child.type == 'text' and '**' in child.content:
                # Literal Python powers, dictionary unpacking and globs in Judge quotes
                # are explicitly escaped; they are not failed emphasis delimiters.
                assert r'\*\*' in token.content, (path, token.map, child.content)
    if path.parent.name in ('papers', 'ledgers'):
        assert sum(t.type == 'heading_open' and t.tag == 'h1' for t in tokens) == 1, path
    results.append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                    'headings': counts['heading_open'], 'tables': counts['table_open'],
                    'code_blocks': counts['fence']})

main_tokens = parser.parse(MAIN.read_text())
assert sum(t.type == 'blockquote_open' for t in main_tokens) == 3262 * 2
assert sum(t.type == 'inline' and re.fullmatch(
    r'\d{4}\.\d{5} / (midloop|bigloop) / (alg|setup|res)-\d+', t.content)
    is not None for t in main_tokens) == 1631
expected = [r['criterion']['verification'] for r in json.loads((O / 'rubric_ledger.json').read_text())
            if r['condition'] == 'A' and r['criterion'].get('verification')]
actual = [json.loads(t.content) for t in main_tokens if t.type == 'fence' and t.info == 'json']
assert actual == expected, 'Rendered verification specs differ from original criteria'
result = {'status': 'passed', 'parser': 'markdown-it-py (CommonMark + tables)',
          'documents_checked': len(results), 'rubrics': 1631,
          'judge_evidence_and_reason_blocks': 6524, 'verification_json_blocks': len(actual),
          'documents': results}
(O / 'MARKDOWN_FORMAT_VERIFICATION.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k != 'documents'}, ensure_ascii=False, indent=2))
