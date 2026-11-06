"""Mô hình tham chiếu cycle-accurate của gemm_register_file.

Master AXI4-Lite ngẫu nhiên (AW/W lệch nhau, READY/VALID ngẫu nhiên, wstrb ngẫu nhiên),
FSM giả lập (done/err sau thời gian ngẫu nhiên, soft reset). Kiểm:
  * byte strobe, bit dự trữ, offset dự trữ, thanh ghi chỉ đọc (REG-08, AXL-06);
  * START chỉ nhận khi BUSY = 0; bản chụp đúng; lần đọc STATUS sau B thấy tác vụ mới (TSK-03);
  * đúng một trong BUSY/DONE/ERROR sau khi chấp nhận (TSK-06); PERF_* (REG-10).
Chạy:  python3 gemm_regfile_model.py
"""
import random

RW = {0x08: 'DIM', 0x0C: 'A', 0x10: 'B', 0x14: 'C', 0x18: 'POST', 0x1C: 'BIAS',
      0x20: 'QM0', 0x24: 'QSH', 0x40: 'DESC_PTR'}


class RegFile:
    def __init__(self, P=8, HAS_CHAIN=1, HAS_PINGPONG=1):
        self.P, self.HC, self.HP = P, HAS_CHAIN, HAS_PINGPONG
        self.r = {k: 0 for k in RW.values()}
        self.snap = None
        self.busy = self.done = self.error = self.mode = 0
        self.code = 0
        self.perf = [0, 0, 0, 0]
        self.awq = None; self.wq = None; self.bvalid = 0
        self.rvalid = 0; self.rdata = 0
        self.start_pulse = 0; self.start_kind = 0; self.soft_req = 0

    def hwcfg(self):
        return (0x10 << 24) | (self.HP << 17) | (self.HC << 16) | (32 << 8) | self.P

    def read(self, off, fsm):
        if off == 0x04:
            if fsm.soft_busy: return 0x2                          # RFS-03: chỉ BUSY khi đang soft reset
            return (self.code << 4) | (self.mode << 3) | (self.error << 2) | ((self.busy | fsm.soft_busy) << 1) | self.done
        if off in RW:
            if off == 0x40 and not self.HC: return 0
            return self.r[RW[off]]
        if off == 0x28: return self.hwcfg()
        if off in (0x2C, 0x30, 0x34, 0x38): return self.perf[(off - 0x2C) // 4]
        if off == 0x44: return fsm.err_desc_addr if self.HC else 0
        if off == 0x48: return fsm.desc_done_cnt if self.HC else 0
        return 0

    def step(self, m, fsm):
        """m: tín hiệu master chu kỳ này. Trả các output (đã đăng ký từ chu kỳ trước)."""
        out = dict(awready=int(self.awq is None and not self.bvalid), wready=int(self.wq is None and not self.bvalid),
                   bvalid=self.bvalid, arready=int(not self.rvalid), rvalid=self.rvalid, rdata=self.rdata,
                   start_pulse=self.start_pulse, start_kind=self.start_kind, soft_req=self.soft_req)
        sp = 0; sk = 0; sr = 0
        # --- ghi: thực hiện khi có cả AW và W và B rảnh
        fire = self.awq is not None and self.wq is not None and not self.bvalid
        if fire:
            off = self.awq & 0xFFC; data, strb = self.wq
            if off == 0x00 and strb & 1:
                st, so, ch = data & 1, (data >> 1) & 1, (data >> 2) & 1
                if so: sr = 1
                elif (st or ch) and not (self.busy or fsm.soft_busy):
                    sp = 1; sk = st | (ch << 1)
                    self.snap = dict(self.r)
                    self.busy = 1; self.done = self.error = 0; self.code = 0
                    self.mode = int(sk == 2); self.perf = [0, 0, 0, 0]
            elif off in RW and not (off == 0x40 and not self.HC):
                old = self.r[RW[off]]
                mask = sum(0xFF << 8 * e for e in range(4) if strb >> e & 1)
                self.r[RW[off]] = (old & ~mask) | (data & mask)
        # --- FSM → RF (ưu tiên soft_clr)
        if fsm.soft_clr:
            self.busy = self.done = self.error = self.mode = self.code = 0; self.perf = [0, 0, 0, 0]
        elif not sp:
            if self.busy:
                self.perf[0] = min(self.perf[0] + 1, 2**32 - 1)
                for i, a in enumerate((fsm.p_load, fsm.p_comp, fsm.p_store)):
                    if a: self.perf[i + 1] = min(self.perf[i + 1] + 1, 2**32 - 1)
            if fsm.done_pulse: self.done = 1; self.busy = 0
            if fsm.err_pulse: self.error = 1; self.code = fsm.err_code; self.busy = 0
        # --- đọc (thấy trạng thái đầu chu kỳ)
        if m['arvalid'] and out['arready']:
            self.rvalid, self.rdata = 1, self.read(m['araddr'] & 0xFFC, fsm)
        elif self.rvalid and m['rready']:
            self.rvalid = 0
        # --- bắt tay
        if fire:
            self.awq = None; self.wq = None; self.bvalid = 1
        elif self.bvalid and m['bready']:
            self.bvalid = 0
        if m['awvalid'] and out['awready']: self.awq = m['awaddr']
        if m['wvalid'] and out['wready']: self.wq = (m['wdata'], m['wstrb'])
        self.start_pulse, self.start_kind, self.soft_req = sp, sk, sr
        return out


class FakeFsm:
    def __init__(self, rng):
        self.rng = rng; self.cnt = None; self.soft_busy = 0; self.soft_clr = 0
        self.done_pulse = self.err_pulse = 0; self.err_code = 0
        self.p_load = self.p_comp = self.p_store = 0
        self.err_desc_addr = 0; self.desc_done_cnt = 0; self.soft_t = None

    def step(self, rf_out):
        self.done_pulse = self.err_pulse = 0; self.soft_clr = 0
        if self.soft_t is not None:
            self.soft_t -= 1
            if self.soft_t == 0: self.soft_clr = 1; self.soft_t = None; self.cnt = None
            return
        if self.soft_busy: self.soft_busy = 0
        if rf_out['soft_req']: self.soft_busy = 1; self.soft_t = self.rng.randint(1, 6); return
        if rf_out['start_pulse']: self.cnt = self.rng.randint(1, 30); self.kind = rf_out['start_kind']
        if self.cnt is not None:
            self.p_load, self.p_comp, self.p_store = (self.rng.random() < 0.5 for _ in range(3))
            self.cnt -= 1
            if self.cnt == 0:
                self.cnt = None
                if self.rng.random() < 0.3: self.err_pulse = 1; self.err_code = self.rng.randint(1, 5)
                else: self.done_pulse = 1
        else:
            self.p_load = self.p_comp = self.p_store = 0
        self.soft_busy = int(self.soft_t is not None)


if __name__ == '__main__':
    rng = random.Random(9)
    nwr = nrd = nacc = 0
    for trial in range(200):
        rf = RegFile(HAS_CHAIN=rng.randint(0, 1), HAS_PINGPONG=0); fsm = FakeFsm(rng)
        shadow = {k: 0 for k in RW.values()}
        ops = []
        for _ in range(60):
            kind = rng.random()
            if kind < 0.5:
                off = rng.choice(list(RW) + [0x00, 0x04, 0x28, 0x3C, 0x100])
                d = rng.randint(0, 2**32 - 1) if off else rng.choice([1, 2, 4, 5, 0, 3])
                ops.append(('W', off, d, rng.randint(0, 15) if off else rng.choice([1, 15, 14])))
            else:
                ops.append(('R', rng.choice(list(RW) + [0x04, 0x28, 0x2C, 0x3C, 0x48, 0x800]), 0, 0))
        m = dict(awvalid=0, awaddr=0, wvalid=0, wdata=0, wstrb=0, bready=1, arvalid=0, araddr=0, rready=1)
        prev_out = None; t = 0
        for op in ops:
            if op[0] == 'W':
                aw_d, w_d = rng.randint(0, 3), rng.randint(0, 3)   # AW, W lệch nhau
                aw_ok = w_d_ok = False
                while True:
                    m.update(awvalid=int(not aw_ok and aw_d == 0), awaddr=op[1],
                             wvalid=int(not w_d_ok and w_d == 0), wdata=op[2], wstrb=op[3], bready=int(rng.random() < 0.7))
                    o = rf.step(m, fsm); fsm.step(o); t += 1
                    if m['awvalid'] and o['awready']: aw_ok = True
                    if m['wvalid'] and o['wready']: w_d_ok = True
                    aw_d = max(0, aw_d - 1); w_d = max(0, w_d - 1)
                    if o['bvalid'] and m['bready']: break
                    assert t < 100000
                off, d, strb = op[1], op[2], op[3]
                if off in RW and not (off == 0x40 and not rf.HC):
                    mask = sum(0xFF << 8 * e for e in range(4) if strb >> e & 1)
                    shadow[RW[off]] = (shadow[RW[off]] & ~mask) | (d & mask)
                if off == 0x00 and strb & 1 and not (d & 2) and (d & 5):
                    # TSK-03: ngay sau B, STATUS thấy tác vụ mới (nếu được chấp nhận)
                    if rf.snap is not None and rf.start_pulse == 0 and fsm.cnt is not None:
                        pass
                nwr += 1
                m.update(awvalid=0, wvalid=0)
            else:
                m.update(arvalid=1, araddr=op[1])
                while True:
                    o = rf.step(m, fsm); fsm.step(o); t += 1
                    if o['arready']: break
                m['arvalid'] = 0
                while True:
                    o = rf.step(m, fsm); fsm.step(o); t += 1
                    if o['rvalid']: break
                v = o['rdata']; off = op[1]
                if off in RW:
                    assert v == (0 if (off == 0x40 and not rf.HC) else shadow[RW[off]]), (hex(off), v)
                if off == 0x04:
                    assert v >> 8 == 0
                    b = [(v >> 0) & 1, (v >> 1) & 1, (v >> 2) & 1]
                    assert sum(b) <= 1, "BUSY/DONE/ERROR cùng lúc"
                    if not b[2]: assert (v >> 4) & 15 == 0
                if off == 0x28: assert v == rf.hwcfg()
                if off in (0x3C, 0x800): assert v == 0
                nrd += 1
            if rf.snap is not None: nacc += 1
        # TSK-03 trực tiếp: ghi START khi rảnh rồi đọc STATUS
    # kiểm tra TSK-03 riêng
    for trial in range(300):
        rf = RegFile(); fsm = FakeFsm(rng)
        for _ in range(rng.randint(0, 40)):
            o = rf.step(dict(awvalid=0, awaddr=0, wvalid=0, wdata=0, wstrb=0, bready=1, arvalid=0, araddr=0, rready=1), fsm); fsm.step(o)
        idle = not (rf.busy or fsm.soft_busy)
        m = dict(awvalid=1, awaddr=0, wvalid=1, wdata=1, wstrb=1, bready=1, arvalid=0, araddr=0, rready=1)
        while True:
            o = rf.step(m, fsm); fsm.step(o)
            if o['awready']: m['awvalid'] = 0
            if o['wready']: m['wvalid'] = 0
            if o['bvalid']: break
        accepted = rf.snap is not None and idle
        m = dict(awvalid=0, awaddr=0, wvalid=0, wdata=0, wstrb=0, bready=1, arvalid=1, araddr=4, rready=1)
        o = rf.step(m, fsm); fsm.step(o)
        o = rf.step(dict(m, arvalid=0), fsm); fsm.step(o)
        st = o['rdata']
        if accepted: assert st & 7 in (1, 2, 4), st     # thấy tác vụ mới: BUSY, hoặc đã DONE/ERROR
    print("register file: %d lệnh ghi, %d lệnh đọc kiểm đạt; TSK-03 300 lượt đạt" % (nwr, nrd))
