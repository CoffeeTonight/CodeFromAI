import json
import os
import time

IDX = 0

def create_nested_instances(depth, instance_index):
    global IDX
    """재귀적으로 인스턴스를 생성하는 함수"""
    if depth == 0:
        return {}
    IDX += 1
    instance_key = f"u_sub_{IDX}"
    return {
        instance_key: {
            "module": "module",
            "ports": {
                "clk": "clk",
                "reset": "reset",
                "out": "out"
            },
            "filepath": f"/home/dyxn/PycharmProjects/a/design/HDLforAST/./sub_module_{IDX}.v",
            "instances": create_nested_instances(depth - 1, IDX)  # 다음 깊이로 재귀 호출
        }
    }


def create_nested_json(x, y, z):
    # 큰 JSON 구조 시

    nested_json = {
        "top_a": {
            "instances": {}
        }
    }

    for i in range(x):
        instance_key = f"A_{i}"
        nested_json["top_a"]["instances"][instance_key] = {
            "module": "module",
            "ports": {
                "clk": "clk",
                "reset": "reset"
            },
            "filepath": f"/home/dyxn/PycharmProjects/a/design/HDLforAST/module_{i}.v",
            "instances": {}
        }

        for j in range(y):
            # z 깊이만큼 재귀적으로 nested instances 추가
            nested_json["top_a"]["instances"][instance_key]["instances"].update(create_nested_instances(z, j))

    return nested_json


# 함수 호출 예시
x = 20  # A의 개수
y = 20  # 각 A의 nested instances 개수
z = 100  # 깊이
nested_json = create_nested_json(x, y, z)

# 저장할 디렉토리 생성
output_dir = "elab_outputs_dummy"
os.makedirs(output_dir, exist_ok=True)

# JSON 파일로 저장
json_file_path = os.path.join(output_dir, 'Elaborated_Hierarchy_top_a.json')
with open(json_file_path, 'w') as json_file:
    json.dump(nested_json, json_file, indent=4, ensure_ascii=False)

print(f"JSON saved to {json_file_path}")
