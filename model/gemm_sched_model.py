"""Mô hình tham chiếu của bộ lập lịch trong gemm_main_fsm (chế độ đơn, chuỗi, ping-pong).

Mô hình chạy theo chu kỳ, đúng các quy tắc của spec FSM:
  * ba engine Đọc / Tính / Ghi, slot "đã nạp" 1 mục giữa Đọc và Tính,
    Tính giữ job ở trạng thái HAND tới khi Ghi nhận;
  * chọn bank theo bảng 7-4; bộ đếm rcnt[A|B|BIAS][bank], wcnt[C][bank];
  * NB = 1 (không ping-pong): mọi pha dùng bus/SRAM loại trừ nhau, ưu tiên Ghi > Tính > Đọc;
  * WAIT_PREV, REUSE_B, LAST, bản ghi lỗi giữ descriptor nhỏ nhất (DSC-08).
Dữ liệu được mô hình thật (DRAM theo byte, bank SRAM theo phần tử): mọi bên đọc
lấy dữ liệu ở đầu và cuối pha và phải thấy giống nhau, nên mọi ghi đè sai bank bị phát hiện.
Kết quả DRAM được so với thực thi tuần tự từng descriptor.
Chạy:  python3 gemm_sched_model.py
"""
import random

ERR_CFG, ERR_RD, ERR_WR, ERR_FETCH = 1, 2, 3, 4


def s8(x):  return ((x + 128) & 0xFF) - 128
def s32(x): return ((x + 2**31) & (2**32 - 1)) - 2**31


def post(c, b, m0, sh, relu):
    acc = s32(c + b)
    y = (acc * m0 + (1 << (30 + sh))) >> (31 + sh)
    if relu: y = max(y, 0)
    return min(max(y, -128), 127)


# ------------------------------------------------------------------ DRAM và descriptor
class Dram:
    def __init__(self): self.b = {}
    def rd8(self, a): return s8(self.b.get(a, 0))
    def wr8(self, a, v): self.b[a] = v & 0xFF
    def rd32(self, a): return s32(sum(self.b.get(a + e, 0) << 8 * e for e in range(4)))
    def wr32(self, a, v):
        for e in range(4): self.b[a + e] = (v >> 8 * e) & 0xFF


def eff(j):
    lda = j['LDA'] or j['K']; ldb = j['LDB'] or j['N']
    ldc = j['LDC'] or (j['N'] if j['POST'] else 4 * j['N'])
    return lda, ldb, ldc


def rd_A(dr, j):
    lda, _, _ = eff(j)
    return [[dr.rd8(j['A'] + i * lda + k) for k in range(j['K'])] for i in range(j['M'])]


def rd_B(dr, j):
    _, ldb, _ = eff(j)
    return [[dr.rd8(j['B'] + k * ldb + n) for n in range(j['N'])] for k in range(j['K'])]


def rd_bias(dr, j): return [dr.rd32(j['BIAS'] + 4 * n) for n in range(j['N'])]


def gemm(A, B, bias, j):
    C = [[s32(sum(A[i][k] * B[k][n] for k in range(j['K']))) for n in range(j['N'])] for i in range(j['M'])]
    if j['POST']:
        C = [[post(C[i][n], bias[n], j['QM0'], j['QSH'], j['RELU']) for n in range(j['N'])] for i in range(j['M'])]
    return C


def wr_C(dr, j, C):
    _, _, ldc = eff(j)
    for i in range(j['M']):
        for n in range(j['N']):
            if j['POST']: dr.wr8(j['C'] + i * ldc + n, C[i][n])
            else: dr.wr32(j['C'] + i * ldc + 4 * n, C[i][n])


def desc_valid(j, first, prev):
    """DSC-03 + NEXT_PTR căn 64 byte (khi LAST = 0)."""
    ok = 1 <= j['M'] <= 32 and j['N'] in range(4, 33, 4) and j['K'] in range(4, 33, 4)
    ok &= j['RSV'] == 0
    for f in ('A', 'C'): ok &= j[f] % 4 == 0
    if not j['REUSE']: ok &= j['B'] % 4 == 0
    if j['POST']: ok &= j['BIAS'] % 4 == 0
    lc = j['N'] if j['POST'] else 4 * j['N']
    for s, L in ((j['LDA'], j['K']), (j['LDB'], j['N']), (j['LDC'], lc)):
        ok &= s == 0 or (s >= L and s % 4 == 0)
    ok &= (not j['RELU']) or j['POST']
    if j['REUSE']: ok &= (not first) and prev is not None and prev == (j['K'], j['N'])
    if not j['LAST']: ok &= j['NEXT'] % 64 == 0
    return bool(ok)


