/** @brief Test Control Register
 * @ip Test
 * @address 0x1000
 */
typedef volatile union _SFR_TEST_CTRL {
    uint64_t nValue; /**< Full 64-bit value */
    struct {
        uint64_t W : 10; /**< Write control */
    } stNativeR;
} SFR_TEST_CTRL, *pSFR_TEST_CTRL;

typedef volatile struct _TEST_STRUCT {
    uint32_t field; // Simple comment
    SFR_TEST_CTRL ctrl;
} TEST_STRUCT;
