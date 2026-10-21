"""같은 합성 답변 묶음에 기존 검증과 개선 검증을 적용해 실측한다."""
import csv
import json
from pathlib import Path
from time import perf_counter
from eval.cases import build_cases
from agent.validation import validate_answer


def baseline(draft):
    # 제공된 graph.py의 최초 검증 조건을 그대로 보존한다.
    # 기존의 3회 강제 통과 동작은 이 단일 답변 실험에 포함하지 않는다.
    return len(draft) >= 30 and '1)' in draft


def metrics(rows, key):
    invalid = [r for r in rows if not r['expected_pass']]
    valid = [r for r in rows if r['expected_pass']]
    tp = sum(not r[key] for r in invalid)
    fp = sum(not r[key] for r in valid)
    return {'total': len(rows), 'invalid': len(invalid), 'valid': len(valid),
            'errors_detected': tp, 'errors_missed': len(invalid)-tp,
            'correct_rejected': fp, 'correct_accepted': len(valid)-fp,
            'detection_rate': tp/len(invalid),
            'false_rejection_rate': fp/len(valid),
            'accuracy': sum(r[key] == r['expected_pass'] for r in rows)/len(rows)}


def main():
    rows = []
    elapsed = {'before': [], 'after': []}
    for case in build_cases():
        # 작은 함수 지연의 잡음을 줄이기 위해 고정 입력을 100번씩 반복해 평균을 구한다.
        start = perf_counter()
        for _ in range(100):
            old = baseline(case['draft'])
        elapsed['before'].append((perf_counter()-start)*1000/100)
        start = perf_counter()
        for _ in range(100):
            report = validate_answer(case['draft'], case['collected'])
        elapsed['after'].append((perf_counter()-start)*1000/100)
        rows.append({'id': case['id'], 'category': case['category'],
                     'expected_pass': case['expected_pass'], 'before_pass': old,
                     'after_pass': report['passed'],
                     'issues': [i['code'] for i in report['issues']]})
    summary = {key: metrics(rows, field) for key, field in [('before', 'before_pass'), ('after', 'after_pass')]}
    for key in elapsed:
        summary[key]['mean_validation_ms'] = sum(elapsed[key])/len(elapsed[key])
    summary['method'] = ('23 fixed synthetic drafts; no LLM calls; same input per validator; '
                         'includes one semantically correct legacy-format draft rejected by the strict contract; '
                         'latency is local validation only, 100 repetitions per case')
    out = Path(__file__).resolve().parents[1]/'reports'
    out.mkdir(exist_ok=True)
    (out/'evaluation.json').write_text(json.dumps({'summary': summary, 'cases': rows}, ensure_ascii=False, indent=2))
    with (out/'evaluation.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({**r, 'issues': ', '.join(r['issues'])} for r in rows)
    lines = ['# 검증기 Before / After 실험', '',
             '고정 합성 답변 23개를 동일하게 입력했습니다. 실제 LLM 생성 품질이나 운영 정확도 결과가 아닙니다.', '',
             '| 지표 | 기존 | 개선 |', '|---|---:|---:|']
    for label, key in [('잘못된 답변 탐지', 'errors_detected'), ('오류 답변 통과', 'errors_missed'),
                       ('정확한 답변 보류', 'correct_rejected')]:
        lines.append(f"| {label} | {summary['before'][key]} | {summary['after'][key]} |")
    for label, key in [('오류 탐지율', 'detection_rate'), ('정답 보류율', 'false_rejection_rate')]:
        lines.append(f"| {label} | {summary['before'][key]:.1%} | {summary['after'][key]:.1%} |")
    lines += ['', '## 실험 범위와 한계', '',
              '- 정답 6개, 오류 17개인 소규모 수동 합성 사례입니다. 검증 규칙을 알고 만든 사례라 일반화 성능으로 해석할 수 없습니다.',
              '- 정확한 자유형 답변 1개도 정형 출력 계약에 맞지 않아 개선본에서 보류됩니다. 형식 제약의 비용입니다.',
              '- 기존 검증의 3회 후 강제 통과는 단일 답변 비교에서 제외했습니다. 그래프 테스트에서 별도로 확인합니다.',
              '- 지연은 함수만 측정한 로컬 평균입니다. 모델 호출, MCP, 재작성, 네트워크 지연은 포함하지 않습니다.',
              '- 현재는 규칙 검증입니다. 원인·조치의 의미적 정확성 전체, 매뉴얼 내용의 신뢰성, 실제 서버 상태를 보증하지 않습니다.', '',
              '## 사례별 결과', '', '| 사례 | 기대 | 기존 | 개선 | 사유 |', '|---|---|---|---|---|']
    for r in rows:
        label = lambda value: '통과' if value else '보류'
        lines.append(f"| {r['id']} | {label(r['expected_pass'])} | {label(r['before_pass'])} | {label(r['after_pass'])} | {', '.join(r['issues']) or '-'} |")
    (out/'evaluation.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
