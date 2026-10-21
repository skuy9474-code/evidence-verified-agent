import json
import unittest
from agent.answer_schema import render_report, report_user
from agent.validation import validate_answer
from agent.targets import normalize_plan, explicit_targets
from eval.cases import record


def answer(cpu=78, status='degraded', memory=61):
    return {'evidence': [{'system_name': 'auth-service', 'status': status,
                          'cpu_percent': cpu, 'memory_percent': memory}],
            'cause': '연결 자원 문제가 원인일 가능성이 있으며 추가 확인이 필요합니다.',
            'actions': ['관련 로그와 매뉴얼을 확인하세요.'],
            'limits': '샘플 데이터이며 실제 원인은 확정할 수 없습니다.'}


class StructuredAnswerTests(unittest.TestCase):
    def test_correct_json_is_readable_and_passes(self):
        draft = render_report(json.dumps(answer()))
        self.assertIn('1) 모니터링 근거', draft)
        self.assertTrue(validate_answer(draft, [record()])['passed'])

    def test_renderer_preserves_wrong_values_so_validator_catches_them(self):
        draft = render_report(json.dumps(answer(cpu=18)))
        self.assertIn('CPU=18.0%', draft)
        report = validate_answer(draft, [record()])
        self.assertFalse(report['passed'])
        self.assertIn('metric_mismatch', [i['code'] for i in report['issues']])

    def test_malformed_missing_and_boolean_answers_are_rejected(self):
        for content in ('not json', '{}', json.dumps(answer(cpu=True))):
            with self.subTest(content=content):
                self.assertFalse(validate_answer(render_report(content), [record()])['passed'])

    def test_unknown_null_is_not_rendered_as_zero(self):
        draft = render_report(json.dumps(answer(cpu=None, memory=None, status='unknown')))
        self.assertIn('CPU=미확인', draft)
        self.assertTrue(validate_answer(draft, [record(status='unknown', cpu=0, memory=0)])['passed'])

    def test_unknown_input_is_not_given_to_model_as_measured_zero(self):
        user = json.loads(report_user('진단', [record(status='unknown', cpu=0, memory=0)]))
        self.assertIsNone(user['collected'][0]['data']['cpu_percent'])

    def test_unknown_target_is_not_replaced_by_auth_service(self):
        raw = {'tasks': [{'agent': 'research', 'target': 'auth-service'}]}
        plan = normalize_plan(raw, 'billing-service 장애를 진단해줘', {'auth-service'})
        self.assertEqual([t['target'] for t in plan['tasks']], ['billing-service'])

    def test_korean_particles_and_multi_systems_are_preserved(self):
        query = 'payments-service와 cache-service를 함께 진단해줘'
        self.assertEqual(explicit_targets(query, {'payments-service', 'cache-service'}),
                         ['payments-service', 'cache-service'])
        plan = normalize_plan({'tasks': []}, query, {'payments-service', 'cache-service'})
        self.assertEqual(len(plan['tasks']), 2)


if __name__ == '__main__':
    unittest.main()
