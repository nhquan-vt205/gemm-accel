/* =============================================================================
 * gemm_regs.h — register map của accelerator (spec hệ thống v1.0, bảng 3-1 … 3-3)
 * Dùng cho driver bare-metal trên Rocket. Địa chỉ nền do SoC Chipyard cấp.
 * ========================================================================== */
#ifndef GEMM_REGS_H
#define GEMM_REGS_H
#include <stdint.h>

#define GEMM_CTRL            0x000u  /* [0] START [1] SOFT_RESET [2] START_CHAIN */
#define GEMM_STATUS          0x004u  /* [0] DONE [1] BUSY [2] ERROR [3] MODE [7:4] ERR_CODE */
#define GEMM_MATRIX_DIM      0x008u  /* [7:0] M [15:8] N [23:16] K */
#define GEMM_BASE_ADDR_IN    0x00Cu
#define GEMM_BASE_ADDR_WEIGHT 0x010u
#define GEMM_BASE_ADDR_OUT   0x014u
#define GEMM_POST_CTRL       0x018u  /* [0] POST_EN [1] RELU_EN */
#define GEMM_BIAS_ADDR       0x01Cu
#define GEMM_QUANT_M0        0x020u
#define GEMM_QUANT_SHIFT     0x024u  /* [4:0] */
#define GEMM_HW_CONFIG       0x028u  /* [7:0] P [15:8] MAX_DIM [16] HAS_CHAIN [17] HAS_PINGPONG [31:24] SPEC_VER */
#define GEMM_PERF_TOTAL      0x02Cu
#define GEMM_PERF_LOAD       0x030u
#define GEMM_PERF_COMPUTE    0x034u
#define GEMM_PERF_STORE      0x038u
#define GEMM_DESC_PTR        0x040u
#define GEMM_ERR_DESC_ADDR   0x044u
#define GEMM_DESC_DONE_CNT   0x048u

#define GEMM_CTRL_START        (1u << 0)
#define GEMM_CTRL_SOFT_RESET   (1u << 1)
#define GEMM_CTRL_START_CHAIN  (1u << 2)
#define GEMM_STATUS_DONE       (1u << 0)
#define GEMM_STATUS_BUSY       (1u << 1)
#define GEMM_STATUS_ERROR      (1u << 2)
#define GEMM_STATUS_ERR_CODE(s) (((s) >> 4) & 0xFu)

#define GEMM_DIM(m, n, k)  ((uint32_t)(m) | ((uint32_t)(n) << 8) | ((uint32_t)(k) << 16))

/* Descriptor 16 word, căn 64 byte (spec hệ thống mục 7.2) */
typedef struct __attribute__((aligned(64))) {
  uint32_t dim;        /* w0  [7:0] M [15:8] N [23:16] K */
  uint32_t a_addr;     /* w1 */
  uint32_t b_addr;     /* w2 */
  uint32_t c_addr;     /* w3 */
  uint32_t ld_ab;      /* w4  [15:0] LDA [31:16] LDB (byte, 0 = liền) */
  uint32_t ldc;        /* w5  [15:0] LDC */
  uint32_t flags;      /* w6  [0] LAST [1] WAIT_PREV [2] REUSE_B [3] POST_EN [4] RELU_EN */
  uint32_t next_ptr;   /* w7 */
  uint32_t bias_addr;  /* w8 */
  uint32_t quant_m0;   /* w9 */
  uint32_t quant_shift;/* w10 [4:0] */
  uint32_t tag;        /* w11 phần mềm tự dùng */
  uint32_t rsv[4];     /* w12 … w15 phải bằng 0 */
} gemm_desc_t;

#define GEMM_DESC_LAST      (1u << 0)
#define GEMM_DESC_WAIT_PREV (1u << 1)
#define GEMM_DESC_REUSE_B   (1u << 2)
#define GEMM_DESC_POST_EN   (1u << 3)
#define GEMM_DESC_RELU_EN   (1u << 4)

#endif /* GEMM_REGS_H */
