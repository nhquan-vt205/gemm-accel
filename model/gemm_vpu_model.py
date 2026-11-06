"""Mô hình tham chiếu cycle-accurate của gemm_vpu.

Mô hình đúng vi kiến trúc trong spec module gemm_vpu:
  V1  chốt đoạn hàng, phát đọc bias (trễ SRAM 1 chu kỳ)
  V2  acc  = POST_EN ? c + bias : c            (INT32 wrap)
  V3  prod = POST_EN ? acc * M0 : sext(acc)    (64 bit, MUL_STAGES tầng)
  V4  thanh ghi đầu ra: đóng gói INT32 hoặc INT8, phát lệnh ghi C
Độ trễ LAT = 3 + MUL_STAGES (chu kỳ từ i_row_valid tới o_c_wr_en).

Dùng để:
  * golden bit-exact cho testbench RTL (post_ref, requant_ref);
  * kiểm tra cách hiện thực làm tròn rút gọn (requant_impl);
  * kiểm tra pipeline: luồng hàng ngẫu nhiên, luồng hàng đúng nhịp array,
    bố cục buffer C INT32 / INT8, thời điểm ghi và pe_done.
Chạy:  python3 gemm_vpu_model.py
"""
import random

MASK32 = (1 << 32) - 1


def s32(x):
    x &= MASK32
    return x - (1 << 32) if x >> 31 else x


# ---------------------------------------------------------------- golden (FUN-03)
def requant_ref(acc, M0, sh, relu):
    prod = acc * M0                                   # 64 bit có dấu, không tràn
    y = (prod + (1 << (30 + sh))) >> (31 + sh)        # dịch số học (Python >> = floor)
    if relu:
        y = max(y, 0)
    return min(max(y, -128), 127)


def post_ref(c, bias, M0, sh, relu):
    return requant_ref(s32(c + bias), M0, sh, relu)


# ---------------------------------------------------------------- cách hiện thực (REQ-03)
def requant_impl(prod, sh, relu):
    t = prod >> (30 + sh)                             # 34 bit có dấu
    assert -(1 << 33) <= t < (1 << 33)
    y = (t + 1) >> 1                                  # 33 bit có dấu
    if relu and y < 0:
        y = 0
    if y > 127:
        y = 127
    if y < -128:
        y = -128
    return y


# ---------------------------------------------------------------- mô hình chu kỳ
class Vpu:
    def __init__(self, P, MUL_STAGES=1):
        assert P in (2, 4, 8) and MUL_STAGES in (1, 2)
        self.P, self.MS = P, MUL_STAGES
        self.LAT = 3 + MUL_STAGES
        self.s1 = None                      # (meta, c[P])
        self.s2 = None                      # (meta, acc[P])
        self.s3 = [None] * MUL_STAGES       # (meta, prod[P])
        self.out = None                     # (en, fmt, row, col, data[P], mask[P])
        self.bias_q = None                  # dữ liệu SRAM bias (trễ 1)

    def soft_clr(self):
        self.s1 = self.s2 = None
        self.s3 = [None] * self.MS
        self.out = None

    def step(self, row, cfg, bias_mem):
        """row = None hoặc (idx, col, data[P], mask[P]); trả về lệnh ghi C của chu kỳ này."""
        P = self.P
        post, relu, M0, sh = cfg
        wr = self.out                                       # o_c_wr_* là thanh ghi
        rd = (row is not None) and post                     # o_bias_rd_en
        # ---- tổ hợp từng tầng
        n2 = None
        if self.s1:
            meta, c = self.s1
            b = self.bias_q
            if post:
                assert b is not None, "thiếu dữ liệu bias đúng chu kỳ"
                acc = [s32(c[k] + b[k]) if meta[2][k] else None for k in range(P)]
            else:
                acc = list(c)
            n2 = (meta, acc)
        n3 = None
        if self.s2:
            meta, acc = self.s2
            n3 = (meta, [(a * M0 if post else a) if a is not None else None for a in acc])
        nout = None
        last = self.s3[-1]
        if last:
            (idx, col, mask), prod = last
            if post:
                data = [requant_impl(p, sh, relu) if m else None for p, m in zip(prod, mask)]
            else:
                data = [s32(p) if m else None for p, m in zip(prod, mask)]
            nout = (1, int(post), idx, col, data, mask)
        # ---- cạnh clock
        self.bias_q = [bias_mem[row[1] + k] if row[1] + k < len(bias_mem) else None
                       for k in range(P)] if rd else None
        self.out = nout
        self.s3 = [n3] + self.s3[:-1]
        self.s2 = n2
        self.s1 = ((row[0], row[1], row[3]), list(row[2])) if row else None
        return wr, rd