# ------------------------------------------------------------------ bộ lập lịch
class Sched:
    def __init__(self, NB, chain, descs, dram, rng, fail=None, dur=None):
        self.NB, self.chain, self.descs, self.dr, self.rng = NB, chain, descs, dram, rng
        self.fail = fail or {}                    # (idx, phase) -> True
        self.dur = dur or (lambda ph: rng.randint(1, 40))
        self.sram = {}                            # (buf, bank) -> dữ liệu
        self.rcnt = {(x, b): 0 for x in ('A', 'B', 'BIAS') for b in range(NB)}
        self.wcnt = {b: 0 for b in range(NB)}
        self.nxt = dict(A=0, C=0, BIAS=0, B=0); self.prev_b = 0
        self.err = None                           # (idx, code, addr)
        self.done_cnt = 0
        self.r = dict(st='START', idx=0, job=None, first=True, prev=None, ptr=descs[0]['ADDR'])
        self.slot = None
        self.c = dict(st='IDLE', job=None)
        self.s = dict(st='IDLE', job=None)
        self.rd_ch = None; self.wr_ch = None      # (còn lại, phase, idx, payload)
        self.c_run = None
        self.t = 0
        self.finished = None
        self.phases = []                          # (bắt đầu, kết thúc, phase, idx) để kiểm tra
        self.open = {}
        self.perf = dict(LOAD=0, COMP=0, STORE=0, TOTAL=0)

    def blocked(self, idx):
        return self.err is not None and idx >= self.err[0]

    def record_err(self, idx, code, addr):
        if self.err is None or idx < self.err[0]:
            self.err = (idx, code, addr)

    def any_active(self):
        return self.rd_ch is not None or self.wr_ch is not None or self.c_run is not None

    # ---- điều kiện muốn bắt đầu pha (tính từ trạng thái đầu chu kỳ)
    def want_store(self):
        return (self.s['st'] == 'IDLE' and self.c['st'] == 'HAND'
                and not self.blocked(self.c['job']['idx']))

    def want_comp(self):
        j = self.slot
        return (self.c['st'] == 'IDLE' and j is not None and not self.blocked(j['idx'])
                and self.wcnt[j['bc']] == 0)

    def want_read(self):
        r = self.r
        if self.rd_ch is not None or self.blocked(r['idx']): return False
        if r['st'] == 'FETCH': return True
        if r['st'] in ('LBIAS', 'LA', 'LB'):
            buf = {'LBIAS': 'BIAS', 'LA': 'A', 'LB': 'B'}[r['st']]
            bank = r['job']['b' + buf.lower()[0] if buf != 'BIAS' else 'bbias']
            return self.rcnt[(buf, bank)] == 0
        return False

    def start_phase(self, ph, idx):
        assert not self.blocked(idx), ("bắt đầu pha sau lỗi", ph, idx)
        self.open[(ph, idx)] = self.t

    def end_phase(self, ph, idx):
        self.phases.append((self.open.pop((ph, idx)), self.t, ph, idx))

    def step(self):
        t = self.t
        PP = self.NB == 2
        # lỗi kết thúc trong chu kỳ này chặn ngay mọi pha mới cùng chu kỳ (FSM-xx)
        if self.wr_ch and self.wr_ch[0] == 0 and self.fail.get((self.wr_ch[2], 'STORE')):
            self.record_err(self.wr_ch[2], ERR_WR, self.wr_ch[3]['ADDR'])
        if self.rd_ch and self.rd_ch[0] == 0 and self.fail.get((self.rd_ch[2], self.rd_ch[1])):
            ph = self.rd_ch[1]
            self.record_err(self.rd_ch[2], ERR_FETCH if ph == 'FETCH' else ERR_RD,
                            self.r['ptr'] if ph == 'FETCH' else self.r['job']['ADDR'])
        ws, wc, wr = self.want_store(), self.want_comp(), self.want_read()
        act = self.any_active()
        go_s = ws and (PP or not act)
        go_c = wc and (PP or (not act and not ws))
        go_r = wr and (PP or (not act and not ws and not wc))
        # bộ đếm hiệu năng
        self.perf['TOTAL'] += 1
        if self.rd_ch and self.rd_ch[1] != 'FETCH': self.perf['LOAD'] += 1
        if self.c_run: self.perf['COMP'] += 1
        if self.wr_ch: self.perf['STORE'] += 1

        # ================= Ghi
        s = self.s
        if s['st'] == 'RUN':
            rem, ph, idx, j = self.wr_ch
            if rem == 0:
                self.wr_ch = None
                self.end_phase('STORE', idx)
                assert self.sram[('C', j['bc'])] == j['_C'], "bank C bị ghi đè khi đang STORE"
                if self.fail.get((idx, 'STORE')):
                    self.record_err(idx, ERR_WR, j['ADDR'])
                else:
                    wr_C(self.dr, j, j['_C'])
                    self.wcnt[j['bc']] -= 1
                    self.done_cnt += 1
                    if j['LAST']: self.finished = ('DONE', None)
                s['st'] = 'IDLE'
            else:
                self.wr_ch = (rem - 1, ph, idx, j)
        elif go_s:
            j = self.c['job']; self.c = dict(st='IDLE', job=None)
            assert self.sram[('C', j['bc'])] == j['_C']
            s.update(st='RUN', job=j); self.start_phase('STORE', j['idx'])
            self.wr_ch = (self.dur('STORE'), 'STORE', j['idx'], j)

        # ================= Tính
        c = self.c
        if c['st'] == 'RUN':
            rem, j = self.c_run
            if rem == 0:
                self.c_run = None; self.end_phase('COMP', j['idx'])
                # đọc lại bank lúc kết thúc: phải còn nguyên
                assert self.sram[('A', j['ba'])] == j['_A'] and self.sram[('B', j['bb'])] == j['_B']
                if j['POST']: assert self.sram[('BIAS', j['bbias'])] == j['_bias']
                self.sram[('C', j['bc'])] = j['_C']
                self.rcnt[('A', j['ba'])] -= 1; self.rcnt[('B', j['bb'])] -= 1
                if j['POST']: self.rcnt[('BIAS', j['bbias'])] -= 1
                c['st'] = 'HAND'
            else:
                self.c_run = (rem - 1, j)
        elif go_c:
            j = self.slot; self.slot = None
            j['_A'] = self.sram[('A', j['ba'])]; j['_B'] = self.sram[('B', j['bb'])]
            j['_bias'] = self.sram.get(('BIAS', j['bbias'])) if j['POST'] else None
            assert j['_A'] == j['gA'] and j['_B'] == j['gB'], "dữ liệu bank sai lúc COMPUTE"
            if j['POST']: assert j['_bias'] == j['gbias']
            j['_C'] = gemm(j['_A'], j['_B'], j['_bias'], j)
            self.wcnt[j['bc']] += 1
            c.update(st='RUN', job=j); self.start_phase('COMP', j['idx'])
            self.c_run = (self.dur('COMP'), j)

        # ================= Đọc
        r = self.r
        if self.rd_ch is not None:
            rem, ph, idx, pay = self.rd_ch
            if rem == 0:
                self.rd_ch = None; self.end_phase(ph, idx)
                if ph == 'FETCH':
                    if self.fail.get((idx, 'FETCH')):
                        self.record_err(idx, ERR_FETCH, r['ptr']); r['st'] = 'STOP'
                    else:
                        r['job'] = dict(self.descs[idx]); r['st'] = 'CHECK'
                else:
                    buf, bank, data_start = pay
                    j = r['job']
                    now = {'A': rd_A, 'B': rd_B, 'BIAS': rd_bias}[buf](self.dr, j)
                    assert now == data_start, "vùng nguồn bị ghi trong lúc LOAD (thiếu WAIT_PREV?)"
                    if self.fail.get((idx, 'L' + buf)):
                        self.record_err(idx, ERR_RD, j['ADDR']); r['st'] = 'STOP'
                    else:
                        self.sram[(buf, bank)] = now
                        r['st'] = {'BIAS': 'LA', 'A': ('RB' if j['REUSE'] else 'LB'), 'B': 'PUSH'}[buf]
            else:
                self.rd_ch = (rem - 1, ph, idx, pay)
        else:
            if r['st'] not in ('STOP', 'START') and self.blocked(r['idx']):
                r['st'] = 'STOP'
            if r['st'] == 'START':
                if self.chain and self.descs[0]['ADDR'] % 64:
                    self.record_err(0, ERR_CFG, self.descs[0]['ADDR']); r['st'] = 'STOP'
                else:
                    r['st'] = 'FETCH' if self.chain else 'CHECK'
                    if not self.chain: r['job'] = dict(self.descs[0])
            elif r['st'] == 'FETCH' and go_r:
                self.start_phase('FETCH', r['idx'])
                self.rd_ch = (self.dur('FETCH'), 'FETCH', r['idx'], None)
            elif r['st'] == 'CHECK':
                j = r['job']
                if not desc_valid(j, r['first'], r['prev']):
                    self.record_err(r['idx'], ERR_CFG, j['ADDR']); r['st'] = 'STOP'
                else:
                    NB = self.NB
                    j['ba'] = self.nxt['A']; j['bc'] = self.nxt['C']
                    if NB == 2: self.nxt['A'] ^= 1; self.nxt['C'] ^= 1
                    if j['POST']:
                        j['bbias'] = self.nxt['BIAS']
                        if NB == 2: self.nxt['BIAS'] ^= 1
                    else: j['bbias'] = 0
                    if j['REUSE']: j['bb'] = self.prev_b
                    else:
                        j['bb'] = self.nxt['B']; self.prev_b = j['bb']
                        if NB == 2: self.nxt['B'] ^= 1
                    j['idx'] = r['idx']
                    j['gA'], j['gB'] = rd_A(self.dr, j), (rd_B(self.dr, j) if not j['REUSE'] else None)
                    j['gbias'] = rd_bias(self.dr, j) if j['POST'] else None
                    r['st'] = 'WP'
            elif r['st'] == 'WP':
                j = r['job']
                if not j['WAITP'] or self.done_cnt == r['idx']:
                    r['st'] = 'LBIAS' if j['POST'] else 'LA'
                    j['gA'] = rd_A(self.dr, j)
                    if not j['REUSE']: j['gB'] = rd_B(self.dr, j)
                    if j['POST']: j['gbias'] = rd_bias(self.dr, j)
            elif r['st'] in ('LBIAS', 'LA', 'LB') and go_r:
                j = r['job']
                buf = {'LBIAS': 'BIAS', 'LA': 'A', 'LB': 'B'}[r['st']]
                bank = {'BIAS': j['bbias'], 'A': j['ba'], 'B': j['bb']}[buf]
                self.rcnt[(buf, bank)] += 1
                ds = {'A': rd_A, 'B': rd_B, 'BIAS': rd_bias}[buf](self.dr, j)
                self.start_phase('L' + buf, r['idx'])
                self.rd_ch = (self.dur('L' + buf), 'L' + buf, r['idx'], (buf, bank, ds))
            if r['st'] == 'RB' and self.rd_ch is None:
                j = r['job']; self.rcnt[('B', j['bb'])] += 1
                j['gB'] = self.sram[('B', j['bb'])]
                r['st'] = 'PUSH'
            elif r['st'] == 'PUSH' and self.slot is None:
                j = r['job']
                if j['REUSE']: j['gB'] = self.sram[('B', j['bb'])]
                self.slot = j
                if j['LAST'] or not self.chain:
                    r['st'] = 'STOP'
                else:
                    r['prev'] = (j['K'], j['N']); r['first'] = False
                    r['ptr'] = j['NEXT']; r['idx'] += 1; r['st'] = 'FETCH'

        # ================= kết thúc tác vụ có lỗi
        if self.err is not None and self.finished is None:
            f = self.err[0]
            quiet = (r['st'] == 'STOP' and self.rd_ch is None and self.c_run is None
                     and not (self.slot and self.slot['idx'] < f)
                     and not (self.c['st'] == 'HAND' and self.c['job']['idx'] < f)
                     and self.s['st'] == 'IDLE')
            if quiet: self.finished = ('ERROR', self.err)
        self.t += 1

    def run(self, limit=200000):
        while self.finished is None:
            self.step()
            assert self.t < limit, "kẹt (deadlock)"
        return self.finished


