"""Tests only the implemented local scaffold, not LLM/scientific performance."""
from __future__ import annotations
import copy
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from _core import load_json, validate_task, validate_rows, validate_bundle, search_plan


class StarterTests(unittest.TestCase):
    def setUp(self):
        self.task = load_json(ROOT / "examples/minimal-demo/task.json")
        with (ROOT / "examples/minimal-demo/experiments.csv").open(encoding="utf-8", newline="") as f:
            r = csv.DictReader(f)
            self.columns = r.fieldnames
            self.rows = list(r)

    def test_valid_bundle(self):
        result = validate_bundle(ROOT / "examples/minimal-demo/task.json")
        self.assertTrue(result["valid"])
        self.assertEqual(result["n_rows"], 6)
        self.assertEqual(result["scientific_validity"], "not_assessed")

    def test_missing_bounds(self):
        self.task["factors"][0]["bounds"] = [None, None]
        self.assertTrue(validate_task(self.task))

    def test_wrong_unit(self):
        self.task["factors"][1]["unit"] = "ms"
        self.assertTrue(validate_task(self.task))

    def test_nonfinite_value(self):
        self.rows[0]["track_width_um"] = "nan"
        self.assertFalse(validate_rows(self.task, self.rows, self.columns)["valid"])

    def test_out_of_bounds(self):
        self.rows[0]["delay_s"] = "99"
        self.assertFalse(validate_rows(self.task, self.rows, self.columns)["valid"])

    def test_material_pooling(self):
        self.rows[0]["material_pair"] = "DIFFERENT"
        self.assertFalse(validate_rows(self.task, self.rows, self.columns)["valid"])

    def test_source_required(self):
        self.rows[0]["source_ref"] = ""
        self.assertFalse(validate_rows(self.task, self.rows, self.columns)["valid"])

    def test_boolean_budget_rejected(self):
        self.task["budget"]["next_trials"] = True
        self.assertTrue(validate_task(self.task))

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            task = copy.deepcopy(self.task)
            task["dataset_file"] = "../elsewhere.csv"
            p = Path(td) / "task.json"
            p.write_text(json.dumps(task), encoding="utf-8")
            self.assertFalse(validate_bundle(p)["valid"])

    def test_duplicate_record(self):
        self.rows[1]["record_id"] = self.rows[0]["record_id"]
        self.assertFalse(validate_rows(self.task, self.rows, self.columns)["valid"])

    def test_mixed_data_origin(self):
        self.rows[0]["data_kind"] = "measured"
        self.assertFalse(validate_rows(self.task, self.rows, self.columns)["valid"])

    def test_synthetic_not_research(self):
        self.task["mode"] = "research"
        self.assertTrue(validate_task(self.task))

    def test_forbidden_device_permission(self):
        self.task["allow"]["hardware_commands"] = True
        self.assertTrue(validate_task(self.task))

    def test_offline_search_not_execution(self):
        r = search_plan(load_json(ROOT / "registry/seed_candidates.json"), "literature")
        self.assertEqual(len(r["seed_candidates"]), 2)
        self.assertFalse(r["live_search_executed"])
        self.assertIsNone(r["selected_candidate_id"])
        self.assertTrue(all(not c["approved"] for c in r["seed_candidates"]))

    def test_empty_candidate_stage_is_gap(self):
        r = search_plan(load_json(ROOT / "registry/seed_candidates.json"), "measurement")
        self.assertEqual(r["seed_candidates"], [])
        self.assertFalse(r["remote_skill_executed"])

    def test_task_template_intentionally_incomplete(self):
        self.assertTrue(validate_task(load_json(ROOT / "templates/task.json")))

    def test_demo_and_overwrite_protection(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "run"
            cmd = [sys.executable, str(ROOT / "scripts/demo.py"), "--out", str(out)]
            first = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            self.assertEqual(first.returncode, 0, first.stderr)
            state = load_json(out / "run_state.json")
            self.assertEqual(state["status"], "needs_evidence_and_model")
            self.assertIn("optimisation", state["not_executed"])
            second = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            self.assertNotEqual(second.returncode, 0)

if __name__ == "__main__":
    unittest.main()
