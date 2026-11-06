"""Golden dùng chung cho mọi cấp test (unit, integ, top).

Mọi expected của testcase PHẢI được tính bằng các hàm ở đây hoặc bằng các mô
hình module trong thư mục này, để cả nhóm dùng một chuẩn duy nhất.
Công thức: spec hệ thống v1.0 mục 2 (FUN-01 … FUN-04) và tài liệu thuật toán.
"""

MASK32 = (1 << 32) - 1


def s8(x):
    return ((x + 128) & 0xFF) - 128


def s32(x):
    return ((x + 2**31) & MASK32) - 2**31


def dot(a, b):
    """Tích vô hướng INT8 × INT8, tích lũy INT32 (wrap)."""
    return s32(sum(x * y for x, y in zip(a, b)))


def gemm(A, B):
    """C = A·B, A: M×K INT8, B: K×N INT8, C: M×N INT32."""
    K, N = len(B), len(B[0])
    return [[dot(row, [B[k][n] for k in range(K)]) for n in range(N)] for row in A]


def requant(acc, m0, sh, relu):
    """FUN-03: y = clamp(relu((acc·M0 + 2^(30+sh)) >> (31+sh)))."""
    y = (acc * m0 + (1 << (30 + sh))) >> (31 + sh)
    if relu:
        y = max(y, 0)
    return min(max(y, -128), 127)


def post(C, bias, m0, sh, relu):
    """Hậu xử lý VPU cho cả ma trận: cộng bias, requantize, ReLU, kẹp INT8."""
    return [[requant(s32(c + bias[j]), m0, sh, relu) for j, c in enumerate(row)] for row in C]


def quantize_multiplier(m):
    """Đổi hệ số thực 0 < m < 1 thành (M0, sh) với m ≈ M0 · 2^-(31+sh)."""
    assert 0 < m < 1
    sh = 0
    while m * 2 ** sh < 0.5 and sh < 31:
        sh += 1
    m0 = round(m * 2 ** (31 + sh))
    if m0 == 2**31:
        m0 //= 2; sh -= 1
    return m0, sh


# ---- ghi file testcase ----------------------------------------------------------
def write_hex(path, words, width=32):
    with open(path, "w") as f:
        for w in words:
            f.write("%0*x\n" % ((width + 3) // 4, w & ((1 << width) - 1)))


def write_words(path, pairs):
    """pairs: [(địa chỉ byte, word 32 bit)] → 'AAAAAAAA DDDDDDDD' mỗi dòng."""
    with open(path, "w") as f:
        for a, d in pairs:
            f.write("%08x %08x\n" % (a & MASK32, d & MASK32))


class ByteMem:
    """DRAM thưa theo byte (little-endian), dùng để dựng dram_init/expected."""
    def __init__(self):
        self.b = {}

    def w8(self, a, v):
        self.b[a] = v & 0xFF

    def w32(self, a, v):
        for e in range(4):
            self.b[a + e] = (v >> 8 * e) & 0xFF

    def r8(self, a):
        return s8(self.b.get(a, 0))

    def r32(self, a):
        return s32(sum(self.b.get(a + e, 0) << 8 * e for e in range(4)))

    def words(self, only=None):
        """Danh sách (addr, word) của mọi word có byte được ghi (hoặc trong 'only')."""
        addrs = sorted({a & ~3 for a in (only if only is not None else self.b)})
        return [(a, sum(self.b.get(a + e, 0) << 8 * e for e in range(4))) for a in addrs]


if __name__ == "__main__":
    # ví dụ của tài liệu thuật toán
    A = [[12, -5, 30, 7], [-20, 8, 4, 15]]
    B = [[3, -2, 10, 5], [6, 4, -7, 1], [-4, 9, 2, -3], [8, -1, 5, 6]]
    C = gemm(A, B)
    assert C == [[-58, 219, 250, 7], [92, 93, -173, -14]]
    m0, sh = quantize_multiplier(0.05 * 0.02 / 0.04)
    assert (m0, sh) == (1717986918, 5)
    Y = post(C, [500, -300, 200, -1000], m0, sh, 1)
    assert Y == [[11, 0, 11, 0], [15, 0, 1, 0]]
    print("gemm_golden: ví dụ tài liệu thuật toán khớp")