# ------------------------------------------------------------------ sinh chuỗi ngẫu nhiên
def make_chain(rng, n, dram, allow_invalid=False):
    descs = []; nxt = 0x1000; free = 0x100000
    def alloc(sz):
        nonlocal free
        a = free; free += (sz + 63) // 64 * 64 + 64 * rng.randint(0, 3); return a
    prev = None
    for d in range(n):
        reuse = prev is not None and rng.random() < 0.3
        dep = prev is not None and prev['POST'] and not reuse and rng.random() < 0.4
        if reuse:
            K, N = prev['K'], prev['N']; M = rng.randint(1, 12)
        elif dep:
            M, K = prev['M'], prev['N']; N = rng.choice([4, 8, 12])
        else:
            M = rng.randint(1, 12); N = rng.choice([4, 8, 12]); K = rng.choice([4, 8, 12])
        post_en = rng.random() < 0.6
        j = dict(M=M, N=N, K=K, POST=int(post_en), RELU=int(post_en and rng.random() < 0.5),
                 REUSE=int(reuse), WAITP=int(dep or rng.random() < 0.1), LAST=int(d == n - 1),
                 QM0=rng.randint(2**30, 2**31 - 1), QSH=rng.randint(0, 8), RSV=0, ADDR=nxt)
        j['LDA'] = rng.choice([0, 0, K + 4 * rng.randint(1, 3)])
        j['LDB'] = rng.choice([0, 0, N + 4 * rng.randint(1, 3)])
        lc = N if post_en else 4 * N
        j['LDC'] = rng.choice([0, 0, lc + 4 * rng.randint(1, 3)])
        if dep:
            j['A'] = prev['C']; j['LDA'] = eff(prev)[2]
        else:
            j['A'] = alloc(M * (j['LDA'] or K))
            for i in range(M):
                for k in range(K): dram.wr8(j['A'] + i * eff(j)[0] + k, rng.randint(-128, 127))
        if reuse:
            j['B'] = 0xDEAD0001 if rng.random() < 0.5 else prev['B']; j['LDB'] = prev['LDB']
        else:
            j['B'] = alloc(K * (j['LDB'] or N))
            for k in range(K):
                for x in range(N): dram.wr8(j['B'] + k * eff(j)[1] + x, rng.randint(-128, 127))
        j['BIAS'] = alloc(4 * N)
        for x in range(N): dram.wr32(j['BIAS'] + 4 * x, rng.randint(-3000, 3000))
        j['C'] = alloc(M * (j['LDC'] or lc))
        nxt = alloc(64) if d < n - 1 else 0
        j['NEXT'] = nxt
        descs.append(j); prev = j
    if allow_invalid and rng.random() < 0.2:
        d = rng.randrange(n); bad = rng.choice(['RSV', 'LDA', 'RELU', 'NEXT', 'A'])
        if bad == 'RSV': descs[d]['RSV'] = 1
        if bad == 'LDA': descs[d]['LDA'] = descs[d]['K'] - 4 if descs[d]['K'] > 4 else 2
        if bad == 'RELU': descs[d]['RELU'] = 1; descs[d]['POST'] = 0
        if bad == 'NEXT' and not descs[d]['LAST']: descs[d]['NEXT'] += 4
        if bad == 'A': descs[d]['A'] += 2
    return descs


