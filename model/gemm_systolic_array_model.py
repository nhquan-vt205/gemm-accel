"""Mô hình tham chiếu cycle-accurate của gemm_systolic_array.

Mô hình đúng vi kiến trúc trong spec module (bộ tuần tự tile, làm lệch,
lưới PE có first/last/res, khối xả kích hoạt bởi o_last của cột cuối,
FIFO metadata, độ trễ VPU). Dùng để:
  * kiểm tra kết quả và thời điểm pe_done của RTL (predict());
  * sinh vector kiểm thử cho testbench.
Chu kỳ 0 là chu kỳ có pe_start = 1.
Chạy:  python3 gemm_systolic_array_model.py
"""
import random, math
import numpy as np

def run(A, B, M, N, K, P, L_VPU=0, seed=0):
    rnd = random.Random(seed)
    I = max(K, P)
    TM, TN = -(-M // P), -(-N // P)
    NT = TM * TN
    # ---- trạng thái thanh ghi
    seq = dict(busy=False, ti=0, tj=0, k=0, cnt=0, tile=0)
    sram_a = None; sram_b = None              # dữ liệu SRAM (đầu ra có thanh ghi, trễ 1)
    ctl_d1 = None                              # (vld_row[P], first, last) trễ 1
    skA = [[None]*r for r in range(P)]         # lane r: r tầng
    skB = [[None]*c for c in range(P)]
    pe = [[dict(a=0,v=0,f=0,l=0,b=0,acc=0,res=0) for c in range(P)] for r in range(P)]
    fifo = []                                  # metadata tile (i0, j0, last_tile)
    drain = None                               # metadata tile đang xả
    out_reg = None                             # thanh ghi đầu ra o_row_*
    vpu_pipe = [None]*L_VPU
    C = np.full((M, N), None, dtype=object)
    writes = 0
    done_cycle = None; done_cnt = 0
    last_out_cycle = None
    pending_done = None
    for t in range(0, 20000):
        pe_start = (t == 0)
        # ===== tổ hợp: bộ tuần tự phát yêu cầu đọc
        rd = None
        if seq['busy'] and seq['cnt'] < K:
            i0, j0 = seq['ti']*P, seq['tj']*P
            rd = (i0, j0, seq['cnt'])
        # ===== tổ hợp: đầu vào cột 0 / hàng 0 của lưới PE
        def lane_a(r):
            if r == 0:
                return (sram_a[0] if sram_a else 0,) + ((ctl_d1[0][0], ctl_d1[1], ctl_d1[2]) if ctl_d1 else (0,0,0))
            x = skA[r][-1]
            return x if x else (0,0,0,0)
        def lane_b(c):
            if c == 0: return sram_b[0] if sram_b else 0
            x = skB[c][-1]; return x if x is not None else 0
        # đầu vào từng PE
        ins = [[None]*P for _ in range(P)]
        for r in range(P):
            for c in range(P):
                if c == 0: a,v,f,l = lane_a(r)
                else: q = pe[r][c-1]; a,v,f,l = q['a'],q['v'],q['f'],q['l']
                b = lane_b(c) if r == 0 else pe[r-1][c]['b']
                ins[r][c] = (a,v,f,l,b)
        # ===== tổ hợp: khối xả — kích hoạt bởi o_last của PE(r, P-1)
        trig = [pe[r][P-1]['v'] and pe[r][P-1]['l'] for r in range(P)]
        assert sum(trig) <= 1, ("hai hàng cùng xả", t)
        new_out = None
        new_drain = drain
        for r in range(P):
            if trig[r]:
                if r == 0:
                    new_drain = fifo.pop(0)
                md = new_drain
                i0, j0, lt, rows = md
                row = [pe[r][c]['res'] for c in range(P)]
                mask = [1 if j0+c < N else 0 for c in range(P)]
                new_out = (i0+r, j0, row, mask, lt and r == rows-1)
        # ===== đầu ra (L_VPU) và ghi C
        vin = out_reg
        if L_VPU == 0: vout = vin
        else: vout = vpu_pipe[-1]
        if vout:
            i, j0, row, mask, islast = vout
            for c in range(P):
                if mask[c]:
                    assert C[i][j0+c] is None, "ghi hai lần"
                    C[i][j0+c] = row[c]; writes += 1
            if islast: pending_done = t + 1
        pe_done = (pending_done is not None and t == pending_done)
        if pe_done:
            done_cnt += 1; done_cycle = t
        # ===== cập nhật thanh ghi (cạnh clock cuối chu kỳ t)
        # PE
        for r in range(P):
            for c in range(P):
                a,v,f,l,b = ins[r][c]; q = pe[r][c]
                if v:
                    s = (0 if f else q['acc']) + a*b
                    s = ((s + 2**31) % 2**32) - 2**31
                    q['acc'] = s
                    if l: q['res'] = s
                q['a'],q['v'],q['f'],q['l'],q['b'] = a,v,f,l,b
        # skew A lane r>=1: tầng 0 nhận (sram_a[r], ctl row r)
        for r in range(1, P):
            st = skA[r]
            inp = (sram_a[r] if sram_a else 0,) + ((ctl_d1[0][r], ctl_d1[1], ctl_d1[2]) if ctl_d1 else (0,0,0))
            skA[r] = [inp] + st[:-1]
        for c in range(1, P):
            st = skB[c]
            skB[c] = [sram_b[c] if sram_b else 0] + st[:-1]
        # SRAM và ctl_d1
        if rd:
            i0, j0, k = rd
            sram_a = [int(A[i0+r][k]) if i0+r < M else rnd.randint(-128,127) for r in range(P)]
            sram_b = [int(B[k][j0+c]) if j0+c < N else rnd.randint(-128,127) for c in range(P)]
            ctl_d1 = ([1 if i0+r < M else 0 for r in range(P)], int(k == 0), int(k == K-1))
        else:
            sram_a = None; sram_b = None; ctl_d1 = None
        # FIFO metadata: đẩy khi phát k = K-1
        if rd and rd[2] == K-1:
            i0, j0, _ = rd
            fifo.append((i0, j0, seq['tile'] == NT-1, min(P, M-i0)))
            assert len(fifo) <= 2, "FIFO > 2"
        drain = new_drain
        # VPU pipe, out_reg
        if L_VPU: vpu_pipe = [vin] + vpu_pipe[:-1]
        out_reg = new_out
        # bộ tuần tự
        if pe_start:
            seq.update(busy=True, ti=0, tj=0, cnt=0, tile=0)
        elif seq['busy']:
            seq['cnt'] += 1
            if seq['cnt'] == I:
                seq['cnt'] = 0; seq['tile'] += 1
                seq['tj'] += 1
                if seq['tj'] == TN: seq['tj'] = 0; seq['ti'] += 1
                if seq['tile'] == NT: seq['busy'] = False
        if done_cycle is not None and t > done_cycle + 5: break
    return C, writes, done_cycle, done_cnt

def predict(M,N,K,P,L):
    I=max(K,P); NT=-(-M//P)*-(-N//P); rl=min(P, M-(-(-M//P)-1)*P)-1
    return 1+(NT-1)*I+1+K+P+rl+L+1

if __name__ == '__main__':
  rng=np.random.default_rng(1); bad=0; n=0
  for P in (2,4,8):
    for trial in range(150 if P>2 else 30):
      M=int(rng.integers(1,33)); N=int(rng.integers(1,9))*4; K=int(rng.integers(1,9))*4
      if P==2: M=int(rng.integers(1,9)); N=int(rng.integers(1,3))*4; K=int(rng.integers(1,3))*4
      L=int(rng.integers(0,4))
      A=rng.integers(-128,128,(M,K)); B=rng.integers(-128,128,(K,N))
      C,w,dc,dn=run(A,B,M,N,K,P,L,seed=trial)
      ref=(A.astype(np.int64)@B.astype(np.int64))
      ok = w==M*N and all(C[i][j]==ref[i][j] for i in range(M) for j in range(N)) and dn==1 and dc==predict(M,N,K,P,L)
      n+=1
      if not ok: bad+=1; print("FAIL",P,M,N,K,L,w,dc,predict(M,N,K,P,L))
  print("tests",n,"fail",bad)
  A=np.array([[12,-5,30,7],[-20,8,4,15]]);B=np.array([[3,-2,10,5],[6,4,-7,1],[-4,9,2,-3],[8,-1,5,6]])
  C,w,dc,dn=run(A,B,2,4,4,2,0); print(C, dc)
  for P in (4,8): print(P, predict(32,32,32,P,0), predict(32,32,32,P,4), predict(20,12,8,P,0), predict(1,4,4,P,0))
