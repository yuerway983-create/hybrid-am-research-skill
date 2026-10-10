"""Numerical and provenance contracts for the offline foam model, not physical validation."""
from __future__ import annotations

import copy
import csv
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from _core import file_hash, load_json, write_json
from foam_model import (
    InputError, _direction_details, _folds, _inside_hull, _process_analysis, _sensitivity, analyse,
    baseline_predict, error_metrics, feature_value, fit_powerlaw, fit_refinement,
    hierarchy_from_density_eta, load_measurements, model_predict, powerlaw_prediction, run_task, validate_task,
)


DEMO = ROOT / 'examples/foam-refinement-demo/task.json'


def bundle():
    task = load_json(DEMO)
    rows, check = load_measurements(task, DEMO.parent / task['dataset_file'])
    return task, rows, check


def pure_scale_rows(scale='macro', coefficient=.85, exponent=2.2, base=1000.):
    rows = []
    for index, density in enumerate((.25, .35, .5, .7, .85)):
        rows.append({
            'record_id': f'record-{index}', 'sample_id': f'sample-{index}',
            'batch_id': 'fixture-fit', 'condition_id': f'condition-{index}',
            'partition': 'fit', 'scale': scale,
            'total_relative_density': density,
            'eta': 0. if scale == 'macro' else 1.,
            'response_MPa': base * coefficient * density ** exponent,
        })
    return rows


class HierarchyTests(unittest.TestCase):
    def test_density_is_product_of_the_two_scales(self):
        for density in (.1, .4, .9):
            for eta in (0., .25, .5, .75, 1.):
                with self.subTest(density=density, eta=eta):
                    hierarchy = hierarchy_from_density_eta(density, eta)
                    self.assertAlmostEqual(
                        hierarchy['macro_relative_density'] * hierarchy['micro_relative_density'],
                        density,
                    )
                    self.assertAlmostEqual(hierarchy['total_relative_density'], density)
                    self.assertTrue(0 < hierarchy['micro_relative_density'] <= 1)
                    self.assertTrue(0 < hierarchy['macro_relative_density'] <= 1)
                    microscale_void_volume = (
                        (1 - hierarchy['micro_relative_density']) * hierarchy['macro_relative_density']
                    )
                    self.assertAlmostEqual(microscale_void_volume / (1 - density), eta)
                    self.assertAlmostEqual(hierarchy['microscale_porosity_fraction'], eta)

    def test_eta_is_a_void_volume_fraction(self):
        hierarchy = hierarchy_from_density_eta(.4, .5)
        self.assertAlmostEqual(hierarchy['macro_relative_density'], .7)
        self.assertAlmostEqual(hierarchy['micro_relative_density'], 4 / 7)

    def test_solid_limit_keeps_both_densities_equal_to_one(self):
        hierarchy = hierarchy_from_density_eta(1., 0.)
        self.assertEqual(hierarchy['macro_relative_density'], 1.)
        self.assertEqual(hierarchy['micro_relative_density'], 1.)
        for eta in (.5, 1.):
            with self.subTest(eta=eta), self.assertRaises(InputError):
                hierarchy_from_density_eta(1., eta)

    def test_eta_zero_is_pure_macroscale(self):
        hierarchy = hierarchy_from_density_eta(.4, 0.)
        self.assertAlmostEqual(hierarchy['macro_relative_density'], .4)
        self.assertAlmostEqual(hierarchy['micro_relative_density'], 1.)
        self.assertAlmostEqual(hierarchy['microscale_porosity_fraction'], 0.)

    def test_eta_one_is_pure_microscale(self):
        hierarchy = hierarchy_from_density_eta(.4, 1.)
        self.assertAlmostEqual(hierarchy['macro_relative_density'], 1.)
        self.assertAlmostEqual(hierarchy['micro_relative_density'], .4)
        self.assertAlmostEqual(hierarchy['microscale_porosity_fraction'], 1.)

    def test_illegal_density(self):
        for value in (0., -1., 1.1, True, False, float('nan'), float('inf')):
            with self.subTest(value=value), self.assertRaises(InputError):
                hierarchy_from_density_eta(value, .5)

    def test_illegal_eta(self):
        for value in (-.1, 1.1, True, False, float('nan'), float('inf')):
            with self.subTest(value=value), self.assertRaises(InputError):
                hierarchy_from_density_eta(.4, value)

    def test_single_scale_predictions_match_known_power_laws(self):
        micro = {'coefficient': 1., 'exponent': 2.}
        macro = {'coefficient': 1., 'exponent': 3.}
        self.assertAlmostEqual(powerlaw_prediction(.4, 0., 1000., micro, macro), 64.)
        self.assertAlmostEqual(powerlaw_prediction(.4, 1., 1000., micro, macro), 160.)

    def test_two_stage_coefficients_and_exponents_remain_multiplicative(self):
        micro = {'coefficient': .8, 'exponent': 2.}
        macro = {'coefficient': .9, 'exponent': 2.}
        self.assertAlmostEqual(powerlaw_prediction(.4, .5, 1000., micro, macro), 115.2)
        linear = {'coefficient': 1., 'exponent': 1.}
        for eta in (0., .25, .5, .75, 1.):
            with self.subTest(eta=eta):
                self.assertAlmostEqual(powerlaw_prediction(.4, eta, 1000., linear, linear), 400.)

    def test_prediction_parameters_are_positive_finite_numbers(self):
        good = {'coefficient': 1., 'exponent': 2.}
        for field in ('coefficient', 'exponent'):
            for value in (0., -1., True, float('nan'), float('inf')):
                bad = {**good, field: value}
                with self.subTest(field=field, value=value), self.assertRaises(InputError):
                    powerlaw_prediction(.4, .5, 1000., bad, good)
        for value in (0., -1., True, float('nan'), float('inf')):
            with self.subTest(base=value), self.assertRaises(InputError):
                powerlaw_prediction(.4, .5, value, good, good)

    def test_finite_inputs_cannot_produce_overflow_or_underflow_predictions(self):
        ordinary = {'coefficient': 1., 'exponent': 2.}
        enormous = {'coefficient': 1e308, 'exponent': 2.}
        with self.assertRaises(InputError):
            powerlaw_prediction(.4, .5, 1e308, enormous, ordinary)
        with self.assertRaises(InputError):
            powerlaw_prediction(1e-300, .5, 1000., ordinary, ordinary)


