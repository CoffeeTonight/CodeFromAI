import re
import os
import sys
import glob


def parse_makefile(file_path):
    targets = {}  # {타겟: [의존성 리스트]}
    variables = {}  # {변수 이름: 값}

    if not os.path.isfile(file_path):
        print(f"Error: {file_path} is not a valid file")
        return targets, variables

    with open(file_path, 'r') as f:
        lines = f.readlines()

    current_target = None
    for line in lines:
        line = line.strip()
        if line.startswith('#') or not line:
            continue

        # 변수 정의
        if '=' in line:
            var_match = re.match(r'(\w+)\s*[:]?=\s*(.+)', line)
            if var_match:
                var_name, var_value = var_match.groups()
                variables[var_name] = var_value
                continue

        # 타겟 정의
        target_match = re.match(r'([^:\s]+)\s*:\s*(.+)', line)
        if target_match:
            target, deps = target_match.groups()
            if target != '.PHONY':
                targets[target] = deps.split()
            current_target = target
            continue

        if line.startswith('\t'):
            continue

    # 변수 치환
    for target, deps in targets.items():
        new_deps = []
        for dep in deps:
            expanded_dep = expand_variable(dep, variables)
            new_deps.extend(expanded_dep)
        targets[target] = new_deps

    return targets, variables


def expand_variable(value, variables):
    """Makefile 변수 치환"""
    if not value:
        return [value]

    # $(wildcard 패턴) 처리
    wildcard_match = re.match(r'\$\(wildcard\s+(.+?)\)', value)
    if wildcard_match:
        pattern = wildcard_match.group(1)
        return glob.glob(pattern)

    # $(patsubst 패턴,대체,대상) 처리
    patsubst_match = re.match(r'\$\(patsubst\s+(.+?),(.+?),(.+?)\)', value)
    if patsubst_match:
        pattern, replacement, target = patsubst_match.groups()
        target_files = expand_variable(target, variables)
        result = []
        for tf in target_files:
            if pattern in tf:
                result.append(tf.replace(pattern, replacement.replace('$(OBJ_DIR)', variables.get('OBJ_DIR', './obj'))))
        return result

    # 단순 변수 치환
    if value in variables:
        return expand_variable(variables[value], variables)
    return [value]


def extract_target_sources(targets, specific_target=None):
    result = {}
    for target, deps in targets.items():
        if specific_target and target != specific_target:
            continue
        sources = [dep for dep in deps if dep.endswith(('.c', '.cpp', '.cc', '.h', '.hpp'))]
        if sources:
            result[target] = sources
    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_targets_from_makefile.py <makefile_path> [target]")
        sys.exit(1)

    makefile_path = sys.argv[1]
    specific_target = sys.argv[2] if len(sys.argv) > 2 else None

    targets, variables = parse_makefile(makefile_path)
    print(f"Parsed variables: {variables}")

    target_sources = extract_target_sources(targets, specific_target)

    if not target_sources:
        print("No source files found for the specified target.")
    else:
        print("\n=== Target Sources ===")
        for target, sources in target_sources.items():
            print(f"Target: {target}")
            print(f"Sources: {', '.join(sources)}")
            print()


if __name__ == "__main__":
    main()