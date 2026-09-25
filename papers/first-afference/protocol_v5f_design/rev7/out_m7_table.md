| configuration | budgets (F / I / X / W) | rev 6 | rev 7 |
|---|---|---|---|
| open(X) ∥ exit(X) | 0,1,2 / 0 / 0 / 0 | ok (3,738/13,969/16,798 states) | ok (3,738/13,969/16,798 states) |
| close(X) ∥ exit(X) | 0,1,2 / 0 / 0 / 0 | ok (998/2,297/2,832 states) | ok (998/2,297/2,832 states) |
| open(X) ∥ open(X) | 0,1,2 / 0 / 0 / 0 | ok (418/2,468/5,538 states) | ok (418/2,468/5,538 states) |
| open(X) ∥ open(Y) | 0,1,2 / 0 / 0 / 0 | ok (418/2,468/5,538 states) | ok (418/2,468/5,538 states) |
| open(Y) ∥ exit(X) | 0,1,2 / 0 / 0 / 0 | ok (440/1,714/2,314 states) | ok (440/1,714/2,314 states) |
| exit(X) ∥ exit(X) | 0,1,2 / 0 / 0 / 0 | ok (145/247/266 states) | ok (145/247/266 states) |
| exit(X) ∥ exit(Y) | 0,1,2 / 0 / 0 / 0 | ok  [BUSY_TX=28] (472/997/1,126 states) | ok  [BUSY_TX=28] (472/997/1,126 states) |
| rec ∥ open(X), X facade dead | 0,1,2 / 0 / 0 / 0 | ok (2,969/10,406/12,392 states) | ok (2,969/10,406/12,392 states) |
| rec ∥ open(Y) | 0,1,2 / 0 / 0 / 0 | ok (220/822/1,041 states) | ok (220/822/1,041 states) |
| rec ∥ exit(X) | 0,1,2 / 0 / 0 / 0 | ok  [BUSY_TX=26] (170/352/388 states) | ok  [BUSY_TX=26] (170/352/388 states) |
| enter(X) ∥ exit(Y) | 0,1,2 / 0 / 0 / 0 | ok  [BUSY_TX=29] (315/714/828 states) | ok  [BUSY_TX=29] (315/714/828 states) |
| enter(X) ∥ open(Y) | 0,1,2 / 0 / 0 / 0 | ok (340/1,354/1,899 states) | ok (340/1,354/1,899 states) |
| enter(X) ∥ enter(X) | 0,1,2 / 0 / 0 / 0 | ok (109/193/210 states) | ok (109/193/210 states) |
| open(X) ∥ exit(X) ∥ rec | 0,1 / 0 / 0 / 0 | ok  [BUSY_TX=13260] / ok  [BUSY_TX=3770] (27,964/129,329 states) | ok  [BUSY_TX=13260] / ok  [BUSY_TX=3770] (27,964/129,329 states) |
| open(X) ∥ open(X) ∥ exit(Y) | 0,1 / 0 / 0 / 0 | ok (9,196/56,904 states) | ok (9,196/56,904 states) |
| open(X) ∥ open(X) ∥ exit(X) | 0,1 / 0 / 0 / 0 | ok (627,725/3,585,319 states) | ok (627,725/3,585,319 states) |
| open(X) ∥ exit(X) ∥ exit(X) | 0,1 / 0 / 0 / 0 | ok (22,328/85,840 states) | ok (22,328/85,840 states) |
| close(X)+[open(Y)] ∥ open(Y) | 0,1 / 1 / 0 / 0 | ok (4,750/25,487 states) | ok (4,750/25,487 states) |
| R19: close(X)+[aopen(Y)] ∥ idle | 0,1 / 1 / 0 / 0 | ok (279/1,129 states) | ok (279/1,129 states) |
| R19+mask: close(X)+[aopen(Y)] ∥ open(Z) | 0 / 1 / 0 / 0 | ok (2,922 states) | ok (2,922 states) |
| c8: close(X)+[open(Y)] ∥ close(X)+[open(Y)] | 0 / 2 / 0 / 0 | ok (320,834 states) | ok (320,834 states) |
| open(X)+[exit(X)] | 0,1 / 1 / 0 / 0 | ok (663/2,898 states) | ok (663/2,898 states) |
| exit(X)+[rec] ∥ open(Y) | 0,1 / 1 / 0 / 0 | ok  [REENT=1008] / ok  [REENT=280] (2,560/9,846 states) | ok  [REENT=1008] / ok  [REENT=280] (2,560/9,846 states) |
| aopen(X) ∥ exit(X) ∥ idle | 0,1 / 0 / 0 / 0 | ok (5,638/20,985 states) | ok (5,638/20,985 states) |
| c3: with L: open(X) ∥ close(Y)+[lock] | 0,1 / 1 / 0 / 0 | ok (781/2,973 states) | ok (781/2,973 states) |
| with L: exit(X) ∥ exit(Y)+[lock] | 0 / 1 / 0 / 0 | ok  [CYC_TX=14, BUSY_TX=70] (1,497 states) | ok  [CYC_TX=14, BUSY_TX=70] (1,497 states) |
| with L: open(X) ∥ open(Y)+[lock] | 0 / 1 / 0 / 0 | ok (1,331 states) | ok (1,331 states) |
| ext: open(X) ∥ open(Y) | 0 / 0 / 2 / 0 | ok  [LOST=88, MASKED=16] (15,505 states) | ok  [LOST=88, MASKED=16] (15,505 states) |
| ext: open(X) ∥ exit(X) | 0 / 0 / 2 / 0 | ok  [LOST=26, MASKED=2, REGCLOB=290] (103,317 states) | ok  [LOST=26, MASKED=2, REGCLOB=290] (103,317 states) |
| ext: close(X) ∥ rec | 0,1 / 0 / 2 / 0 | ok  [LOST=1] / ok  [LOST=6] (772/1,735 states) | ok  [LOST=1] / ok  [LOST=6] (772/1,735 states) |
| ext: enter(X) ∥ open(Y) | 0 / 0 / 2 / 0 | ok  [LOST=12] (5,536 states) | ok  [LOST=12] (5,536 states) |
| reg: exit(X) + outside free/take | 0,1 / 0 / 2 / 0 | ok  [REGCLOB=2] (148/206 states) | ok  [REGCLOB=2] (148/206 states) |
| reg: open(Y) ∥ exit(X) + free/take | 0 / 0 / 2 / 0 | ok  [LOST=11, REGCLOB=96] (4,795 states) | ok  [LOST=11, REGCLOB=96] (4,795 states) |
| reg: first enter(X) + free/take | 0,1 / 0 / 2 / 0 | ok  [REGCLOB=2] (156/248 states) | ok  [REGCLOB=2] (178/290 states) |
| reg: rec ∥ open(X) + free/take/free | 0 / 0 / 3 / 0 | ok  [LOST=18, REGCLOB=96] (7,684 states) | ok  [LOST=18, REGCLOB=96] (7,684 states) |
| rebind: enter(X) ∥ open(Y) + take | 0 / 0 / 2 / 0 | ok  [LOST=9] (3,481 states) | ok  [LOST=9] (3,481 states) |
| cb/local: open(X) ∥ exit(X) | 0 / 0 / 1 / 0 | ok  [LOST=4] (15,197 states) | ok  [LOST=4] (15,197 states) |
| ext+re: close(X)+[open(Y)] ∥ open(Y) | 0 / 1 / 1 / 0 | ok  [LOST=18] (61,027 states) | ok  [LOST=18] (61,027 states) |
| ext+re: exit(X)+[rec] ∥ open(Y) | 0 / 1 / 1 / 0 | ok  [LOST=9, REENT=2163] (23,039 states) | ok  [LOST=9, REENT=2163] (23,039 states) |
| ext+greenlet: [close(X), open(X)] ∥ open(Y) | 0 / 0 / 1 / 2 | ok  [LOST=36] (144,565 states) | ok  [LOST=36] (144,565 states) |
| ext+greenlet: [exit(X), rec] ∥ open(X) | 0 / 0 / 1 / 2 | ok  [LOST=16] (3,636,007 states) | ok  [LOST=16] (3,636,007 states) |
| ext+async: aopen(X) ∥ exit(X) ∥ idle | 0 / 0 / 1 / 0 | ok  [LOST=8] (48,111 states) | ok  [LOST=8] (48,111 states) |
| greenlet: [close(X), open(X)] ∥ open(Y) | 0 / 0 / 0 / 2 | ok (9,893 states) | ok (9,893 states) |
| greenlet: [exit(X), rec] ∥ open(X) | 0 / 0 / 0 / 2 | ok (494,652 states) | ok (494,652 states) |
| cb2: open(Y) ∥ exit(X) [cbrep] | 0 / 0 / 1 / 0 | LOSTNOTE=1  [LOST=2] (1,277 states) | ok  [LOST=2] (1,277 states) |
| cb2: open(Y) ∥ exit(X) [cbrep0] | 0 / 0 / 1 / 0 | LOSTNOTE=1  [LOST=2] (1,308 states) | ok  [LOST=2] (1,308 states) |
| cb2: open(Y) ∥ exit(X) [lclr] | 0 / 0 / 1 / 0 | ok  [LOST=2] (1,246 states) | ok  [LOST=2] (1,246 states) |
| cb2: open(Y) ∥ exit(X) [all, X2] | 0 / 0 / 2 / 0 | LOSTNOTE=3  [LOST=16] (6,082 states) | ok  [LOST=16] (6,082 states) |
| cb2: open(X) ∥ open(Y) ∥ exit(Y) [cbrep] | 0 / 0 / 1 / 0 | LOSTNOTE=12  [LOST=28] (557,112 states) | ok  [LOST=28] (557,112 states) |
| cb2: open(Y) ∥ exit(X) [cbrep, F1] | 1 / 0 / 1 / 0 | LOSTNOTE=9  [LOST=37] (7,373 states) | ok  [LOST=37] (7,373 states) |
| cb2+greenlet: [exit(X), exit(Z)] ∥ open(Y) [cbrep] | 0 / 0 / 1 / 2 | LOSTNOTE=12  [LOST=18] (191,982 states) | ok  [LOST=22] (195,020 states) |
| cb2+re: exit(X)+[exit(Z)] ∥ open(Y) [cbrep] | 0 / 1 / 1 / 0 | LOSTNOTE=5  [LOST=9, REENT=776] (20,175 states) | ok  [LOST=10, REENT=776] (20,330 states) |
| reg2: rec ∥ open(Y) + free/take | 0,1 / 0 / 2 / 0 | ok  [LOST=28] / ok  [LOST=4] (1,628/5,518 states) | ok  [LOST=28] / ok  [LOST=4] (1,628/5,518 states) |
| reg2: rec ∥ open(Y) + free/free | 0,1 / 0 / 2 / 0 | ok  [LOST=29] / ok  [LOST=4] (2,617/8,925 states) | ok  [LOST=29] / ok  [LOST=4] (2,617/8,925 states) |
| reg2: enter(X) ∥ open(Y) + free x3 | 0 / 0 / 3 / 0 | ok  [LOST=53] (12,182 states) | ok  [LOST=14] (10,538 states) |
| reg2: enter(X) ∥ open(Y) + free/take, F1 | 1 / 0 / 2 / 0 | ok  [LOST=104] (12,547 states) | ok  [LOST=104] (12,547 states) |
| reg2: enter(X) ∥ exit(Y) + free/take/cbrep | 0 / 0 / 2 / 0 | ok  [REGCLOB=12, BUSY_TX=308] (5,144 states) | ok  [REGCLOB=12, BUSY_TX=308] (5,171 states) |
| rebind2: enter(X) ∥ open(Y) + take [other id has styxx leftovers] | 0 / 0 / 2 / 0 | ok  [LOST=9] (3,481 states) | ok  [LOST=9] (3,481 states) |

configurations 58; runs: rev6 99, rev7 99; state hashes: rev6 10,463,772, rev7 10,465,412; runs with a violation: rev6 7, rev7 0
