import clang.cindex
import logging
import re  # 추가: 정규 표현식 모듈 임포트

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

index = clang.cindex.Index.create()
tu = index.parse('/home/user/workspace/CodeFromAI/cppTree/cpp/patterns/src/testcase_hierarchy.cpp', args=['-I', '/home/user/workspace/CodeFromAI/cppTree/cpp/patterns/./header'])
tokens = list(tu.get_tokens(extent=tu.cursor.extent))
logger.debug(f"Full token list: {[t.spelling for t in tokens]}")

address_map = {}
i = 0
while i < len(tokens) - 1:
    if tokens[i].spelling == "#" and tokens[i + 1].spelling == "define" and i + 3 < len(tokens):
        name = tokens[i + 2].spelling
        value = tokens[i + 3].spelling
        logger.debug(f"Found #define: {name} = {value}")
        if re.match(r'0x[0-9A-Fa-f]+|\d+', value):
            address_map[name] = value
            logger.debug(f"Address mapped: {name} -> {value}")
        elif value in address_map:
            address_map[name] = address_map[value]
            logger.debug(f"Address mapped via reference: {name} -> {address_map[value]}")
        i += 4
    else:
        i += 1
logger.debug(f"Address map: {address_map}")