def c_buffer_write(cbuf, wr, P):
    """Ngữ nghĩa cổng ghi C phía SRAM (VPU-W..): cbuf[(i, word)] = word 32 bit."""
    if not wr:
        return
    _, fmt, i, j0, data, mask = wr
    for c in range(P):
        if not mask[c]:
            continue
        j = j0 + c
        if fmt == 0:
            key = (i, j)
            assert key not in cbuf, "ghi hai lần"
            cbuf[key] = data[c] & MASK32
        else:
            key = (i, j >> 2)
            old = cbuf.get(key, 0)
            lane = j & 3
            assert (key, lane) not in cbuf.setdefault('_bytes', set()), "ghi hai lần"
            cbuf['_bytes'].add((key, lane))
            cbuf[key] = (old & ~(0xFF << 8 * lane)) | ((data[c] & 0xFF) << 8 * lane)


def golden_cbuf(Cm, bias, cfg, M, N):
    post, relu, M0, sh = cfg
    g = {}
    for i in range(M):
        for j in range(N):
            if post:
                y = post_ref(Cm[i][j], bias[j], M0, sh, relu) & 0xFF
                g[(i, j >> 2)] = g.get((i, j >> 2), 0) | (y << 8 * (j & 3))
            else:
                g[(i, j)] = Cm[i][j] & MASK32
    return g


