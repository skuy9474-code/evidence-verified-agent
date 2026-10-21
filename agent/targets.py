"""질문에 명시한 시스템을 보존한다. 미등록 이름도 unknown 조회 대상으로 남긴다."""
import re


def explicit_targets(query, known_systems):
    pattern = r'(?<![a-zA-Z0-9_-])(?:[a-z][a-z0-9]*(?:-[a-z0-9]+)*-service|[a-z]+-\d+)(?![a-zA-Z0-9_-])'
    matches = [(m.start(), m.group(0).lower()) for m in re.finditer(pattern, query, re.I)]
    for name in known_systems:
        match = re.search(r'(?<![a-zA-Z0-9_-])'+re.escape(name)+r'(?![a-zA-Z0-9_-])', query, re.I)
        if match:
            matches.append((match.start(), name))
    return list(dict.fromkeys(name for _, name in sorted(matches)))


def normalize_plan(raw, query, known_systems):
    requested = explicit_targets(query, known_systems)
    model_tasks = raw.get('tasks', []) if isinstance(raw, dict) else []
    if not isinstance(model_tasks, list):
        model_tasks = []
    targets = requested or list(dict.fromkeys(
        t.get('target') for t in model_tasks if isinstance(t, dict)
        and t.get('agent') == 'research' and t.get('target') in known_systems)) or ['auth-service']
    tasks = [{'id': f'task-{i}', 'agent': 'research', 'kind': 'monitoring',
              'target': target, 'status': 'pending'} for i, target in enumerate(targets)]
    analysis = bool(raw.get('needs_analysis', False)) if isinstance(raw, dict) else False
    if analysis:
        tasks.append({'id': 'task-analysis', 'agent': 'analysis', 'kind': 'pattern-analysis', 'status': 'pending'})
    return {'needs_analysis': analysis, 'tasks': tasks}
