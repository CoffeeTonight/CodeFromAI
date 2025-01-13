// embedded_example.c
#include <stdio.h>

void setup() {
    // 초기화 코드
}

void loop(int i) {
    // 메인 루프 코드
    *(unsigned long *)(0x1000) = i;
    printf("Hello, Embedded C!\n");
}

int main() {
    setup();
    int i=0;
    while (1) {
        loop(i);
	i += 1;
    }
    return 0;
}
