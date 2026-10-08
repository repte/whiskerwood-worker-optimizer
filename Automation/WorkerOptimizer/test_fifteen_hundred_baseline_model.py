"""Check that the large benchmark rejects changed tie assignments offline."""

import ast
from pathlib import Path


def run():
    path = Path(__file__).with_name('benchmark_fifteen_hundred_workers.py')
    tree = ast.parse(path.read_text(encoding='utf-8'))
    selected = [item for item in tree.body if
                isinstance(item, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == 'BASELINE_ASSIGNMENTS'
                    for target in item.targets) or
                isinstance(item, ast.FunctionDef) and item.name == 'verify_baseline_assignment']
    namespace = {}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)
    verify = namespace['verify_baseline_assignment']
    expected = namespace['BASELINE_ASSIGNMENTS']
    assert len(expected) == 6
    for case, digest in expected.items():
        result = {'assignment_sha256': digest}
        verify(case, result)
        assert result['baseline_assignment_verified'] is True
        for changed in ('0' * 64, ''):
            try:
                verify(case, {'assignment_sha256': changed})
            except AssertionError:
                pass
            else:
                raise AssertionError(('changed assignment accepted', case))
    print('WO_1500_BASELINE_ASSIGNMENT_MODEL_PASS six matches and twelve rejections')


if __name__ == '__main__':
    run()
