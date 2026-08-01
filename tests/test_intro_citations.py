from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


extract = load_module(
    "test_extract_workspace_info",
    "skills/reasflow/intro/introduction-framing/scripts/extract-workspace-info.py",
)
writer = load_module(
    "test_write_introduction",
    "skills/reasflow/intro/introduction-framing/scripts/write-introduction.py",
)
hygiene = load_module(
    "test_citation_hygiene",
    "skills/reasflow/shared/citation-hygiene/scripts/check_citation_hygiene.py",
)
llm_client = load_module(
    "test_intro_llm_client",
    "skills/reasflow/intro/introduction-framing/scripts/llm_client.py",
)


class FakeStreamResponse:
    def __init__(self, lines: list[str]) -> None:
        self.lines = [line.encode("utf-8") for line in lines]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def __iter__(self):
        return iter(self.lines)


class LlmClientTests(unittest.TestCase):
    def test_responses_stream_collects_output_text_deltas(self) -> None:
        stream = FakeStreamResponse(
            [
                'event: response.output_text.delta\n',
                'data: {"type":"response.output_text.delta","delta":"hello "}\n',
                'data: {"type":"response.output_text.delta","delta":"world"}\n',
                'data: {"type":"response.completed"}\n',
            ]
        )
        with mock.patch.object(llm_client.urllib.request, "urlopen", return_value=stream):
            text = llm_client.call_text(
                system="system",
                user="user",
                base_url="https://example.test/v1",
                api_key="test-key",
                model="test-model",
                wire_api="responses",
                timeout=1,
                temperature=0.1,
            )

        self.assertEqual(text, "hello world")

    def test_chat_completions_stream_collects_choice_deltas(self) -> None:
        stream = FakeStreamResponse(
            [
                'data: {"choices":[{"delta":{"content":"hello"}}]}\n',
                'data: {"choices":[{"delta":{"content":" chat"}}]}\n',
                'data: [DONE]\n',
            ]
        )
        with mock.patch.object(llm_client.urllib.request, "urlopen", return_value=stream):
            text = llm_client.call_text(
                system="system",
                user="user",
                base_url="https://example.test/v1",
                api_key="test-key",
                model="test-model",
                wire_api="chat_completions",
                timeout=1,
                temperature=0.1,
            )

        self.assertEqual(text, "hello chat")


