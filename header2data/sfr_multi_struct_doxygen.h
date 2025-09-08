/** @defgroup Peripheral Peripheral Registers
 *  @brief Peripheral-related SFRs and configurations
 *  @{
 */

typedef uint8_t uint08; // 비표준 타입 정의

/** @brief Base address for SFRs
 *  @address 0x1000
 */
#define BADDR 0x1000

/** @brief Test Control Register
 *  @ip Test
 *  @address 0x1000
 *  @note 64-bit register with read/write native structures
 *  @bit 0-9 W Write Control (Value: 0x3FF, Effect: Configure write parameters)
 *  @bit 10-19 D Data Control (Value: 0xFFC00, Effect: Configure data parameters)
 *  @bit 30-34 STATUS Status Flags (Value: 0x7C000000, Effect: Indicate status)
 *  @bit 40-43 RDYVAL Ready Value (Value: 0xF000000000, Effect: Indicate readiness)
 *  @bit 44-59 DATA Data Field (Value: 0xFFFF0000000000, Effect: Data payload)
 */
typedef volatile union _SFR_TEST_CTRL {
    volatile uint64_t nValue; /**< Full 64-bit value */
    volatile uint32_t nValue32[2]; /**< 32-bit value array */

    /** @brief Native read structure */
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

    /** @brief Native write structure */
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

/** @brief Value Control Register
 *  @ip Value
 *  @address 0x1008
 *  @bit 0-15 W Write Value (Value: 0xFFFF, Effect: Set write value)
 *  @bit 16-31 R Read Value (Value: 0xFFFF0000, Effect: Read value)
 */
typedef volatile union _SFR_VAL_CTRL {
    volatile uint32_t nValue; /**< Full 32-bit value */
    volatile uint08_t nValue8[4]; /**< 8-bit value array */

    /** @brief Native structure */
    struct {
        volatile uint32_t W : 16; /**< Write value */
        volatile uint32_t R : 16; /**< Read value */
    } stNative;
} SFR_VAL_CTRL, *pSFR_VAL_CTRL;

/** @brief OX Control Register
 *  @ip OX
 *  @address 0x1010
 *  @bit 0-7 WW Write Word (Value: 0xFF, Effect: Write control word)
 *  @bit 8-15 XX Extra Control (Value: 0xFF00, Effect: Extra parameters)
 *  @bit 16-23 YW Yield Word (Value: 0xFF0000, Effect: Yield control)
 *  @bit 24-31 ZR Zero Reset (Value: 0xFF000000, Effect: Reset to zero)
 */
typedef volatile union _SFR_OX_CTRL {
    volatile uint32_t nValue; /**< Full 32-bit value */

    /** @brief Native structure */
    struct {
        volatile uint32_t WW : 8; /**< Write word */
        volatile uint32_t XX : 8; /**< Extra control */
        volatile uint32_t YW : 8; /**< Yield word */
        volatile uint32_t RSVD0 : 8; /**< Reserved */
    } stNative;
} SFR_OX_CTRL, *pSFR_OX_CTRL;

/** @brief S1 Group Structure
 *  @ip S1
 *  @address 0x1020
 */
typedef volatile struct _SFR_S1_GRP {
    /** @brief Test register 0 */
    uint32_t nTEST0;
    /** @brief Test register array
     *  @element 0 Test 1-0
     *  @element 1 Test 1-1
     */
    uint32_t anTEST1[2];
    /** @brief Reserved registers */
    uint32_t anRSVD[10];
    /** @brief Test register 2 array */
    uint08_t nTEST2[12];
} SFR_S1_GRP, *pSFR_S1_GRP;

/** @brief S2 Group Structure
 *  @ip S2
 *  @address 0x1040
 */
typedef volatile struct _SFR_S2_GRP {
    /** @brief Test control register */
    SFR_TEST_CTRL nTEST;
    /** @brief Value control register array
     *  @element 0 Value 0
     *  @element 1 Value 1
     */
    SFR_VAL_CTRL anVAL[2];
    /** @brief OX control register array
     *  @element 0 OX 0
     */
    SFR_OX_CTRL anOX[10];
    /** @brief Test register 0 array */
    uint32_t nTEST0[3];
} SFR_S2_GRP, *pSFR_S2_GRP;

/** @brief All SFR Structure
 *  @ip Peripheral
 *  @address 0x1080
 *  @element 0 Peripheral instance 0
 */
typedef volatile struct _SFR_AL {
    /** @brief Test register 1 */
    uint32_t nTEST1;
    /** @brief Test register array */
    uint08_t anTEST[8];
    /** @brief Test register 2 */
    uint64_t nTEST2;
    /** @brief S1 group structure */
    SFR_S1_GRP stS1_GRP;
    /** @brief S2 group structure */
    SFR_S2_GRP stS2_GRP;
    /** @brief S1 group array
     *  @element 0 S1 Group 0
     */
    SFR_S1_GRP astS1_GRP[4];
    /** @brief S2 group array
     *  @element 0 S2 Group 0
     */
    SFR_S2_GRP astS2_GRP[4];
} SFR_AL, *pSFR_AL;

/** @} */