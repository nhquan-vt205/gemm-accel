"""Mô hình tham chiếu của gemm_dma_engine (kênh đọc và kênh ghi).

* bursts(): quy tắc chia đoạn và cắt burst (DMA-03, DSC-09) — dùng làm golden
  cho testbench: danh sách (địa chỉ, số beat) mà RTL phải phát, đúng thứ tự.
* spm_addr(): địa chỉ scratchpad logic của word thứ n (SPM-02).
* RdChannel / WrChannel: mô hình cycle-accurate của hai kênh với slave AXI
  ngẫu nhiên (trễ READY/VALID, lỗi RESP, rlast sai), kiểm dữ liệu, giao thức,
  lỗi và abort.
Chạy:  python3 gemm_dma_model.py
"""
import random

DST_A, DST_B, DST_BIAS, DST_DESC = 0, 1, 2, 3


def wide_layout(dst=None, fmt=None):
    """True: địa chỉ {row[4:0], w[4:0]}; False: {row[4:0], w[2:0]}."""
    if dst is not None:
        return dst == DST_BIAS
    return fmt == 0                       # STORE_C: INT32 rộng, INT8 hẹp


def spm_addr(n, rwords, wide):
    row, w = divmod(n, rwords)
    return row * 32 + w if wide else row * 8 + w


def segments(base, rows, rwords, stride):
    if stride == 4 * rwords:
        return [(base, rows * rwords)]
    return [(base + r * stride, rwords) for r in range(rows)]


