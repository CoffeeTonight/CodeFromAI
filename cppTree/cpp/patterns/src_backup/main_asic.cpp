
// main.cpp
#include "asic_driver.hpp"

int main() {
    AsicDriver driver;
    driver.transferData(0xDEADBEEF);  // ASIC에 데이터 전송
    uint32_t result = driver.readData();  // ASIC에서 데이터 읽기
    return 0;
}
