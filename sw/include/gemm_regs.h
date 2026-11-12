/* =============================================================================
 * gemm_regs.h — register map của accelerator (spec hệ thống baseline, mục 2 và 5)
 * Dùng cho driver bare-metal trên Rocket. Địa chỉ nền do SoC Chipyard cấp.
 * Chỉ có một chế độ: chuỗi descriptor + scratchpad ping-pong (D-01, D-03).
 * ========================================================================== */
#ifndef GEMM_REGS_H
#define GEMM_REGS_H
#include <stdint.h>

/* ---- Offset thanh ghi; 0x008 … 0x024 và 0x03C dự trữ (đọc 0, ghi bị bỏ qua) */
#define GEMM_CTRL            0x000u  /* W : [1] SOFT_RESET [2] START; [0], [31:3] dự trữ */
#define GEMM_STATUS          0x004u  /* RO: [0] DONE [1] BUSY [2] ERROR [3] dự trữ [7:4] ERR_CODE */
#define GEMM_HW_CONFIG       0x028u  /* RO: [7:0] P [15:8] MAX_DIM [23:16] dự trữ [31:24] SPEC_VER */
#define GEMM_PERF_TOTAL      0x02Cu
#define GEMM_PERF_LOAD       0x030u
#define GEMM_PERF_COMPUTE    0x034u
#define GEMM_PERF_STORE      0x038u
#define GEMM_DESC_PTR        0x040u  /* RW: địa chỉ descriptor đầu chuỗi, căn 64 byte */
#define GEMM_ERR_DESC_ADDR   0x044u
#define GEMM_DESC_DONE_CNT   0x048u

/* ---- CTRL (chỉ có hiệu lực khi wstrb[0] = 1; SOFT_RESET thắng START) */
#define GEMM_CTRL_SOFT_RESET   (1u << 1)
#define GEMM_CTRL_START        (1u << 2)

/* ---- STATUS */
#define GEMM_STATUS_DONE       (1u << 0)
#define GEMM_STATUS_BUSY       (1u << 1)
#define GEMM_STATUS_ERROR      (1u << 2)
#define GEMM_STATUS_ERR_CODE(s) (((s) >> 4) & 0xFu)

/* ---- ERR_CODE (STATUS[7:4]); 5 … 15 dự trữ, không bao giờ xuất hiện */
#define GEMM_ERR_NONE          0u
#define GEMM_ERR_CFG           1u   /* descriptor sai điều kiện hoặc DESC_PTR không căn 64 byte */
#define GEMM_ERR_AXI_RD        2u   /* LOAD_A / LOAD_B / LOAD_BIAS */
#define GEMM_ERR_AXI_WR        3u   /* STORE_C */
#define GEMM_ERR_FETCH         4u   /* đọc descriptor */

/* ---- HW_CONFIG: giá trị reset 0x1100_2008 */
#define GEMM_HW_CONFIG_VALUE   0x11002008u
#define GEMM_HW_P(v)           ((v) & 0xFFu)
#define GEMM_HW_MAX_DIM(v)     (((v) >> 8) & 0xFFu)
#define GEMM_HW_SPEC_VER(v)    (((v) >> 24) & 0xFFu)

#define GEMM_DIM(m, n, k)  ((uint32_t)(m) | ((uint32_t)(n) << 8) | ((uint32_t)(k) << 16))

/* Descriptor 16 word, căn 64 byte (spec hệ thống baseline, mục 5.2) */
typedef struct __attribute__((aligned(64))) {
  uint32_t dim;        /* w0  [7:0] M [15:8] N [23:16] K; [31:24] = 0 */
  uint32_t a_addr;     /* w1 */
  uint32_t b_addr;     /* w2  bỏ qua khi REUSE_B = 1 */
  uint32_t c_addr;     /* w3 */
  uint32_t ld_ab;      /* w4  [15:0] LDA [31:16] LDB (byte, 0 = liền) */
  uint32_t ldc;        /* w5  [15:0] LDC; [31:16] dự trữ */
  uint32_t flags;      /* w6  [0] LAST [1] WAIT_PREV [2] REUSE_B [3] POST_EN [4] RELU_EN */
  uint32_t next_ptr;   /* w7  căn 64 byte; bỏ qua khi LAST = 1 */
  uint32_t bias_addr;  /* w8  chỉ dùng khi POST_EN = 1 */
  uint32_t quant_m0;   /* w9  INT32 có dấu; chỉ dùng khi POST_EN = 1 */
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