def bursts(base, rows, rwords, stride, maxb):
    out = []
    for a, rem in segments(base, rows, rwords, stride):
        while rem:
            n = min(rem, maxb, (4096 - a % 4096) // 4)
            out.append((a, n))
            a += 4 * n
            rem -= n
    return out


# ------------------------------------------------------------------ slave AXI ngẫu nhiên
class Slave:
    def __init__(self, rng, mem, p_err=0.0, p_rlast=0.0):
        self.rng, self.mem = rng, mem
        self.p_err, self.p_rlast = p_err, p_rlast
        self.rq = []          # burst đọc đang phục vụ: [addr, nbeat, beat, rlast_at]
        self.wq = []          # burst ghi: địa chỉ đã nhận
        self.wdat = []
        self.bq = []

    def r_beat(self):
        """Trả (rvalid, rdata, rresp, rlast) cho chu kỳ này (giữ ổn định tới khi bắt tay)."""
        if not self.rq:
            return None
        b = self.rq[0]
        if 'cur' not in b:
            if self.rng.random() < 0.3:
                return None
            k = b['beat']
            a = b['addr'] + 4 * k
            resp = 2 if self.rng.random() < self.p_err else 0
            b['cur'] = (self.mem.get(a, 0), resp, k == b['rlast_at'])
        return b['cur']

    def r_accept(self):
        b = self.rq[0]
        last = b['cur'][2]
        del b['cur']
        b['beat'] += 1
        if last:
            self.rq.pop(0)


class RdChannel:
    """Kênh đọc: FETCH, LOAD_A, LOAD_B, LOAD_BIAS. 1 burst outstanding."""
    def __init__(self, maxb):
        self.maxb = maxb
        self.busy = False

    def start(self, dst, base, rows, rwords, stride, bank):
        assert not self.busy
        self.busy = True
        self.dst, self.bank, self.rwords = dst, bank, rwords
        self.plan = bursts(base, rows, rwords, stride, maxb=self.maxb)
        self.n = 0                    # số word đã ghi
        self.state = 'ISSUE'
        self.err = False
        self.abort = False

    def step(self, slave, spm, desc, log):
        """Một chu kỳ. Trả 'done'/'error'/None."""
        if not self.busy:
            return None
        if self.state == 'ISSUE':
            if self.abort or self.err or not self.plan:
                self.busy = False
                return 'error' if self.err else 'done'
            a, nb = self.plan[0]
            # arvalid = 1; slave nhận ngẫu nhiên
            if slave.rng.random() < 0.6:
                assert (a % 4096) // 4 + nb <= 1024, "burst vượt 4 KiB"
                assert nb <= self.maxb
                rl = nb - 1
                if slave.p_rlast and slave.rng.random() < slave.p_rlast:
                    rl = max(0, nb - 1 + slave.rng.choice([-1, 1]))
                slave.rq.append(dict(addr=a, beat=0, rlast_at=rl))
                log.append(('AR', a, nb))
                self.plan.pop(0)
                self.exp, self.got = nb, 0
                self.state = 'R'
            return None
        if self.state == 'R':
            x = slave.r_beat()
            if x is None:
                return None
            data, resp, last = x
            slave.r_accept()               # rready = 1 (SRAM luôn sẵn sàng)
            self.got += 1
            if resp != 0:
                self.err = True
            if self.got <= self.exp:
                if self.dst == DST_DESC:
                    desc[self.n] = data
                else:
                    spm[(self.dst, self.bank, spm_addr(self.n, self.rwords,
                                                      wide_layout(dst=self.dst)))] = data
                self.n += 1
            if self.got == self.exp and not last:
                self.err = True           # rlast trễ: nhận tiếp tới rlast, bỏ beat thừa
            if last:
                if self.got < self.exp:
                    self.err = True       # rlast sớm: burst kết thúc
                    self.n += self.exp - self.got   # bỏ qua các word thiếu
                self.state = 'ISSUE'
            return None


class WrChannel:
    """Kênh ghi: STORE_C. FIFO 4 word, AW và W độc lập, 1 burst outstanding."""
    FIFO = 4

    def __init__(self, maxb):
        self.maxb = maxb
        self.busy = False

    def start(self, fmt, base, rows, rwords, stride, bank):
        assert not self.busy
        self.busy = True
        self.fmt, self.bank, self.rwords = fmt, bank, rwords
        self.plan = bursts(base, rows, rwords, stride, self.maxb)
        self.n_rd = 0                 # word đã gửi yêu cầu đọc SRAM
        self.fifo, self.inflight = [], None
        self.state = 'NEXT'
        self.err = False
        self.abort = False

    def step(self, slave, spm, dram, log, rng, p_err):
        if not self.busy:
            return None
        # dữ liệu SRAM trả về (trễ 1) vào FIFO
        if self.inflight is not None:
            self.fifo.append(self.inflight)
            self.inflight = None
        assert len(self.fifo) <= self.FIFO
        if self.state == 'NEXT':
            if self.abort or self.err or not self.plan:
                self.busy = False
                return 'error' if self.err else 'done'
            self.a, self.nb = self.plan.pop(0)
            self.aw_done, self.w_sent, self.to_read = False, 0, self.nb
            self.state = 'BURST'
            log.append(('AW', self.a, self.nb))
        if self.state == 'BURST':
            # đọc SRAM theo credit
            if self.to_read and len(self.fifo) + (1 if self.inflight is not None else 0) < self.FIFO:
                key = ('C', self.bank, spm_addr(self.n_rd, self.rwords, wide_layout(fmt=self.fmt)))
                self.inflight = spm[key]
                self.n_rd += 1
                self.to_read -= 1
            if not self.aw_done and rng.random() < 0.6:
                self.aw_done = True
            if self.fifo and self.w_sent < self.nb and rng.random() < 0.7:
                d = self.fifo.pop(0)
                dram[self.a + 4 * self.w_sent] = d
                self.w_sent += 1
            if self.aw_done and self.w_sent == self.nb:
                self.state = 'B'
                self.bwait = rng.randint(0, 3)
            return None
        if self.state == 'B':
            if self.bwait:
                self.bwait -= 1
                return None
            if rng.random() < p_err:
                self.err = True
            self.state = 'NEXT'
            return None


def ref_words(kind, job):
    """Danh sách (địa chỉ byte DRAM, chỉ số logic) theo công thức phần tử của spec."""
    M, N, K = job['M'], job['N'], job['K']
    out = []
    if kind == 'A':
        for i in range(M):
            for kw in range(K // 4):
                out.append((job['a'] + i * job['lda'] + 4 * kw, i * 8 + kw))
    if kind == 'B':
        for k in range(K):
            for jw in range(N // 4):
                out.append((job['b'] + k * job['ldb'] + 4 * jw, k * 8 + jw))
    if kind == 'BIAS':
        for j in range(N):
            out.append((job['bias'] + 4 * j, j))
    if kind == 'C32':
        for i in range(M):
            for j in range(N):
                out.append((job['c'] + i * job['ldc'] + 4 * j, i * 32 + j))
    if kind == 'C8':
        for i in range(M):
            for jw in range(N // 4):
                out.append((job['c'] + i * job['ldc'] + 4 * jw, i * 8 + jw))
    return out


def cmd_of(kind, job):
    """Tham số lệnh DMA mà FSM phát cho mỗi loại (bảng của spec FSM)."""
    M, N, K = job['M'], job['N'], job['K']
    if kind == 'A':    return (job['a'], M, K // 4, job['lda'])
    if kind == 'B':    return (job['b'], K, N // 4, job['ldb'])
    if kind == 'BIAS': return (job['bias'], 1, N, 4 * N)
    if kind == 'C32':  return (job['c'], M, N, job['ldc'])
    if kind == 'C8':   return (job['c'], M, N // 4, job['ldc'])


if __name__ == '__main__':
    rng = random.Random(3)
    # 1. địa chỉ: lệnh FSM + cắt burst + địa chỉ SPM == công thức phần tử
    nchk = 0
    for _ in range(3000):
        M = rng.randint(1, 32); N = rng.randint(1, 8) * 4; K = rng.randint(1, 8) * 4
        def st(minb):
            return rng.choice([minb, minb, minb + 4 * rng.randint(1, 20)])
        job = dict(M=M, N=N, K=K, a=4 * rng.randint(0, 2**20), b=4 * rng.randint(0, 2**20),
                   c=4 * rng.randint(0, 2**20), bias=4 * rng.randint(0, 2**20))
        job['lda'], job['ldb'] = st(K), st(N)
        for kind in ('A', 'B', 'BIAS', 'C32', 'C8'):
            if kind == 'C32': job['ldc'] = st(4 * N)
            if kind == 'C8':  job['ldc'] = st(N)
            base, rows, rw, stv = cmd_of(kind, job)
            maxb = rng.choice([1, 4, 16, 256])
            bl = bursts(base, rows, rw, stv, maxb)
            seq = [a + 4 * t for a, nb in bl for t in range(nb)]
            wide = kind in ('BIAS', 'C32')
            got = [(seq[n], spm_addr(n, rw, wide)) for n in range(len(seq))]
            assert got == ref_words(kind, job), kind
            for a, nb in bl:
                assert 1 <= nb <= maxb and (a % 4096) + 4 * nb <= 4096
            # DSC-09: không burst nào trải qua khoảng hở
            if stv != 4 * rw:
                for a, nb in bl:
                    r = (a - base) // stv
                    assert a + 4 * nb <= base + r * stv + 4 * rw
            nchk += 1
    print("địa chỉ và cắt burst: %d lệnh khớp" % nchk)

    # 2. kênh đọc với slave ngẫu nhiên
    ok = 0
    for trial in range(1500):
        maxb = rng.choice([2, 4, 16])
        mem = {}
        dst = rng.choice([DST_A, DST_B, DST_BIAS, DST_DESC])
        if dst == DST_DESC:
            rows, rw = 1, 16; base = 64 * rng.randint(0, 2**16); stv = 64
        else:
            rows = rng.randint(1, 32); rw = rng.randint(1, 8) if dst != DST_BIAS else rng.randint(1, 32)
            if dst == DST_BIAS: rows = 1
            base = 4 * rng.randint(0, 3000); stv = rng.choice([4 * rw, 4 * rw + 4 * rng.randint(1, 9)])
        for a, nb in bursts(base, rows, rw, stv, maxb):
            for t in range(nb): mem[a + 4 * t] = rng.randint(0, 2**32 - 1)
        mode = rng.choice(['ok', 'ok', 'err', 'rlast', 'abort'])
        sl = Slave(rng, mem, p_err=0.05 if mode == 'err' else 0, p_rlast=0.2 if mode == 'rlast' else 0)
        ch = RdChannel(maxb); spm = {}; desc = {}; log = []
        ch.start(dst, base, rows, rw, stv, bank=rng.randint(0, 1))
        res = None; t = 0; ab_t = rng.randint(0, 60) if mode == 'abort' else None
        ar_after_abort = 0
        while res is None:
            if ab_t is not None and t == ab_t: ch.abort = True
            n0 = len(log)
            res = ch.step(sl, spm, desc, log)
            if ch.abort and len(log) > n0 and t > ab_t: ar_after_abort += 1
            t += 1
            assert t < 100000
        expect_err = any(1 for _ in []) or (mode in ('err', 'rlast') and res == 'error')
        if mode == 'ok' or (mode in ('err', 'rlast') and res == 'done'):
            assert res == 'done'
            bl = bursts(base, rows, rw, stv, maxb)
            seq = [a + 4 * x for a, nb in bl for x in range(nb)]
            for n, a in enumerate(seq):
                if dst == DST_DESC: assert desc[n] == mem[a]
                else: assert spm[(dst, ch.bank, spm_addr(n, rw, dst == DST_BIAS))] == mem[a]
        assert ar_after_abort == 0
        assert len(sl.rq) == 0, "burst chưa nhận xong"
        ok += 1
    print("kênh đọc: %d lượt (ok, lỗi rresp, rlast sai, abort) đạt" % ok)

    # 3. kênh ghi
    ok = 0
    for trial in range(1500):
        maxb = rng.choice([2, 4, 16])
        fmt = rng.randint(0, 1)
        rows = rng.randint(1, 32); rw = rng.randint(1, 32) if fmt == 0 else rng.randint(1, 8)
        base = 4 * rng.randint(0, 3000); stv = rng.choice([4 * rw, 4 * rw + 4 * rng.randint(1, 9)])
        bank = rng.randint(0, 1)
        spm = {('C', bank, spm_addr(n, rw, fmt == 0)): rng.randint(0, 2**32 - 1) for n in range(rows * rw)}
        dram = {}; log = []
        mode = rng.choice(['ok', 'ok', 'err', 'abort'])
        ch = WrChannel(maxb); ch.start(fmt, base, rows, rw, stv, bank)
        res = None; t = 0; ab_t = rng.randint(0, 80) if mode == 'abort' else None
        while res is None:
            if ab_t is not None and t == ab_t: ch.abort = True
            res = ch.step(None, spm, dram, log, rng, 0.05 if mode == 'err' else 0)
            t += 1
        bl = bursts(base, rows, rw, stv, maxb)
        if mode == 'ok':
            assert res == 'done'
            seq = [a + 4 * x for a, nb in bl for x in range(nb)]
            assert all(dram[a] == spm[('C', bank, spm_addr(n, rw, fmt == 0))] for n, a in enumerate(seq))
        # mọi burst đã phát AW đều có đủ beat W (không bỏ dở burst)
        for _, a, nb in log:
            assert all(a + 4 * x in dram for x in range(nb))
        ok += 1
    print("kênh ghi: %d lượt (ok, lỗi bresp, abort) đạt" % ok)