class PowerlawFitTests(unittest.TestCase):
    def test_input_errors_are_value_errors(self):
        self.assertTrue(issubclass(InputError, ValueError))

    def test_recovers_coefficient_in_property_units(self):
        for scale in ('macro', 'micro'):
            with self.subTest(scale=scale):
                fitted = fit_powerlaw(pure_scale_rows(scale), 1000., scale, [.1, 2.], [1., 4.])
                self.assertAlmostEqual(fitted['coefficient'], .85, places=6)
                self.assertAlmostEqual(fitted['exponent'], 2.2, places=6)
                predicted = 1000. * fitted['coefficient'] * .5 ** fitted['exponent']
                self.assertAlmostEqual(predicted, 1000. * .85 * .5 ** 2.2, places=6)

    def test_fitted_density_bounds_are_only_from_the_selected_scale(self):
        rows = pure_scale_rows('macro') + pure_scale_rows('micro')
        for row in rows:
            if row['scale'] == 'micro':
                row['total_relative_density'] = .1 + .1 * row['total_relative_density']
        fitted = fit_powerlaw(rows, 1000., 'macro', [.1, 2.], [1., 4.])
        self.assertEqual(fitted['training_density_bounds'], [.25, .85])

    def test_fitted_parameters_respect_prespecified_bounds(self):
        fitted = fit_powerlaw(pure_scale_rows(exponent=4.), 1000., 'macro', [.1, 2.], [1., 2.])
        self.assertTrue(.1 <= fitted['coefficient'] <= 2.)
        self.assertTrue(1. <= fitted['exponent'] <= 2.)

    def test_conditions_have_equal_total_weight(self):
        rows = pure_scale_rows()
        rows[0]['response_MPa'] *= 1.4
        original = fit_powerlaw(rows, 1000., 'macro', [.1, 2.], [1., 4.])
        repeated = copy.deepcopy(rows)
        for index in range(20):
            duplicate = copy.deepcopy(rows[0])
            duplicate['sample_id'] = f'additional-sample-{index}'
            repeated.append(duplicate)
        result = fit_powerlaw(repeated, 1000., 'macro', [.1, 2.], [1., 4.])
        self.assertAlmostEqual(result['coefficient'], original['coefficient'], places=9)
        self.assertAlmostEqual(result['exponent'], original['exponent'], places=9)

    def test_direct_fit_rejects_illegal_response_and_density(self):
        invalid = {
            'total_relative_density': (0., -1., 1.1, True, None, float('nan'), float('inf')),
            'response_MPa': (0., -1., True, None, float('nan'), float('inf')),
        }
        for field, values in invalid.items():
            for value in values:
                rows = pure_scale_rows()
                rows[0][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(InputError):
                    fit_powerlaw(rows, 1000., 'macro', [.1, 2.], [1., 4.])

    def test_direct_fit_rejects_illegal_parameter_bounds(self):
        for index in (0, 1):
            for invalid in (None, [], [1.], [2., 1.], [1., 1.], [0., 2.], [True, 2.], [1., float('inf')]):
                bounds = [[.1, 2.], [1., 4.]]
                bounds[index] = invalid
                with self.subTest(index=index, bounds=invalid), self.assertRaises(InputError):
                    fit_powerlaw(pure_scale_rows(), 1000., 'macro', *bounds)

    def test_direct_fit_rejects_unidentifiable_constant_density(self):
        rows = pure_scale_rows()
        for row in rows:
            row['total_relative_density'] = .5
        with self.assertRaises(InputError):
            fit_powerlaw(rows, 1000., 'macro', [.1, 2.], [1., 4.])

    def test_log_fit_remains_finite_when_property_ratio_would_overflow(self):
        rows = pure_scale_rows()
        for row in rows:
            row['response_MPa'] = 1e200
        fitted = fit_powerlaw(rows, 1e-200, 'macro', [.001, 1000.], [1., 4.])
        self.assertTrue(math.isfinite(fitted['coefficient']))
        self.assertTrue(math.isfinite(fitted['exponent']))
        self.assertGreater(fitted['coefficient'], 0.)


class TaskTests(unittest.TestCase):
    def setUp(self):
        self.task = load_json(DEMO)

    def test_valid_synthetic_task(self):
        validate_task(self.task)

    def test_synthetic_cannot_be_relabelled_as_research(self):
        self.task['mode'] = 'research'
        with self.assertRaises(InputError):
            validate_task(self.task)

    def test_only_supported_compression_observables(self):
        self.task['observable'] = 'energy_absorption'
        self.task['measurement_definition']['quantity'] = 'energy_absorption'
        with self.assertRaises(InputError):
            validate_task(self.task)

    def test_mpa_units_cannot_be_implicitly_converted(self):
        for section, field in (('units', 'response_MPa'), ('measurement_definition', 'unit'), ('base_property', 'unit')):
            task = copy.deepcopy(self.task)
            task[section][field] = 'kPa'
            with self.subTest(section=section), self.assertRaises(InputError):
                validate_task(task)

    def test_base_property_is_a_positive_finite_number(self):
        for value in (0., -1., True, float('nan'), float('inf')):
            task = copy.deepcopy(self.task)
            task['base_property']['value'] = value
            with self.subTest(value=value), self.assertRaises(InputError):
                validate_task(task)

    def test_powerlaw_bounds_are_prespecified_increasing_and_positive(self):
        for field in ('coefficient_bounds', 'exponent_bounds'):
            for bounds in ([], [1.], [2., 1.], [1., 1.], [0., 2.], [True, 2.], [1., float('inf')]):
                task = copy.deepcopy(self.task)
                task['powerlaw'][field] = bounds
                with self.subTest(field=field, bounds=bounds), self.assertRaises(InputError):
                    validate_task(task)

    def test_refinement_uses_at_most_two_explicit_whitelisted_terms(self):
        invalid = (
            [], ['temperature_C ** 2'], ['temperature_C', 'temperature_C'],
            ['temperature_C', 'inverse_scale_ratio', 'porosity_partition_interaction'],
        )
        for features in invalid:
            task = copy.deepcopy(self.task)
            task['refinement']['features'] = features
            with self.subTest(features=features), self.assertRaises(InputError):
                validate_task(task)

    def test_ratio_threshold_and_source_must_be_prespecified(self):
        for field in ('min_wall_to_pore_ratio', 'source_ref'):
            task = copy.deepcopy(self.task)
            task['scale_separation'].pop(field)
            with self.subTest(field=field), self.assertRaises(InputError):
                validate_task(task)

    def test_hardware_and_solver_permissions_are_forbidden(self):
        for field in ('hardware_commands', 'dedicated_simulation_software'):
            task = copy.deepcopy(self.task)
            task['allow'][field] = True
            with self.subTest(field=field), self.assertRaises(InputError):
                validate_task(task)


class MeasurementTests(unittest.TestCase):
    def setUp(self):
        self.task = load_json(DEMO)
        with (DEMO.parent / self.task['dataset_file']).open(encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            self.headers = reader.fieldnames
            self.raw = list(reader)

    def load_modified(self, raw):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'measurements.csv'
            with path.open('w', encoding='utf-8', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=self.headers)
                writer.writeheader()
                writer.writerows(raw)
            return load_measurements(self.task, path)

    def test_technical_repeats_are_sample_means(self):
        rows, check = self.load_modified(self.raw)
        sample_ids = {row['sample_id'] for row in self.raw}
        self.assertEqual(len(rows), len(sample_ids))
        self.assertGreater(len(self.raw), len(rows))
        self.assertEqual(check['raw_records'], len(self.raw))
        self.assertEqual(check['samples'], len(rows))
        for row in rows:
            raw_responses = [float(raw['response_MPa']) for raw in self.raw if raw['sample_id'] == row['sample_id']]
            self.assertAlmostEqual(row['response_MPa'], sum(raw_responses) / len(raw_responses))
            self.assertEqual(row['technical_repeats'], len(raw_responses))
        self.assertFalse(check['independent_batch_or_physical_validity_certified'])

    def test_technical_repeat_count_does_not_shift_fitted_parameters(self):
        rows, _ = self.load_modified(self.raw)
        original = analyse(self.task, rows)
        sample_id = self.raw[0]['sample_id']
        additional = copy.deepcopy([row for row in self.raw if row['sample_id'] == sample_id])
        for index, row in enumerate(additional):
            row['record_id'] = f'extra-technical-repeat-{index}'
        repeated_rows, _ = self.load_modified(self.raw + additional)
        repeated = analyse(self.task, repeated_rows)
        for scale in ('micro', 'macro'):
            for parameter in ('coefficient', 'exponent'):
                self.assertAlmostEqual(original['baseline'][scale][parameter], repeated['baseline'][scale][parameter], places=9)
        self.assertEqual(original['selected_model'], repeated['selected_model'])

    def test_duplicate_record_id_is_rejected(self):
        with self.assertRaises(InputError):
            self.load_modified(self.raw + [copy.deepcopy(self.raw[0])])

    def test_nonfinite_or_nonpositive_measurements_are_rejected(self):
        for value in ('', 'nan', 'inf', '-1', '0'):
            raw = copy.deepcopy(self.raw)
            raw[0]['response_MPa'] = value
            with self.subTest(value=value), self.assertRaises(InputError):
                self.load_modified(raw)

    def test_sample_condition_and_batch_cannot_cross_partitions(self):
        for identity in ('sample_id', 'condition_id', 'batch_id'):
            extra = copy.deepcopy(self.raw[0])
            extra['record_id'] = f'leak-record-{identity}'
            extra['partition'] = 'holdout' if extra['partition'] == 'train' else 'train'
            for other in ('sample_id', 'condition_id', 'batch_id'):
                if other != identity:
                    extra[other] = f'new-{other}-{identity}'
            with self.subTest(identity=identity), self.assertRaises(InputError):
                self.load_modified(self.raw + [extra])

    def test_one_condition_cannot_have_different_settings(self):
        for field in ('temperature_C', 'flow_ratio', 'scale'):
            extra = copy.deepcopy(self.raw[0])
            extra['record_id'] = 'different-settings-record'
            extra['sample_id'] = 'different-settings-sample'
            extra[field] = 'hierarchical' if field == 'scale' else str(float(extra[field]) + 1.)
            with self.subTest(field=field), self.assertRaises(InputError):
                self.load_modified(self.raw + [extra])

    def test_independent_samples_can_have_different_measured_geometry_in_one_condition(self):
        original = next(row for row in self.raw if row['scale'] == 'micro')
        new_sample = copy.deepcopy(original)
        new_sample['sample_id'] = 'independent-geometry-sample'
        new_sample['total_relative_density'] = str((1. + float(original['total_relative_density'])) / 2.)
        new_sample['wall_thickness_um'] = str(float(original['wall_thickness_um']) + 5.)
        new_sample['mean_pore_diameter_um'] = str(float(original['mean_pore_diameter_um']) + 5.)
        additional = []
        for index in range(2):
            repeat = copy.deepcopy(new_sample)
            repeat['record_id'] = f'independent-geometry-repeat-{index}'
            additional.append(repeat)
        rows, check = self.load_modified(self.raw + additional)
        sample = next(row for row in rows if row['sample_id'] == new_sample['sample_id'])
        self.assertEqual(sample['condition_id'], original['condition_id'])
        self.assertEqual(sample['technical_repeats'], 2)
        for field in ('total_relative_density', 'wall_thickness_um', 'mean_pore_diameter_um'):
            self.assertAlmostEqual(sample[field], float(new_sample[field]))
            self.assertNotEqual(sample[field], float(original[field]))
        self.assertEqual(check['samples'], len({row['sample_id'] for row in self.raw}) + 1)

    def test_technical_repeats_cannot_change_sample_settings(self):
        raw = copy.deepcopy(self.raw)
        extra = copy.deepcopy(raw[0])
        extra['record_id'] = 'different-condition-record'
        extra['condition_id'] = 'different-condition'
        with self.assertRaises(InputError):
            self.load_modified(raw + [extra])

    def test_technical_repeats_cannot_change_measured_geometry(self):
        original = next(row for row in self.raw if row['scale'] == 'micro')
        for field in ('total_relative_density', 'wall_thickness_um', 'mean_pore_diameter_um'):
            extra = copy.deepcopy(original)
            extra['record_id'] = f'changed-geometry-repeat-{field}'
            extra[field] = str((1. + float(extra[field])) / 2.) if field == 'total_relative_density' else str(float(extra[field]) + 5.)
            with self.subTest(field=field), self.assertRaises(InputError):
                self.load_modified(self.raw + [extra])

    def test_material_context_and_provenance_must_match_task(self):
        for field in ('material_id', 'context_id', 'data_kind'):
            raw = copy.deepcopy(self.raw)
            raw[0][field] = 'different'
            with self.subTest(field=field), self.assertRaises(InputError):
                self.load_modified(raw)

    def test_source_reference_is_required(self):
        raw = copy.deepcopy(self.raw)
        raw[0]['source_ref'] = ''
        with self.assertRaises(InputError):
            self.load_modified(raw)

    def test_independent_holdout_conditions_are_required(self):
        raw = [row for row in self.raw if row['partition'] == 'train']
        with self.assertRaises(InputError):
            self.load_modified(raw)

    def test_technical_repeats_do_not_replace_independent_conditions(self):
        retained = sorted({row['condition_id'] for row in self.raw if row['scale'] == 'micro' and row['partition'] == 'train'})[:2]
        raw = [row for row in self.raw if row['scale'] != 'micro' or row['partition'] != 'train' or row['condition_id'] in retained]
        with self.assertRaises(InputError):
            self.load_modified(raw)


class AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.task, cls.rows, cls.check = bundle()
        cls.report = analyse(cls.task, cls.rows)

    def test_holdout_responses_cannot_train_or_select_models(self):
        rows = copy.deepcopy(self.rows)
        for row in rows:
            if row['partition'] == 'holdout':
                row['response_MPa'] *= 100.
        changed = analyse(self.task, rows)
        self.assertEqual(changed['baseline'], self.report['baseline'])
        self.assertEqual(changed['selected_model'], self.report['selected_model'])
        self.assertEqual(changed['selection_sha256'], self.report['selection_sha256'])
        self.assertEqual(changed['training_domain'], self.report['training_domain'])
        for name, model in self.report['models'].items():
            self.assertEqual(changed['models'][name]['available'], model['available'])
            if model['available']:
                self.assertEqual(changed['models'][name]['state'], model['state'])
                self.assertEqual(changed['models'][name]['cv'], model['cv'])
        self.assertEqual(changed['process_model']['state'], self.report['process_model']['state'])
        self.assertEqual(changed['process_model']['cv'], self.report['process_model']['cv'])
        self.assertNotEqual(
            changed['models'][changed['selected_model']]['holdout'],
            self.report['models'][self.report['selected_model']]['holdout'],
        )

    def test_holdout_density_cannot_expand_the_training_domain(self):
        rows = copy.deepcopy(self.rows)
        train = [row for row in rows if row['partition'] == 'train' and row['scale'] == 'hierarchical']
        outside_density = (1. + max(row['total_relative_density'] for row in train)) / 2.
        for row in rows:
            if row['partition'] == 'holdout' and row['scale'] == 'hierarchical':
                row.update(hierarchy_from_density_eta(outside_density, row['microscale_porosity_fraction']))
        changed = analyse(self.task, rows)
        self.assertEqual(changed['training_domain'], self.report['training_domain'])
        self.assertEqual(changed['selected_model'], self.report['selected_model'])
        self.assertEqual(changed['selection_sha256'], self.report['selection_sha256'])
        self.assertFalse(changed['numerical_checks']['density_eta_domain'])

    def test_demo_hierarchical_densities_are_within_both_monoscale_calibration_domains(self):
        hierarchical = {row['sample_id']: row for row in self.rows if row['scale'] == 'hierarchical'}
        self.assertTrue(self.report['numerical_checks']['monoscale_density_domain'])
        self.assertTrue(self.report['numerical_checks']['hierarchical_within_monoscale_calibration_domain'])
        for scale in ('micro', 'macro'):
            checks = self.report['baseline_validation'][scale]['hierarchical_calibration_transfer']
            self.assertCountEqual([check['sample_id'] for check in checks], list(hierarchical))
            for check in checks:
                row = hierarchical[check['sample_id']]
                self.assertAlmostEqual(check['relative_density'], row[f'{scale}_relative_density'])
                self.assertTrue(check['inside_training_density_range'])

    def test_hierarchical_density_outside_macro_calibration_still_has_diagnostic_predictions(self):
        rows = copy.deepcopy(self.rows)
        macro_train = [row for row in rows if row['scale'] == 'macro' and row['partition'] == 'train']
        lower = min(row['total_relative_density'] for row in macro_train)
        upper = max(row['total_relative_density'] for row in macro_train)
        for row in rows:
            if row['scale'] == 'macro':
                compressed = .47 + .06 * (row['total_relative_density'] - lower) / (upper - lower)
                row.update(hierarchy_from_density_eta(compressed, 0.))
        changed = analyse(self.task, rows)
        self.assertTrue(changed['prediction_performed'])
        self.assertTrue(changed['numerical_checks']['monoscale_density_domain'])
        self.assertFalse(changed['numerical_checks']['hierarchical_within_monoscale_calibration_domain'])
        self.assertFalse(changed['numerical_gates_passed'])
        self.assertEqual(changed['training_domain'], self.report['training_domain'])
        macro = changed['baseline_validation']['macro']
        self.assertAlmostEqual(macro['training_density_bounds'][0], .47)
        self.assertAlmostEqual(macro['training_density_bounds'][1], .53)
        hierarchical = {row['sample_id']: row for row in rows if row['scale'] == 'hierarchical'}
        checks = macro['hierarchical_calibration_transfer']
        self.assertCountEqual([check['sample_id'] for check in checks], list(hierarchical))
        self.assertTrue(any(not check['inside_training_density_range'] for check in checks))
        for check in checks:
            row = hierarchical[check['sample_id']]
            self.assertAlmostEqual(check['relative_density'], row['macro_relative_density'])
            expected = .47 - 1e-10 <= row['macro_relative_density'] <= .53 + 1e-10
            self.assertEqual(check['inside_training_density_range'], expected)
        self.assertTrue(changed['predictions'])
        self.assertTrue(all(math.isfinite(row['predicted_MPa']) and row['predicted_MPa'] > 0. for row in changed['predictions']))

    def test_micro_calibration_extrapolation_also_fails_hierarchical_transfer_gate(self):
        rows = copy.deepcopy(self.rows)
        micro_train = [row for row in rows if row['scale'] == 'micro' and row['partition'] == 'train']
        lower = min(row['total_relative_density'] for row in micro_train)
        upper = max(row['total_relative_density'] for row in micro_train)
        for row in rows:
            if row['scale'] == 'micro':
                compressed = .47 + .06 * (row['total_relative_density'] - lower) / (upper - lower)
                row.update(hierarchy_from_density_eta(compressed, 1.))
        changed = analyse(self.task, rows)
        self.assertTrue(changed['prediction_performed'])
        self.assertTrue(changed['numerical_checks']['monoscale_density_domain'])
        self.assertFalse(changed['numerical_checks']['hierarchical_within_monoscale_calibration_domain'])
        self.assertFalse(changed['numerical_gates_passed'])
        self.assertTrue(any(not item['inside_training_density_range'] for item in changed['baseline_validation']['micro']['hierarchical_calibration_transfer']))
        self.assertTrue(all(item['inside_training_density_range'] for item in changed['baseline_validation']['macro']['hierarchical_calibration_transfer']))
        self.assertTrue(changed['predictions'])

    def test_leave_one_condition_folds_have_no_condition_overlap(self):
        train = [row for row in self.rows if row['partition'] == 'train' and row['scale'] == 'hierarchical']
        validation_samples = []
        for fit, validation in _folds(train):
            self.assertEqual(len({row['condition_id'] for row in validation}), 1)
            self.assertFalse({row['condition_id'] for row in fit} & {row['condition_id'] for row in validation})
            validation_samples.extend(row['sample_id'] for row in validation)
        self.assertCountEqual(validation_samples, [row['sample_id'] for row in train])

    def test_error_metrics_have_equal_condition_weight(self):
        rows = [{'condition_id': identity, 'response_MPa': 1.} for identity in ('A', 'A', 'A', 'B')]
        metrics = error_metrics(rows, [3., 3., 3., 5.])
        self.assertAlmostEqual(metrics['mae'], 3.)
        self.assertAlmostEqual(metrics['rmse'], math.sqrt(10.))

    def test_error_metrics_reject_nonfinite_or_nonvector_values(self):
        valid = [{'condition_id': 'A', 'response_MPa': 1.}, {'condition_id': 'B', 'response_MPa': 2.}]
        for predictions in ([1.], [[1.], [2.]], 1., [float('nan'), 2.], [1., float('inf')]):
            with self.subTest(predictions=predictions), self.assertRaises(InputError):
                error_metrics(valid, predictions)
        for value in (float('nan'), float('inf'), [1.]):
            rows = copy.deepcopy(valid)
            rows[0]['response_MPa'] = value
            if isinstance(value, list):
                rows[1]['response_MPa'] = [2.]
            with self.subTest(actual=value), self.assertRaises(InputError):
                error_metrics(rows, [1., 2.])
        with self.assertRaises(InputError):
            error_metrics([], [])

    def test_error_metrics_reject_finite_inputs_that_overflow_error(self):
        for actual, predicted in ((-1e308, 1e308), (1e200, 2e200)):
            with self.subTest(actual=actual, predicted=predicted), self.assertRaises(InputError):
                error_metrics([{'condition_id': 'A', 'response_MPa': actual}], [predicted])

    def test_cv_and_holdout_errors_are_finite(self):
        for name, model in self.report['models'].items():
            if model['available']:
                for partition in ('cv', 'holdout'):
                    for metric in ('rmse', 'mae'):
                        with self.subTest(model=name, partition=partition, metric=metric):
                            self.assertTrue(math.isfinite(model[partition][metric]))
                            self.assertGreaterEqual(model[partition][metric], 0.)
        for scale in ('macro', 'micro'):
            for partition in ('cv', 'holdout'):
                self.assertTrue(math.isfinite(self.report['baseline_validation'][scale][partition]['rmse']))
        json.dumps(self.report, allow_nan=False)

    def test_process_density_response_surface_has_finite_independent_errors(self):
        process = self.report['process_model']
        self.assertTrue(process['available'], process.get('reason'))
        for partition in ('cv', 'holdout'):
            for metric in ('rmse', 'mae'):
                self.assertTrue(math.isfinite(process[partition][metric]))
                self.assertGreaterEqual(process[partition][metric], 0.)
        self.assertFalse(process['causal_interpretation'])
        self.assertFalse(process['is_physical_foaming_simulation'])

    def test_process_model_holdout_cannot_set_training_geometry_or_domain(self):
        rows = copy.deepcopy(self.rows)
        temperature = max(row['temperature_C'] for row in rows if row['scale'] == 'micro' and row['partition'] == 'train') + 20.
        for row in rows:
            if row['scale'] == 'micro' and row['partition'] == 'holdout':
                row.update(hierarchy_from_density_eta(.95, 1.))
                row['temperature_C'] = temperature
        changed = analyse(self.task, rows)
        process, original = changed['process_model'], self.report['process_model']
        self.assertTrue(process['available'], process.get('reason'))
        self.assertEqual(process['state'], original['state'])
        self.assertEqual(process['cv'], original['cv'])
        self.assertEqual(process['training_domain_points'], original['training_domain_points'])
        self.assertTrue(all(not supported for supported in process['holdout_inside_training_domain']))
        self.assertEqual(changed['baseline'], self.report['baseline'])
        self.assertEqual(changed['selection_sha256'], self.report['selection_sha256'])

    def test_scale_ratio_check_does_not_certify_physical_validity(self):
        task = copy.deepcopy(self.task)
        task['scale_separation']['min_wall_to_pore_ratio'] = 1e9
        report = analyse(task, self.rows)
        self.assertFalse(report['scale_separation']['declared_ratio_checks_passed'])
        self.assertTrue(report['scale_separation']['mean_pore_ratio_is_not_proof_of_continuum_validity'])
        self.assertFalse(report['physical_validation_performed'])

    def test_synthetic_calculation_is_not_an_experiment_or_llm_gain(self):
        self.assertEqual(self.report['data_kind'], 'synthetic_demo')
        self.assertEqual(self.report['mode'], 'offline_demo')
        for flag in ('physical_validation_performed', 'fresh_confirmation_performed', 'llm_called_by_script',
                     'dedicated_simulation_software_called', 'hardware_commands_sent'):
            self.assertFalse(self.report[flag], flag)
        self.assertTrue(self.report['selection_frozen_before_holdout'])

    def test_decision_summary_is_consistent_and_never_confirms_physical_gain(self):
        summary = self.report['decision_summary']
        self.assertEqual(summary['mechanical_status'], 'passed' if self.report['numerical_gates_passed'] else 'failed')
        process = self.report['process_model']
        expected_process = 'unavailable' if not process['available'] else 'passed' if process['numerical_gates_passed'] else 'failed'
        self.assertEqual(summary['process_density_status'], expected_process)
        self.assertEqual(summary['scale_assumption_status'], 'needs_review')
        self.assertEqual(summary['failed_numerical_checks'], [name for name, passed in self.report['numerical_checks'].items() if not passed])
        self.assertTrue(summary['priority_actions'])
        self.assertTrue(all(isinstance(action, str) and action.strip() for action in summary['priority_actions']))
        self.assertFalse(summary['physical_improvement_confirmed'])

    def test_decision_summary_distinguishes_failed_ratio_from_review_status(self):
        task = copy.deepcopy(self.task)
        task['scale_separation']['review_status'] = 'reviewed'
        reviewed = analyse(task, self.rows)
        self.assertEqual(reviewed['decision_summary']['scale_assumption_status'], 'reviewed')
        self.assertFalse(reviewed['decision_summary']['physical_improvement_confirmed'])
        task['scale_separation']['min_wall_to_pore_ratio'] = 1e9
        failed = analyse(task, self.rows)
        self.assertEqual(failed['decision_summary']['scale_assumption_status'], 'ratio_failed')
        self.assertFalse(failed['decision_summary']['physical_improvement_confirmed'])

    def test_decision_summary_identifies_failed_mechanical_checks(self):
        rows = copy.deepcopy(self.rows)
        for row in rows:
            if row['partition'] == 'holdout' and row['scale'] == 'hierarchical':
                row['response_MPa'] *= 100.
        report = analyse(self.task, rows)
        summary = report['decision_summary']
        self.assertEqual(summary['mechanical_status'], 'failed')
        self.assertIn('holdout_error', summary['failed_numerical_checks'])
        self.assertFalse(summary['physical_improvement_confirmed'])

    def test_decision_summary_reports_unavailable_process_density_model(self):
        rows = copy.deepcopy(self.rows)
        for row in rows:
            if row['scale'] == 'micro':
                row['flow_ratio'] = .7
        report = analyse(self.task, rows)
        self.assertFalse(report['process_model']['available'])
        self.assertEqual(report['decision_summary']['process_density_status'], 'unavailable')
        self.assertTrue(report['decision_summary']['priority_actions'])


class SensitivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.task, cls.rows, _ = bundle()
        cls.report = analyse(cls.task, cls.rows)

    def test_direction_is_a_sampled_trend_not_an_endpoint_comparison(self):
        cases = (
            ([1., 2., 3.], 'increasing'),
            ([3., 2., 1.], 'decreasing'),
            ([2., 2., 2.], 'flat'),
            ([1., 4., 2.], 'non_monotonic'),
        )
        for predictions, expected in cases:
            with self.subTest(predictions=predictions):
                detail = _direction_details([.2, .5, .8], predictions)
                self.assertEqual(detail['direction'], expected)
                self.assertEqual(detail['endpoint_predictions'], [
                    {'input_value': .2, 'predicted_value': predictions[0]},
                    {'input_value': .8, 'predicted_value': predictions[-1]},
                ])
        for inputs in ([], [.2], [.2, .2]):
            with self.subTest(inputs=inputs), self.assertRaises(InputError):
                _direction_details(inputs, [1.] * len(inputs))

    def assert_supported_endpoints(self, effects, baseline, state, training):
        features = state['feature_names'] if state else []
        bounds = {name: [min(feature_value(row, name) for row in training), max(feature_value(row, name) for row in training)] for name in features}
        points = [[row['total_relative_density'], row['microscale_porosity_fraction']] for row in training]
        for item in effects:
            self.assertGreaterEqual(item['sampled_points_count'], 0)
            if not item['available']:
                for unsupported_field in ('response_span_MPa', 'direction', 'endpoint_predictions', 'sampled_supported_range'):
                    self.assertNotIn(unsupported_field, item)
                self.assertTrue(item['reason'])
                continue
            self.assertGreaterEqual(item['sampled_points_count'], 2)
            self.assertIn(item['direction'], {'increasing', 'decreasing', 'non_monotonic', 'flat'})
            endpoints = item['endpoint_predictions']
            self.assertEqual(len(endpoints), 2)
            self.assertEqual([point['input_value'] for point in endpoints], item['sampled_supported_range'])
            self.assertLess(endpoints[0]['input_value'], endpoints[1]['input_value'])
            for point in endpoints:
                row = {**item['fixed_reference'], item['factor']: point['input_value']}
                density = hierarchy_from_density_eta(row['total_relative_density'], row['microscale_porosity_fraction'])
                self.assertTrue(_inside_hull(points, [row['total_relative_density'], row['microscale_porosity_fraction']]))
                for scale in ('micro', 'macro'):
                    lower, upper = baseline[scale]['training_density_bounds']
                    self.assertGreaterEqual(density[f'{scale}_relative_density'], lower - 1e-10)
                    self.assertLessEqual(density[f'{scale}_relative_density'], upper + 1e-10)
                for name, (lower, upper) in bounds.items():
                    self.assertGreaterEqual(feature_value(row, name), lower - 1e-10)
                    self.assertLessEqual(feature_value(row, name), upper + 1e-10)
                self.assertTrue(math.isfinite(point['predicted_value']))
                self.assertGreater(point['predicted_value'], 0.)
                self.assertAlmostEqual(point['predicted_value'], model_predict([row], baseline, state)[0])

    def test_mechanical_sensitivity_endpoints_have_all_calibration_support(self):
        training = [row for row in self.rows if row['scale'] == 'hierarchical' and row['partition'] == 'train']
        state = self.report['models'][self.report['selected_model']]['state']
        self.assert_supported_endpoints(self.report['sensitivity'], self.report['baseline'], state, training)

    def test_mechanical_sensitivity_excludes_monoscale_extrapolation(self):
        training = [row for row in self.rows if row['scale'] == 'hierarchical' and row['partition'] == 'train']
        baseline = copy.deepcopy(self.report['baseline'])
        baseline['macro']['training_density_bounds'] = [.47, .53]
        effects = _sensitivity(training, baseline, None)
        self.assert_supported_endpoints(effects, baseline, None, training)
        self.assertTrue(any(item['sampled_points_count'] < 31 for item in effects))
        density_effect = next(item for item in effects if item['factor'] == 'total_relative_density')
        self.assertTrue(density_effect['available'])
        self.assertNotEqual(density_effect['sampled_supported_range'], density_effect['declared_training_range'])

    def test_nonlinear_refinement_feature_can_exclude_a_mean_reference(self):
        baseline = copy.deepcopy(self.report['baseline'])
        for scale in ('micro', 'macro'):
            baseline[scale]['training_density_bounds'] = [.01, 1.]
        reference = next(row for row in self.rows if row['scale'] == 'hierarchical' and row['partition'] == 'train')
        training = []
        for density in (.3, .5):
            for eta in (.10, .11, .89, .90):
                row = copy.deepcopy(reference)
                row['condition_id'] = f'feature-support-{density}-{eta}'
                row.update(hierarchy_from_density_eta(density, eta))
                row['response_MPa'] = baseline_predict(row, baseline)
                training.append(row)
        state = fit_refinement(training, baseline, ['porosity_partition_interaction'], .01)
        effects = _sensitivity(training, baseline, state)
        density_effect = next(item for item in effects if item['factor'] == 'total_relative_density')
        self.assertFalse(density_effect['available'])
        self.assertEqual(density_effect['sampled_points_count'], 0)
        self.assertAlmostEqual(density_effect['fixed_reference']['microscale_porosity_fraction'], .5)
        self.assert_supported_endpoints(effects, baseline, state, training)

    def test_sensitivity_skips_invalid_generated_scenarios_with_a_legal_solid_training_point(self):
        baseline = copy.deepcopy(self.report['baseline'])
        for scale in ('micro', 'macro'):
            baseline[scale]['training_density_bounds'] = [.1, 1.]
        reference = next(row for row in self.rows if row['scale'] == 'hierarchical' and row['partition'] == 'train')
        training = []
        for index, (density, eta) in enumerate(((.2, .2), (.5, .5), (1., 0.))):
            row = copy.deepcopy(reference)
            row['condition_id'] = f'solid-support-{index}'
            row.update(hierarchy_from_density_eta(density, eta))
            row['response_MPa'] = baseline_predict(row, baseline)
            training.append(row)
        effects = _sensitivity(training, baseline, None)
        self.assertCountEqual([item['factor'] for item in effects], ['total_relative_density', 'microscale_porosity_fraction'])
        self.assert_supported_endpoints(effects, baseline, None, training)
        for item in effects:
            if item['available'] and item['factor'] == 'total_relative_density':
                self.assertLess(item['sampled_supported_range'][1], 1.)

    def test_process_sensitivity_gives_directions_and_supported_endpoints(self):
        effects = {item['factor']: item for item in self.report['process_model']['sensitivity']}
        self.assertEqual(effects['temperature_C']['direction'], 'decreasing')
        self.assertEqual(effects['flow_ratio']['direction'], 'increasing')
        for item in effects.values():
            self.assertTrue(item['available'])
            self.assertGreaterEqual(item['sampled_points_count'], 2)
            self.assertEqual([point['input_value'] for point in item['endpoint_predictions']], item['sampled_supported_range'])
            for point in item['endpoint_predictions']:
                self.assertTrue(0. < point['predicted_value'] < 1.)

    def test_process_sensitivity_with_one_supported_grid_point_is_unavailable(self):
        reference = next(row for row in self.rows if row['scale'] == 'micro' and row['partition'] == 'train')
        rows = []
        settings = [(100., .1), (100.001, .1), (200., .2), (200.001, .2), (150.0005, .15), (160.0005, .16)]
        for index, (temperature, flow) in enumerate(settings):
            row = copy.deepcopy(reference)
            row.update(condition_id=f'narrow-domain-{index}', partition='train' if index < 4 else 'holdout',
                       temperature_C=temperature, flow_ratio=flow)
            density = 1. / (1. + math.exp(-(.5 + .01 * (temperature - 150.) + flow)))
            row.update(hierarchy_from_density_eta(density, 1.))
            rows.append(row)
        process = _process_analysis(rows, self.task['process_model'])
        self.assertTrue(process['available'], process.get('reason'))
        for item in process['sensitivity']:
            self.assertFalse(item['available'])
            self.assertEqual(item['sampled_points_count'], 1)
            self.assertTrue(item['reason'])
            for unsupported_field in ('density_span', 'direction', 'endpoint_predictions', 'sampled_supported_range'):
                self.assertNotIn(unsupported_field, item)


class RunTests(unittest.TestCase):
    def test_end_to_end_artifacts_and_existing_output_protection(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary) / 'run'
            report = run_task(DEMO, out)
            self.assertTrue(report['prediction_performed'], report.get('errors'))
            for name in ('result.json', 'model.json', 'report.md', 'input_task.json', 'input_measurements.csv'):
                self.assertTrue((out / name).is_file(), name)
            before = {path.name: path.read_bytes() for path in out.iterdir() if path.is_file()}
            with self.assertRaises(InputError):
                run_task(DEMO, out)
            after = {path.name: path.read_bytes() for path in out.iterdir() if path.is_file()}
            self.assertEqual(before, after)
            frozen = load_json(out / 'model.json')
            self.assertEqual(frozen['selection_sha256'], report['selection_sha256'])
            self.assertEqual(frozen['data_kind'], 'synthetic_demo')
            self.assertEqual(frozen['source_hashes'], report['source_hashes'])
            for name, digest in report['source_hashes'].items():
                self.assertEqual(digest, file_hash(ROOT / 'scripts' / name))

    def test_data_path_cannot_escape_task_directory(self):
        for relative in ('../outside.csv', str((DEMO.parent / 'outside.csv').resolve())):
            with self.subTest(path=relative), tempfile.TemporaryDirectory() as temporary:
                task = load_json(DEMO)
                task['dataset_file'] = relative
                task_path = Path(temporary) / 'task.json'
                write_json(task_path, task)
                out = Path(temporary) / 'run'
                report = run_task(task_path, out)
                self.assertFalse(report['prediction_performed'])
                self.assertFalse((out / 'model.json').exists())
                self.assertEqual(report['status'], 'blocked')

    def test_local_cli_uses_the_same_synthetic_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary) / 'run'
            process = subprocess.run(
                [sys.executable, str(ROOT / 'scripts/foam_model.py'), 'run', '--task', str(DEMO), '--out', str(out)],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            report = load_json(out / 'result.json')
            self.assertEqual(report['data_kind'], 'synthetic_demo')
            self.assertFalse(report['physical_validation_performed'])

    def test_invalid_cli_input_blocks_without_frozen_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = load_json(DEMO)
            task['dataset_file'] = 'missing.csv'
            task_path = Path(temporary) / 'task.json'
            write_json(task_path, task)
            out = Path(temporary) / 'run'
            process = subprocess.run(
                [sys.executable, str(ROOT / 'scripts/foam_model.py'), 'run', '--task', str(task_path), '--out', str(out)],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(process.returncode, 2, process.stderr)
            self.assertFalse(load_json(out / 'result.json')['prediction_performed'])
            self.assertFalse((out / 'model.json').exists())

    def test_input_snapshots_are_the_analyzed_and_hashed_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task_path = root / 'task.json'
            dataset_path = root / 'measurements.csv'
            task_bytes = DEMO.read_bytes()
            dataset_bytes = (DEMO.parent / 'measurements.csv').read_bytes()
            task_path.write_bytes(task_bytes)
            dataset_path.write_bytes(dataset_bytes)
            out = root / 'run'

            def analyse_and_change_original(task, rows):
                report = analyse(task, rows)
                changed_task = copy.deepcopy(task)
                changed_task['base_property']['value'] *= 2.
                write_json(task_path, changed_task)
                dataset_path.write_bytes(dataset_bytes + b'\n')
                return report

            with mock.patch('foam_model.analyse', side_effect=analyse_and_change_original), \
                 mock.patch('foam_model.load_measurements', wraps=load_measurements) as loader:
                report = run_task(task_path, out)
            self.assertTrue(report['prediction_performed'], report.get('errors'))
            self.assertEqual(Path(loader.call_args.args[1]).resolve(), (out / 'input_measurements.csv').resolve())
            self.assertEqual((out / 'input_task.json').read_bytes(), task_bytes)
            self.assertEqual((out / 'input_measurements.csv').read_bytes(), dataset_bytes)
            self.assertEqual(report['input_hashes']['task_sha256'], file_hash(out / 'input_task.json'))
            self.assertEqual(report['input_hashes']['dataset_sha256'], file_hash(out / 'input_measurements.csv'))
            self.assertNotEqual(report['input_hashes']['task_sha256'], file_hash(task_path))
            self.assertNotEqual(report['input_hashes']['dataset_sha256'], file_hash(dataset_path))
            self.assertEqual(load_json(out / 'model.json')['input_hashes'], report['input_hashes'])

    def test_empty_research_template_blocks_without_fabricating_a_model(self):
        template = ROOT / 'templates/foam-research/task.json'
        self.assertTrue(template.is_file())
        task = load_json(template)
        self.assertEqual(task['mode'], 'research')
        self.assertEqual(task['data_kind'], 'measured')
        self.assertIsNone(task['base_property']['value'])
        with (template.parent / task['dataset_file']).open(encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            self.assertTrue(reader.fieldnames)
            self.assertEqual(list(reader), [])
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary) / 'run'
            report = run_task(template, out)
            self.assertEqual(report['status'], 'blocked')
            self.assertFalse(report['prediction_performed'])
            self.assertTrue(report['errors'])
            self.assertFalse((out / 'model.json').exists())
            self.assertFalse(load_json(out / 'result.json')['prediction_performed'])


if __name__ == '__main__':
    unittest.main()
