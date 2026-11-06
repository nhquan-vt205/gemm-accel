"""Mô hình tham chiếu của gemm_local_sram: ánh xạ địa chỉ logic → (sub-bank, địa chỉ cục bộ).

Kiểm tra cho P = 4, 8 và NB = 1, 2:
  * ánh xạ là song ánh (mỗi word logic có đúng một ô vật lý);
  * mỗi truy cập song song của array / VPU chạm P (hoặc P/4) sub-bank khác nhau;
  * DMA ghi A, B, BIAS theo bố cục logic rồi array / VPU đọc ra đúng phần tử;
  * VPU ghi C (INT32 và INT8) rồi DMA đọc theo bố cục logic ra đúng giá trị.
Chạy:  python3 gemm_sram_model.py
"""
import random


def lg(x):
    return x.bit_length() - 1


def map_a(a, P):            # a = {i[4:0], kw[2:0]}
    i, kw = a >> 3, a & 7
    return i % P, ((i >> lg(P)) << 3) | kw


def map_b(a, P):            # a = {k[4:0], jw[2:0]}
    Q = P // 4
    k, jw = a >> 3, a & 7
    return jw % Q, (k << (3 - lg(Q))) | (jw >> lg(Q))


def map_bias(a, P):         # a = j[4:0]
    return a % P, a >> lg(P)


def map_c(a, P):            # a[9:0], INT32 {i, j} hoặc INT8 {i, jw}
    return a % P, a >> lg(P)


DEPTH = lambda P: dict(A=256 // P, B=256 // (P // 4), BIAS=32 // P, C=1024 // P)
NSUB = lambda P: dict(A=P, B=P // 4, BIAS=P, C=P)
MAPS = dict(A=map_a, B=map_b, BIAS=map_bias, C=map_c)
SIZE = dict(A=256, B=256, BIAS=32, C=1024)


class Sram:
    def __init__(self, P, NB):
        self.P, self.NB = P, NB
        self.m = {(buf, b, s): [None] * DEPTH(P)[buf]
                  for buf in MAPS for b in range(NB) for s in range(NSUB(P)[buf])}

    # ---- phía DMA
    def dma_write(self, buf, bank, a, data):
        s, l = MAPS[buf](a, self.P)
        self.m[(buf, bank, s)][l] = data

    def dma_read_c(self, bank, a):
        s, l = map_c(a, self.P)
        return self.m[('C', bank, s)][l]

    # ---- phía array / VPU (trả về danh sách sub-bank chạm tới để kiểm xung đột)
    def a_read(self, bank, i0, k):
        P = self.P
        subs, out = [], []
        for r in range(P):
            s, l = r, ((i0 >> lg(P)) << 3) | (k >> 2)
            subs.append(s)
            w = self.m[('A', bank, s)][l]
            out.append(None if w is None else (w >> (8 * (k & 3))) & 0xFF)
        return out, subs

    def b_read(self, bank, k, j0):
        P = self.P; Q = P // 4
        subs, out = [], []
        for s in range(Q):
            l = (k << (3 - lg(Q))) | ((j0 >> 2) >> lg(Q))
            subs.append(s)
            w = self.m[('B', bank, s)][l]
            for e in range(4):
                out.append(None if w is None else (w >> (8 * e)) & 0xFF)
        return out, subs

    def bias_read(self, bank, j0):
        P = self.P
        return [self.m[('BIAS', bank, c)][j0 >> lg(P)] for c in range(P)], list(range(P))

    def c_write(self, bank, fmt, i, j0, data, mask):
        P = self.P; Q = P // 4
        subs = []
        if fmt == 0:
            for c in range(P):
                if not mask[c]: continue
                a = (i << 5) | (j0 + c)
                s, l = map_c(a, P)
                assert s == c
                subs.append(s)
                self.m[('C', bank, s)][l] = data[c]
        else:
            base = j0 >> 2
            for s in range(P):
                w = (s - base) % P            # word thứ w của đoạn hàng rơi vào sub-bank s
                if w >= Q: continue
                a = (i << 3) | (base + w)
                s2, l = map_c(a, P)
                assert s2 == s
                old = self.m[('C', bank, s)][l] or 0
                for e in range(4):
                    c = 4 * w + e
                    if mask[c]:
                        old = (old & ~(0xFF << 8 * e)) | ((data[c] & 0xFF) << 8 * e)
                subs.append(s)
                self.m[('C', bank, s)][l] = old
        return subs


if __name__ == '__main__':
    rng = random.Random(5)
    n = 0
    for P in (4, 8):
        for buf, f in MAPS.items():
            cells = {f(a, P) for a in range(SIZE[buf])}
            assert len(cells) == SIZE[buf]
            assert all(0 <= s < NSUB(P)[buf] and 0 <= l < DEPTH(P)[buf] for s, l in cells)
        for NB in (1, 2):
            for trial in range(60):
                M = rng.randint(1, 32); N = rng.randint(1, 8) * 4; K = rng.randint(1, 8) * 4
                sr = Sram(P, NB)
                bank = rng.randrange(NB)
                A = [[rng.randint(0, 255) for _ in range(K)] for _ in range(M)]
                B = [[rng.randint(0, 255) for _ in range(N)] for _ in range(K)]
                bias = [rng.randint(0, 2**32 - 1) for _ in range(N)]
                for i in range(M):                     # DMA LOAD_A: word {i, kw}
                    for kw in range(K // 4):
                        sr.dma_write('A', bank, (i << 3) | kw, sum(A[i][4 * kw + e] << 8 * e for e in range(4)))
                for k in range(K):
                    for jw in range(N // 4):
                        sr.dma_write('B', bank, (k << 3) | jw, sum(B[k][4 * jw + e] << 8 * e for e in range(4)))
                for j in range(N):
                    sr.dma_write('BIAS', bank, j, bias[j])
                for i0 in range(0, M, P):
                    for k in range(K):
                        v, subs = sr.a_read(bank, i0, k)
                        assert len(set(subs)) == len(subs)
                        for r in range(P):
                            if i0 + r < M: assert v[r] == A[i0 + r][k]
                for k in range(K):
                    for j0 in range(0, N, P):
                        v, subs = sr.b_read(bank, k, j0)
                        assert len(set(subs)) == len(subs)
                        for c in range(P):
                            if j0 + c < N: assert v[c] == B[k][j0 + c]
                for j0 in range(0, N, P):
                    v, _ = sr.bias_read(bank, j0)
                    for c in range(P):
                        if j0 + c < N: assert v[c] == bias[j0 + c]
                for fmt in (0, 1):
                    Cm = [[rng.randint(0, 2**32 - 1) if fmt == 0 else rng.randint(0, 255)
                           for _ in range(N)] for _ in range(M)]
                    for i in range(M):
                        for j0 in range(0, N, P):
                            mask = [1 if j0 + c < N else 0 for c in range(P)]
                            subs = sr.c_write(bank, fmt, i, j0, [Cm[i][j0 + c] if mask[c] else 0 for c in range(P)], mask)
                            assert len(set(subs)) == len(subs)
                    for i in range(M):
                        if fmt == 0:
                            for j in range(N): assert sr.dma_read_c(bank, (i << 5) | j) == Cm[i][j]
                        else:
                            for jw in range(N // 4):
                                w = sr.dma_read_c(bank, (i << 3) | jw)
                                assert w == sum(Cm[i][4 * jw + e] << 8 * e for e in range(4))
                n += 1
    print("SRAM: song ánh và không xung đột sub-bank; %d cấu hình nạp/đọc/ghi khớp" % n)