def array_row_stream(M, N, K, P):
    """Thời điểm o_row_valid theo spec gemm_systolic_array: D_n(r) = 1 + nI + K + P + 1 + r."""
    I = max(K, P)
    TM, TN = -(-M // P), -(-N // P)
    ev = {}
    n = 0
    for ti in range(TM):
        for tj in range(TN):
            i0, j0 = ti * P, tj * P
            for r in range(min(P, M - i0)):
                ev[1 + n * I + K + P + 1 + r] = (i0 + r, j0)
            n += 1
    return ev


def run_stream(P, MS, M, N, Cm, bias, cfg, events, rng):
    v = Vpu(P, MS)
    cbuf = {}
    last_in = max(events)
    wr_times = []
    for t in range(last_in + v.LAT + 3):
        row = None
        if t in events:
            i, j0 = events[t]
            mask = [1 if j0 + c < N else 0 for c in range(P)]
            data = [Cm[i][j0 + c] if mask[c] else rng.randint(-2**31, 2**31 - 1) for c in range(P)]
            row = (i, j0, data, mask)
        wr, rd = v.step(row, cfg, bias)
        if wr:
            wr_times.append(t)
            c_buffer_write(cbuf, wr, P)
    cbuf.pop('_bytes', None)
    return cbuf, wr_times, v.LAT


def rand_cfg(rng, post=None):
    post = rng.random() < 0.7 if post is None else post
    relu = post and rng.random() < 0.5
    M0 = rng.choice([rng.randint(2**30, 2**31 - 1), rng.randint(-2**31, 2**31 - 1),
                     -2**31, 2**31 - 1, 0, 1, -1])
    sh = rng.randint(0, 31)
    return (int(post), int(relu), M0, sh)


if __name__ == '__main__':
    rng = random.Random(7)
    # 1. requant_impl == requant_ref (biên + ngẫu nhiên)
    edge_acc = [-2**31, 2**31 - 1, 0, 1, -1, 2**19, -2**19]
    edge_m0 = [-2**31, 2**31 - 1, 0, 1, -1, 2**30, 1717986918]
    nreq = 0
    for a in edge_acc:
        for m in edge_m0:
            for sh in range(32):
                for relu in (0, 1):
                    assert requant_impl(a * m, sh, relu) == requant_ref(a, m, sh, relu)
                    nreq += 1
    for _ in range(200000):
        a = rng.randint(-2**31, 2**31 - 1); m = rng.randint(-2**31, 2**31 - 1)
        sh = rng.randint(0, 31); relu = rng.randint(0, 1)
        # ép thêm trường hợp đúng nửa: prod = (2q+1) * 2^(30+sh)
        if rng.random() < 0.1:
            q = rng.randint(-300, 300); m = 1; a = None
            prod = (2 * q + 1) << (30 + sh)
            ref = (prod + (1 << (30 + sh))) >> (31 + sh)
            ref = min(max(max(ref, 0) if relu else ref, -128), 127)
            assert requant_impl(prod, sh, relu) == ref
        else:
            assert requant_impl(a * m, sh, relu) == requant_ref(a, m, sh, relu)
        nreq += 1
    print("requant: %d trường hợp khớp" % nreq)

    # 2. pipeline với luồng hàng ngẫu nhiên và luồng đúng nhịp array
    ntest = bad = 0
    for P in (4, 8):
        for MS in (1, 2):
            for trial in range(150):
                M = rng.randint(1, 32); N = rng.randint(1, 8) * 4; K = rng.randint(1, 8) * 4
                Cm = [[rng.randint(-2**19, 2**19) for _ in range(N)] for _ in range(M)]
                bias = [rng.randint(-2**31, 2**31 - 1) if rng.random() < 0.2 else rng.randint(-5000, 5000)
                        for _ in range(N)] + [None] * (32 - N)
                cfg = rand_cfg(rng)
                if trial % 2 == 0:
                    ev = array_row_stream(M, N, K, P)
                else:                       # luồng ngẫu nhiên: liền nhau hoặc có khoảng trống
                    segs = [(i, j0) for i in range(M) for j0 in range(0, N, P)]
                    rng.shuffle(segs)
                    ev = {}; t = rng.randint(0, 3)
                    for s in segs:
                        ev[t] = s; t += 1 if rng.random() < 0.6 else rng.randint(2, 5)
                cbuf, wt, LAT = run_stream(P, MS, M, N, Cm, bias, cfg, ev, rng)
                g = golden_cbuf(Cm, bias, cfg, M, N)
                ok = cbuf == g and wt == sorted(t + LAT for t in ev)
                if trial % 2 == 0:
                    pe_done = max(ev) + LAT + 1
                    ok = ok and max(wt) < pe_done
                ntest += 1
                if not ok:
                    bad += 1; print("FAIL", P, MS, M, N, K, cfg)
    print("pipeline: %d test, %d lỗi" % (ntest, bad))

    # 3. ví dụ của tài liệu (P = 4, M = 2, N = 4, K = 4, MUL_STAGES = 1)
    Cm = [[-58, 219, 250, 7], [92, 93, -173, -14]]
    bias = [500, -300, 200, -1000] + [None] * 28
    for cfg in ((1, 1, 1717986918, 5), (0, 0, 0, 0)):
        ev = array_row_stream(2, 4, 4, 4)
        v = Vpu(4, 1)
        for t in range(max(ev) + 8):
            row = None
            if t in ev:
                i, j0 = ev[t]; row = (i, j0, Cm[i][j0:j0 + 4], [1] * 4)
            wr, rd = v.step(row, cfg, bias)
            if row or rd or wr:
                info = ""
                if wr:
                    d = wr[4]
                    word = sum((x & 0xFF) << 8 * k for k, x in enumerate(d)) if wr[1] else None
                    info = "wr fmt=%d row=%d col=%d data=%s%s" % (
                        wr[1], wr[2], wr[3], d, (" word=0x%08X" % word) if word is not None else "")
                print("cfg", cfg, "t", t, "row_in" if row else "", "bias_rd" if rd else "", info)
        print("pe_done =", max(ev) + v.LAT + 1)
    # 4. bảng chu kỳ tổng (array + VPU)
    def pe_done(M, N, K, P, L):
        I = max(K, P); NT = -(-M // P) * -(-N // P); rl = min(P, M - (-(-M // P) - 1) * P) - 1
        return (NT - 1) * I + K + P + rl + L + 3
    for (M, N, K) in ((32, 32, 32), (20, 12, 8), (2, 4, 4)):
        print((M, N, K), [pe_done(M, N, K, P, L) for P in (4, 8) for L in (4, 5)])