def sequential_ref(descs, dram, chain):
    """Thực thi tuần tự: trả (DRAM, số descriptor xong, lỗi cấu hình đầu tiên)."""
    prev = None; first = True
    for d, j in enumerate(descs):
        if not desc_valid(j, first, prev): return dram, d
        B = rd_B(dram, j) if not j['REUSE'] else lastB
        lastB = B
        C = gemm(rd_A(dram, j), B, rd_bias(dram, j) if j['POST'] else None, j)
        wr_C(dram, j, C)
        prev = (j['K'], j['N']); first = False
        if not chain: break
    return dram, len(descs)


if __name__ == '__main__':
    import copy
    rng = random.Random(11)
    stats = dict(ok=0, err=0, cfg=0)
    speed = {1: 0, 2: 0}
    overlap = [0]
    for trial in range(1200):
        n = rng.randint(1, 7)
        dram = Dram()
        descs = make_chain(rng, n, dram, allow_invalid=True)
        ref = copy.deepcopy(dram)
        ref, n_valid = sequential_ref(descs, ref, True)
        fail = {}
        if rng.random() < 0.35:
            for _ in range(rng.randint(1, 2)):
                fail[(rng.randrange(n), rng.choice(['FETCH', 'LA', 'LB', 'LBIAS', 'STORE']))] = True
        durs = {}
        seedd = rng.random()
        for NB in (1, 2):
            dr = copy.deepcopy(dram)
            rr = random.Random(seedd)
            sch = Sched(NB, True, descs, dr, rr, fail=fail,
                        dur=lambda ph, rr=rr: {'FETCH': rr.randint(3, 8), 'COMP': rr.randint(5, 60)}.get(ph, rr.randint(2, 50)))
            res = sch.run()
            ph = sorted(sch.phases)
            if NB == 1:                    # tuần tự tuyệt đối
                for a, b in zip(ph, ph[1:]): assert a[1] <= b[0], ("chồng pha khi NB=1", a, b)
            else:
                overlap[0] += sum(1 for a, b in zip(ph, ph[1:]) if a[1] > b[0])
            # Ghi theo đúng thứ tự descriptor
            st = [p[3] for p in ph if p[2] == 'STORE']
            assert st == sorted(st)
            if res[0] == 'DONE':
                assert n_valid == n and sch.done_cnt == n
                assert dr.b == ref.b, "DRAM khác thực thi tuần tự"
                stats['ok'] += 1; speed[NB] += sch.t
            else:
                f, code, addr = res[1]
                assert sch.done_cnt == f
                assert addr == descs[f]['ADDR']
                # mọi descriptor < f đã ghi kết quả đúng; không pha nào của >= f bắt đầu sau lỗi (assert trong start_phase)
                ref2 = copy.deepcopy(dram)
                prev = None
                for d in range(f):
                    j = descs[d]
                    B = rd_B(ref2, j) if not j['REUSE'] else lastB
                    lastB = B
                    wr_C(ref2, j, gemm(rd_A(ref2, j), B, rd_bias(ref2, j) if j['POST'] else None, j))
                if code == ERR_CFG: assert f == n_valid; stats['cfg'] += 1
                else: assert f <= n_valid; stats['err'] += 1
                # các vùng C của descriptor < f khớp
                for d in range(f):
                    j = descs[d]; _, _, ldc = eff(j)
                    for i in range(j['M']):
                        for x in range(j['N']):
                            if j['POST']: assert dr.rd8(j['C'] + i * ldc + x) == ref2.rd8(j['C'] + i * ldc + x)
                            else: assert dr.rd32(j['C'] + i * ldc + 4 * x) == ref2.rd32(j['C'] + i * ldc + 4 * x)
            assert sch.perf['LOAD'] + sch.perf['COMP'] + sch.perf['STORE'] >= 0
    print("lập lịch: %d chuỗi DONE (khớp tuần tự), %d lỗi AXI, %d lỗi cấu hình — NB=1 và NB=2 đều đạt" %
          (stats['ok'] // 2, stats['err'] // 2, stats['cfg'] // 2))
    print("số cặp pha chạy chồng khi NB=2: %d" % overlap[0])
    print("tổng chu kỳ các chuỗi DONE: NB=1 %d, NB=2 %d (%.2fx)" % (speed[1], speed[2], speed[1] / speed[2]))
    # chế độ đơn
    for trial in range(300):
        dram = Dram(); descs = make_chain(rng, 1, dram)
        j = descs[0]; j.update(LDA=0, LDB=0, LDC=0, REUSE=0, WAITP=0, LAST=1)
        ref = copy.deepcopy(dram); sequential_ref(descs, ref, False)
        for NB in (1, 2):
            dr = copy.deepcopy(dram); sch = Sched(NB, False, descs, dr, rng)
            assert sch.run()[0] == 'DONE' and dr.b == ref.b
            ph = sorted(sch.phases)
            for a, b in zip(ph, ph[1:]): assert a[1] <= b[0]
            assert [p[2] for p in ph] == (['LBIAS'] if j['POST'] else []) + ['LA', 'LB', 'COMP', 'STORE']
    print("chế độ đơn: 300 tác vụ, thứ tự pha LOAD_BIAS → LOAD_A → LOAD_B → COMPUTE → STORE_C, tuần tự")
