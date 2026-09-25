| configuration | budgets (F / I / X / W) | rev 5 | rev 6 |
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
| open(X) ∥ exit(X) ∥ rec | 0,1 / 0 / 0 / 0 | ok  [BUSY_TX=13260] (27,964/129,329 states) | ok  [BUSY_TX=13260] (27,964/129,329 states) |
| open(X) ∥ open(X) ∥ exit(Y) | 0,1 / 0 / 0 / 0 | ok (9,196/56,904 states) | ok (9,196/56,904 states) |
| open(X) ∥ open(X) ∥ exit(X) | 0,1 / 0 / 0 / 0 | ok (627,725/3,585,319 states) | ok (627,725/3,585,319 states) |
| open(X) ∥ exit(X) ∥ exit(X) | 0,1 / 0 / 0 / 0 | ok (22,328/85,840 states) | ok (22,328/85,840 states) |
| close(X)+[open(Y)] ∥ open(Y) | 0,1 / 1 / 0 / 0 | ok (4,750/25,487 states) | ok (4,750/25,487 states) |
| R19: close(X)+[aopen(Y)] ∥ idle | 0,1 / 1 / 0 / 0 | ok (279/1,129 states) | ok (279/1,129 states) |
| R19+mask: close(X)+[aopen(Y)] ∥ open(Z) | 0 / 1 / 0 / 0 | ok (2,922 states) | ok (2,922 states) |
| c8: close(X)+[open(Y)] ∥ close(X)+[open(Y)] | 0 / 2 / 0 / 0 | ok (320,834 states) | ok (320,834 states) |
| open(X)+[exit(X)] | 0,1 / 1 / 0 / 0 | ok (663/2,898 states) | ok (663/2,898 states) |
| exit(X)+[rec] ∥ open(Y) | 0,1 / 1 / 0 / 0 | ok  [REENT=1008] (2,560/9,846 states) | ok  [REENT=1008] (2,560/9,846 states) |
| aopen(X) ∥ exit(X) ∥ idle | 0,1 / 0 / 0 / 0 | ok (5,638/20,985 states) | ok (5,638/20,985 states) |
| c3: with L: open(X) ∥ close(Y)+[lock] | 0,1 / 1 / 0 / 0 | ok (781/2,973 states) | ok (781/2,973 states) |
| with L: exit(X) ∥ exit(Y)+[lock] | 0 / 1 / 0 / 0 | ok  [CYC_TX=14, BUSY_TX=70] (1,497 states) | ok  [CYC_TX=14, BUSY_TX=70] (1,497 states) |
| with L: open(X) ∥ open(Y)+[lock] | 0 / 1 / 0 / 0 | ok (1,331 states) | ok (1,331 states) |
| ext: open(X) ∥ open(Y) | 0 / 0 / 2 / 0 | ok  [LOST=88, MASKED=16] (15,505 states) | ok  [LOST=88, MASKED=16] (15,505 states) |
| ext: open(X) ∥ exit(X) | 0 / 0 / 2 / 0 | CLOBBER=435, REGMULTI=145  [LOST=26, MASKED=2] (103,740 states) | ok  [LOST=26, MASKED=2, REGCLOB=290] (103,317 states) |
| ext: close(X) ∥ rec | 0,1 / 0 / 2 / 0 | ok  [LOST=6] (772/1,735 states) | ok  [LOST=6] (772/1,735 states) |
| ext: enter(X) ∥ open(Y) | 0 / 0 / 2 / 0 | ok  [LOST=12] (5,488 states) | ok  [LOST=12] (5,536 states) |
| reg: exit(X) + outside free/take | 0,1 / 0 / 2 / 0 | CLOBBER=3, REGMULTI=1 (156/219 states) | ok  [REGCLOB=2] (148/206 states) |
| reg: open(Y) ∥ exit(X) + free/take | 0 / 0 / 2 / 0 | CLOBBER=144, REGMULTI=48  [LOST=11] (4,504 states) | ok  [LOST=11, REGCLOB=96] (4,795 states) |
| reg: first enter(X) + free/take | 0,1 / 0 / 2 / 0 | CLOBBER=3, REGMULTI=1 (134/218 states) | ok  [REGCLOB=2] (156/248 states) |
| reg: rec ∥ open(X) + free/take/free | 0 / 0 / 3 / 0 | CLOBBER=144, REGMULTI=48  [LOST=18] (6,882 states) | ok  [LOST=18, REGCLOB=96] (7,684 states) |
| rebind: enter(X) ∥ open(Y) + take | 0 / 0 / 2 / 0 | ok  [LOST=9] (3,433 states) | ok  [LOST=9] (3,481 states) |
| cb/local: open(X) ∥ exit(X) | 0 / 0 / 1 / 0 | ok  [LOST=4] (15,197 states) | ok  [LOST=4] (15,197 states) |
| ext+re: close(X)+[open(Y)] ∥ open(Y) | 0 / 1 / 1 / 0 | ok  [LOST=18] (61,027 states) | ok  [LOST=18] (61,027 states) |
| ext+re: exit(X)+[rec] ∥ open(Y) | 0 / 1 / 1 / 0 | ok  [LOST=9, REENT=2089] (21,572 states) | ok  [LOST=9, REENT=2163] (23,039 states) |
| ext+greenlet: [close(X), open(X)] ∥ open(Y) | 0 / 0 / 1 / 2 | ok  [LOST=36] (144,565 states) | ok  [LOST=36] (144,565 states) |
| ext+greenlet: [exit(X), rec] ∥ open(X) | 0 / 0 / 1 / 2 | ok  [LOST=16] (3,588,164 states) | ok  [LOST=16] (3,636,007 states) |
| ext+async: aopen(X) ∥ exit(X) ∥ idle | 0 / 0 / 1 / 0 | ok  [LOST=8] (47,890 states) | ok  [LOST=8] (48,111 states) |
| greenlet: [close(X), open(X)] ∥ open(Y) | 0 / 0 / 0 / 2 | ok (9,893 states) | ok (9,893 states) |
| greenlet: [exit(X), rec] ∥ open(X) | 0 / 0 / 0 / 2 | ok (494,652 states) | ok (494,652 states) |
