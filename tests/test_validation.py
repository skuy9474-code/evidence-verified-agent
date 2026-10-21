import unittest
from copy import deepcopy
from agent.validation import validate_answer, demo_answer, blocked_answer
from eval.cases import build_cases, record


class ValidationTests(unittest.TestCase):
    def test_synthetic_cases_and_known_format_limitation(self):
        for case in build_cases():
            with self.subTest(case=case['id']):
                expected = case['expected_pass'] and case['id'] != 'legacy_correct_content'
                self.assertEqual(validate_answer(case['draft'], case['collected'])['passed'], expected)

    def test_each_metric_is_bound_to_its_system(self):
        case = next(c for c in build_cases() if c['id'] == 'swapped_system_values')
        report = validate_answer(case['draft'], case['collected'])
        mismatches = [i for i in report['issues'] if i['code'] == 'metric_mismatch']
        self.assertEqual({i['system'] for i in mismatches}, {'auth-service', 'web-01'})

    def test_invalid_source_values_never_pass(self):
        for value in (None, True, float('nan'), float('inf'), -1, 101):
            with self.subTest(value=value):
                collected = [record(cpu=value)]
                report = validate_answer(demo_answer(collected), collected)
                self.assertFalse(report['passed'])
                self.assertIn('invalid_source', [i['code'] for i in report['issues']])

    def test_duplicate_sources_fail_closed(self):
        collected = [record(), record(cpu=55)]
        self.assertFalse(validate_answer(demo_answer(collected), collected)['passed'])

    def test_validator_does_not_change_source(self):
        collected = [record()]
        before = deepcopy(collected)
        validate_answer(demo_answer(collected), collected)
        self.assertEqual(collected, before)

    def test_fallback_never_invents_unknown_measurement(self):
        result = blocked_answer([record('missing-service', 0, 0, 'unknown')])
        self.assertIn('CPU=미확인', result)
        self.assertNotIn('CPU=0%', result)

    def test_correct_repeated_narrative_metric_is_accepted(self):
        facts = [record()]
        self.assertTrue(validate_answer(demo_answer(facts)+'\nauth-service CPU 사용률은 78%입니다.', facts)['passed'])

    def test_wrong_repeated_narrative_metric_is_rejected(self):
        facts = [record()]
        report = validate_answer(demo_answer(facts)+'\nauth-service CPU 사용률은 18%입니다.', facts)
        self.assertFalse(report['passed'])
        self.assertIn('metric_mismatch', [i['code'] for i in report['issues']])

    def test_narrative_multi_system_swaps_are_rejected(self):
        facts = [record(), record('web-01', 34, 48, 'healthy')]
        report = validate_answer(demo_answer(facts)+'\nauth-service CPU=34%, web-01 CPU=78%', facts)
        self.assertEqual(len([i for i in report['issues'] if i['code']=='metric_mismatch']), 2)

    def test_unscoped_multi_system_metric_is_rejected(self):
        facts = [record(), record('web-01', 34, 48, 'healthy')]
        report = validate_answer(demo_answer(facts)+'\nCPU=78%', facts)
        self.assertIn('unscoped_metric', [i['code'] for i in report['issues']])

    def test_sourced_conditional_threshold_is_separate_from_measurement(self):
        facts = [record(), {'source':'runbook', 'data':'CPU가 90%를 넘으면 로그를 확인한다.'}]
        draft = demo_answer(facts)+'\nCPU가 90%를 넘으면 로그를 확인하세요.'
        self.assertTrue(validate_answer(draft, facts)['passed'])
        self.assertFalse(validate_answer(draft, facts[:1])['passed'])

    def test_uncollected_system_metrics_in_narrative_are_rejected(self):
        facts = [record()]
        report = validate_answer(demo_answer(facts)+'\nbilling-service CPU=78%', facts)
        self.assertIn('unsupported_system', [i['code'] for i in report['issues']])

    def test_healthy_named_system_is_not_confused_with_degraded_neighbor(self):
        facts = [record(), record('web-01', 34, 48, 'healthy')]
        self.assertTrue(validate_answer(demo_answer(facts)+'\nweb-01은 정상입니다.', facts)['passed'])

    def test_threshold_does_not_hide_wrong_current_value_on_same_line(self):
        facts = [record(), {'source': 'runbook', 'data': 'CPU가 90%를 넘으면 로그를 확인한다.'}]
        draft = demo_answer(facts)+'\nauth-service CPU는 90%입니다. CPU가 90%를 넘으면 로그를 확인하세요.'
        self.assertIn('metric_mismatch', [i['code'] for i in validate_answer(draft, facts)['issues']])

    def test_threshold_must_match_metric_and_comparison_in_source(self):
        facts = [record(), {'source': 'runbook', 'data': 'CPU가 90%를 넘으면 로그를 확인한다.'}]
        for claim in ('메모리가 90%를 넘으면 로그를 확인하세요.', 'CPU가 90% 이하이면 로그를 확인하세요.'):
            with self.subTest(claim=claim):
                self.assertFalse(validate_answer(demo_answer(facts)+'\n'+claim, facts)['passed'])

    def test_repeated_explicit_status_must_match_source(self):
        facts = [record()]
        for claim in ('auth-service 상태=healthy', 'auth-service 상태는 down입니다.'):
            with self.subTest(claim=claim):
                self.assertIn('status_mismatch', [i['code'] for i in validate_answer(demo_answer(facts)+'\n'+claim, facts)['issues']])
        self.assertTrue(validate_answer(demo_answer(facts)+'\nauth-service 상태는 degraded입니다.', facts)['passed'])

    def test_ambiguous_status_with_multiple_systems_is_blocked(self):
        facts = [record(), record('web-01', 34, 48, 'healthy')]
        self.assertIn('unscoped_status', [i['code'] for i in validate_answer(demo_answer(facts)+'\n상태=healthy', facts)['issues']])


if __name__ == '__main__':
    unittest.main()
