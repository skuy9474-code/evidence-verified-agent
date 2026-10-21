"""고정 합성 사례. 모델 생성 품질 평가가 아니라 검증기 오류 탐지 실험이다."""
from copy import deepcopy
from agent.validation import demo_answer


def record(name='auth-service', cpu=78.0, memory=61.0, status='degraded'):
    return {'source': 'monitoring', 'data': {'system_name': name, 'cpu_percent': cpu,
            'memory_percent': memory, 'status': status, 'alerts': []}}


def build_cases():
    one = [record()]
    two = [record(), record('web-01', 34.0, 48.0, 'healthy')]
    unknown = [record('billing-service', 0.0, 0.0, 'unknown')]
    base = demo_answer(one)
    both = demo_answer(two)
    cases = []

    def add(name, facts, answer, valid, category):
        cases.append({'id': name, 'collected': deepcopy(facts), 'draft': answer,
                      'expected_pass': valid, 'category': category})

    add('correct_single', one, base, True, '정상')
    add('correct_multi', two, both, True, '정상')
    add('equivalent_decimal', one, base.replace('CPU=78.0%', 'CPU=78%'), True, '정상')
    add('correct_unknown', unknown, demo_answer(unknown), True, '정상')
    healthy = [record(status='healthy')]
    add('correct_healthy', healthy, demo_answer(healthy), True, '정상')
    add('wrong_cpu', one, base.replace('CPU=78.0%', 'CPU=18.0%'), False, '수치 불일치')
    add('wrong_memory', one, base.replace('메모리=61.0%', '메모리=16.0%'), False, '수치 불일치')
    add('wrong_status', one, base.replace('상태=degraded', '상태=healthy'), False, '상태 불일치')
    swapped = both.replace('CPU=78.0%', 'CPU=TEMP%').replace('CPU=34.0%', 'CPU=78.0%').replace('CPU=TEMP%', 'CPU=34.0%')
    add('swapped_system_values', two, swapped, False, '시스템 간 수치 혼동')
    add('invented_system', one, base.replace('auth-service', 'imaginary-service'), False, '미조회 시스템')
    add('missing_system', two, '\n'.join(l for l in both.splitlines() if not l.startswith('- web-01')), False, '조회 대상 누락')
    add('duplicate_system', one, base.replace('2) 원인 가설', '- auth-service | 상태=degraded | CPU=78.0% | 메모리=61.0%\n\n2) 원인 가설'), False, '중복 근거')
    add('missing_actions', one, base[:base.index('3) 권장 조치')]+base[base.index('4) 한계'):], False, '필수 항목 누락')
    add('empty_limits', one, base[:base.index('4) 한계')]+'4) 한계\n', False, '필수 항목 누락')
    add('unknown_as_zero', unknown, demo_answer(unknown).replace('CPU=미확인', 'CPU=0%'), False, '미확인 수치 단정')
    add('extra_narrative_number', one, base+'\nCPU=10%', False, '근거 밖 수치')
    add('normality_contradiction', one, base.replace('원인은 추가 확인이 필요합니다.', '시스템은 정상입니다. 원인은 추가 확인이 필요합니다.'), False, '정상 단정')
    add('confident_cause', one, base.replace('관측된 상태와 알림에 관련된 자원 또는 의존성 문제가 원인일 가능성이 있습니다. 원인은 추가 확인이 필요합니다.', '장애 원인은 네트워크 단절입니다.'), False, '가설 단정')
    add('no_source', [], base, False, '근거 없음')
    add('bad_row_format', one, base.replace('CPU=78.0%', 'CPU 사용률 약 78%'), False, '해석 불가 표기')
    add('infinite_number', one, base.replace('CPU=78.0%', 'CPU=NaN%'), False, '해석 불가 수치')
    add('short_draft', one, '재시작하세요.', False, '짧은 답변')
    # 기존 자유형 답변도 전용 형식에 맞지 않으면 보류된다. 오탐/호환성 한계를 숨기지 않는다.
    legacy = '1) auth-service 상태는 degraded이고 CPU 78%, 메모리 61%입니다. 2) 원인은 추가 확인이 필요합니다. 3) 로그를 확인하세요. 실제 상태는 미확인입니다.'
    add('legacy_correct_content', one, legacy, True, '정확하지만 자유형 답변')
    return cases
