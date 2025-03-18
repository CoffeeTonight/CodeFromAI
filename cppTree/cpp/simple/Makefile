# Makefile
CC = g++
CFLAGS = -Wall -O2 -c -std=c++17 -I./header
LDFLAGS = -Wall -O2

SRC_DIR = ./src
OBJ_DIR = ./obj
BIN_DIR = ./bin

# 모든 .cpp 파일 찾기
SOURCES = $(wildcard $(SRC_DIR)/*.cpp)
# 각 소스 파일에 대한 객체 파일 경로
OBJECTS = $(patsubst $(SRC_DIR)/%.cpp,$(OBJ_DIR)/%.o,$(SOURCES))
# 각 소스 파일에 대한 실행 파일 경로
EXECUTABLES = $(patsubst $(SRC_DIR)/%.cpp,$(BIN_DIR)/%,$(SOURCES))

# 헤더 파일 (의존성 추적용)
HEADERS = $(wildcard ./header/*.h)

# 디렉토리 생성
$(shell mkdir -p $(OBJ_DIR) $(BIN_DIR))

# 기본 타겟: 모든 실행 파일 빌드
all: $(EXECUTABLES)

# 각 실행 파일 빌드 규칙
$(BIN_DIR)/%: $(OBJ_DIR)/%.o
	$(CC) $(LDFLAGS) $< -o $@

# 객체 파일 생성 규칙
$(OBJ_DIR)/%.o: $(SRC_DIR)/%.cpp $(HEADERS)
	$(CC) $(CFLAGS) $< -o $@

# 클린
clean:
	rm -rf $(OBJ_DIR)/*.o $(BIN_DIR)/*

.PHONY: all clean
