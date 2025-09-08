
typedef uint8_t uint08; // 비표준 타입 정의

#define BADDR 0x1000

typedef volatile union _SFR_TEST_CTRL {
    volatile uint64_t nValue; /**< Full 64-bit value */
    volatile uint32_t nValue32[2]; /**< 32-bit value array */

    struct {
        volatile uint64_t W : 10; /**< Write control */
        volatile uint64_t D : 10; /**< Data control */
        volatile uint64_t RSVD0 : 10; /**< Reserved */
        volatile uint64_t STATUS : 5; /**< Status flags */
        volatile uint64_t RSVD1 : 5; /**< Reserved */
        volatile uint64_t RDYVAL : 4; /**< Ready value */
        volatile uint64_t DATA : 16; /**< Data field */
        volatile uint64_t RSVD2 : 4; /**< Reserved */
    } stNativeR;

    struct {
        volatile uint64_t W : 10; /**< Write control */
        volatile uint64_t D : 10; /**< Data control */
        volatile uint64_t RSVD0 : 10; /**< Reserved */
        volatile uint64_t STATUS : 5; /**< Status flags */
        volatile uint64_t RSVD1 : 5; /**< Reserved */
        volatile uint64_t RDYVAL : 4; /**< Ready value */
        volatile uint64_t DATA : 16; /**< Data field */
        volatile uint64_t STATUS : 4; /**< Status field (write) */
    } stNativeW;
} SFR_TEST_CTRL, *pSFR_TEST_CTRL;

typedef volatile union _SFR_VAL_CTRL {
    volatile uint32_t nValue; /**< Full 32-bit value */
    volatile uint8_t nValue8[4]; /**< 8-bit value array */

    struct {
        volatile uint32_t W : 16; /**< Write value */
        volatile uint32_t R : 16; /**< Read value */
    } stNative;
} SFR_VAL_CTRL, *pSFR_VAL_CTRL;

typedef volatile union _SFR_OX_CTRL {
    volatile uint32_t nValue; /**< Full 32-bit value */

    struct {
        volatile uint32_t WW : 8; /**< Write word */
        volatile uint32_t XX : 8; /**< Extra control */
        volatile uint32_t YW : 8; /**< Yield word */
        volatile uint32_t RSVD0 : 8; /**< Reserved */
    } stNative;
} SFR_OX_CTRL, *pSFR_OX_CTRL;

typedef volatile struct _SFR_S1_GRP {
    uint32_t nTEST0;
    uint32_t anTEST1[2];
    uint32_t anRSVD[10];
    uint8_t nTEST2[12];
} SFR_S1_GRP, *pSFR_S1_GRP;

typedef volatile struct _SFR_S2_GRP {
    SFR_TEST_CTRL nTEST;
    SFR_VAL_CTRL anVAL[2];
    SFR_OX_CTRL anOX[10];
    uint32_t nTEST0[3];
} SFR_S2_GRP, *pSFR_S2_GRP;

typedef volatile struct _SFR_AL {
    uint32_t nTEST1;
    uint8_t anTEST[8];
    uint64_t nTEST2;
    SFR_S1_GRP stS1_GRP;
    SFR_S2_GRP stS2_GRP;
    SFR_S1_GRP astS1_GRP[4];
    SFR_S2_GRP astS2_GRP[4];
} SFR_AL, *pSFR_AL;