class ExtractionTests(unittest.TestCase):
    def test_tex_inputs_are_expanded_and_citations_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            child = workspace / "section.tex"
            child.write_text(
                "Prior methods are expensive \\citep{smith2024method}.\n",
                encoding="utf-8",
            )
            main = workspace / "main.tex"
            main.write_text("\\section{Background}\n\\input{section}\n", encoding="utf-8")

            content, error = extract._read_source("main.tex", workspace)

            self.assertIsNone(error)
            self.assertIn("Prior methods are expensive", content)
            self.assertIn("[CITE:smith2024method]", content)
            self.assertNotIn("\\input{section}", content)

    def test_long_content_is_split_without_truncation(self) -> None:
        content = "\n\n".join(f"paragraph-{index}-" + "x" * 80 for index in range(100))
        chunks = extract._split_content(content, 2000)

        self.assertGreater(len(chunks), 1)
        for index in range(100):
            self.assertIn(f"paragraph-{index}-", "\n".join(chunks))

    def test_organize_retains_claim_to_bibtex_mapping(self) -> None:
        survey = {
            "source_type": "survey",
            "source_path": "survey/final_report/main.tex",
            "extracted": {
                "background": {
                    "research_field": "Optimization",
                    "importance": "Important",
                    "applications": ["learning"],
                    "claims": [
                        {
                            "claim": "Existing methods require two communication rounds.",
                            "bibtex_keys": ["smith2024method"],
                            "evidence": "The source states two rounds.",
                        }
                    ],
                },
                "related_works": {
                    "categories": [
                        {
                            "category_name": "Tracking",
                            "description": "Tracking methods use auxiliary variables.",
                            "bibtex_keys": ["smith2024method"],
                            "representative_works": [
                                {
                                    "method_name": "MethodX",
                                    "paper_title": "Method X",
                                    "bibtex_key": "smith2024method",
                                    "key_contribution": "MethodX tracks gradients.",
                                }
                            ],
                        }
                    ]
                },
                "gaps": [
                    {
                        "gap_description": "Existing methods need extra communication.",
                        "impact": "Higher cost",
                        "evidence": "Two exchanges per step.",
                        "bibtex_keys": ["smith2024method"],
                    }
                ],
                "citations": [
                    {
                        "bibtex_key": "smith2024method",
                        "paper_title": "Method X",
                        "authors": "Smith",
                    }
                ],
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            survey_path = temp / "survey.json"
            output_path = temp / "organized.json"
            survey_path.write_text(json.dumps(survey), encoding="utf-8")
            args = argparse.Namespace(inputs=[str(survey_path)], output=str(output_path))
            with contextlib.redirect_stdout(io.StringIO()):
                status = extract.cmd_organize(args)
            organized = json.loads(output_path.read_text(encoding="utf-8"))["organized_info"]

        self.assertEqual(status, 0)
        self.assertIn("bibtex_key: smith2024method", organized["related_works"])
        self.assertIn("[cite: smith2024method]", organized["related_works"])
        self.assertTrue(organized["citation_claims"])
        self.assertTrue(
            all(
                claim["bibtex_keys"] == ["smith2024method"]
                for claim in organized["citation_claims"]
            )
        )


class WriterValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.entry = """@article{smith2024method,
  title={Method X},
  author={Smith, A.},
  year={2024}
}"""
        self.claims = [
            {
                "claim_id": "claim-0001",
                "text": "Existing methods require two communication rounds.",
                "citation_required": True,
                "bibtex_keys": ["smith2024method"],
            }
        ]

    def test_uncited_literature_sentence_fails_validation(self) -> None:
        tex = (
            "\\section{Introduction}\n\n"
            "Existing methods often require two communication rounds, which increases cost."
        )
        report = writer._validate_output(
            tex,
            {"smith2024method": self.entry},
            self.claims,
            {"claims": []},
        )

        self.assertFalse(report["passed"])
        self.assertEqual(len(report["uncited_literature_sentences"]), 1)

    def test_inline_citation_and_valid_trace_pass(self) -> None:
        tex = (
            "\\section{Introduction}\n\n"
            "Existing methods often require two communication rounds, which increases cost "
            "\\citep{smith2024method}."
        )
        report = writer._validate_output(
            tex,
            {"smith2024method": self.entry},
            self.claims,
            {
                "claims": [
                    {
                        "claim_id": "claim-0001",
                        "bibtex_keys": ["smith2024method"],
                    }
                ]
            },
        )

        self.assertTrue(report["passed"], report)

    def test_cited_key_without_trace_provenance_fails(self) -> None:
        tex = "Existing methods often require two rounds \\citep{smith2024method}."

        report = writer._validate_output(
            tex,
            {"smith2024method": self.entry},
            self.claims,
            {"claims": []},
        )

        self.assertFalse(report["passed"])
        self.assertTrue(any("TRACE" in error for error in report["trace_errors"]))

    def test_bibliography_entries_are_parsed_and_cataloged(self) -> None:
        entries = writer._parse_bib_entries(self.entry)

        self.assertEqual(set(entries), {"smith2024method"})
        self.assertIn("smith2024method: Method X", writer._reference_catalog(entries))

    def test_claim_contract_excludes_keys_missing_from_input_bibliography(self) -> None:
        claims = self.claims + [
            {
                "claim_id": "claim-0002",
                "text": "An unavailable source makes another claim.",
                "citation_required": True,
                "bibtex_keys": ["missing2025source"],
            }
        ]

        verified, excluded = writer._verified_citation_claims(
            claims,
            {"smith2024method": self.entry},
        )

        self.assertEqual([claim["claim_id"] for claim in verified], ["claim-0001"])
        self.assertEqual(excluded, ["missing2025source"])


class HygieneTests(unittest.TestCase):
    def test_sentence_level_check_does_not_let_one_citation_cover_a_paragraph(self) -> None:
        tex = (
            "\\section{Introduction}\n\n"
            "Prior methods reduce bandwidth \\citep{smith2024method}. "
            "Existing approaches often retain full-dimensional memory buffers.\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "intro.tex"
            path.write_text(tex, encoding="utf-8")
            findings = hygiene.detect_unsupported_claims([path])

        self.assertEqual(len(findings), 1)
        self.assertIn("retain full-dimensional memory buffers", findings[0]["text"])

    def test_verify_comments_are_unresolved_markers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "intro.tex"
            path.write_text("% [VERIFY: missing support]\nText.\n", encoding="utf-8")
            findings = hygiene.detect_unresolved_markers([path])

        self.assertEqual(len(findings), 1)
        self.assertIn("VERIFY", findings[0]["marker"])


if __name__ == "__main__":
    unittest.main()
