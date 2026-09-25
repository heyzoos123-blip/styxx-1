| configuration | budgets (F / I / X / W) | rev 4 | rev 5 |
|---|---|---|---|
| open(X) ∥ exit(X) | 0,1,2 / 0 / 0 / 0 | ok [STALE_rev4=3916] (8,006/32,104/38,946 states) | ok (3,158/11,929/14,626 states) |
| close(X) ∥ exit(X) | 0,1,2 / 0 / 0 / 0 | ok [STALE_rev4=604] (2,385/5,698/7,026 states) | ok (846/1,985/2,480 states) |
| open(X) ∥ open(X) | 0,1,2 / 0 / 0 / 0 | ok [BUSY_OPEN=32, STALE_rev4=10405] (2,728/19,672/52,180 states) | ok (418/2,468/5,538 states) |
| open(X) ∥ open(Y) | 0,1,2 / 0 / 0 / 0 | ok [BUSY_OPEN=32, STALE_rev4=10405] (2,728/19,672/52,180 states) | ok (418/2,468/5,538 states) |
| open(Y) ∥ exit(X) | 0,1,2 / 0 / 0 / 0 | ok [STALE_rev4=923] (826/3,840/5,211 states) | ok (360/1,426/1,982 states) |
| exit(X) ∥ exit(X) | 0,1,2 / 0 / 0 / 0 | ok (151/255/274 states) | ok (121/215/234 states) |
| exit(X) ∥ exit(Y) | 0,1,2 / 0 / 0 / 0 | ok [BUSY_TX=24] (458/983/1,112 states) | ok [BUSY_TX=20] (368/805/934 states) |
| rec ∥ open(X), X facade dead | 0,1,2 / 0 / 0 / 0 | ok [STALE_rev4=7626] (10,786/41,359/48,165 states) | ok (2,969/10,406/12,392 states) |
| rec ∥ open(Y) | 0,1,2 / 0 / 0 / 0 | ok [STALE_rev4=553] (532/2,398/3,006 states) | ok (220/822/1,041 states) |
| rec ∥ exit(X) | 0,1,2 / 0 / 0 / 0 | ok [BUSY_TX=29] (204/432/468 states) | ok [BUSY_TX=22] (162/340/376 states) |
| enter(X) ∥ exit(Y) | 0,1,2 / 0 / 0 / 0 | ok [BUSY_TX=32] (357/816/930 states) | ok [BUSY_TX=25] (291/670/784 states) |
| enter(X) ∥ open(Y) | 0,1,2 / 0 / 0 / 0 | ok [STALE_rev4=949] (852/3,928/5,334 states) | ok (340/1,354/1,899 states) |
| enter(X) ∥ enter(X) | 0,1,2 / 0 / 0 / 0 | ok (127/217/234 states) | ok (109/193/210 states) |
| open(X) ∥ exit(X) ∥ rec | 0,1 / 0 / 0 / 0 | ok [BUSY_TX=34584, STALE_rev4=48570] (86,714/408,593 states) | ok [BUSY_TX=11220] (26,804/125,057 states) |
| open(X) ∥ open(X) ∥ exit(Y) | 0,1 / 0 / 0 / 0 | ok [BUSY_OPEN=2228, STALE_rev4=127641] (108,008/750,156 states) | ok (7,524/47,032 states) |
| close(X)+[open(Y)] ∥ open(Y) | 0,1 / 1 / 0 / 0 | ok [BUSY_OPEN=1831, STALE_rev4=54845] (57,311/394,138 states) | ok (4,750/25,487 states) |
| R19: close(X)+[aopen(Y)] ∥ idle | 0,1 / 1 / 0 / 0 | U1=18, A0=58, END=3  [LOST=16, STALE_rev4=669] (1,030/4,631 states) | ok (279/1,129 states) |
| R19+mask: close(X)+[aopen(Y)] ∥ open(Z) | 0 / 1 / 0 / 0 | U1=123, A0=694, LOSTNOTE=1, END=6  [LOST=5, BUSY_OPEN=199, STALE_rev4=3735] (37,328 states) | ok (2,922 states) |
| c8: close(X)+[open(Y)] ∥ close(X)+[open(Y)] | 0 / 2 / 0 / 0 | CYC_OPEN=28  [BUSY_OPEN=35752, STALE_rev4=473266] (5,546,707 states) | ok (320,834 states) |
| open(X)+[exit(X)] | 0,1 / 1 / 0 / 0 | ok [STALE_rev4=683] (1,203/6,266 states) | ok (587/2,642 states) |
| exit(X)+[rec] ∥ open(Y) | 0,1 / 1 / 0 / 0 | ok [REENT=2259, STALE_rev4=5375] (6,664/30,145 states) | ok [REENT=720] (2,320/8,942 states) |
| aopen(X) ∥ exit(X) ∥ idle | 0,1 / 0 / 0 / 0 | ok [STALE_rev4=6609] (13,388/53,699 states) | ok (4,754/17,881 states) |
| c3: with L: open(X) ∥ close(Y)+[lock] | 0,1 / 1 / 0 / 0 | CYC_OPEN=8  [BUSY_OPEN=24, STALE_rev4=2848] (3,380/15,212 states) | ok (781/2,973 states) |
| with L: exit(X) ∥ exit(Y)+[lock] | 0 / 1 / 0 / 0 | ok [CYC_TX=12, BUSY_TX=60] (1,447 states) | ok [CYC_TX=10, BUSY_TX=50] (1,169 states) |
| with L: open(X) ∥ open(Y)+[lock] | 0 / 1 / 0 / 0 | CYC_OPEN=4  [BUSY_OPEN=20, STALE_rev4=1235] (8,299 states) | ok (1,331 states) |
| ext: open(X) ∥ open(Y) | 0 / 0 / 2 / 0 | CLOBBER=372, LOSTNOTE=6, VALUEERROR=1762  [LOST=140, MASKED=18, BUSY_OPEN=142, STALE_rev4=1240] (149,508 states) | ok [LOST=84, MASKED=16] (14,944 states) |
| ext: open(X) ∥ exit(X) | 0 / 0 / 2 / 0 | CLOBBER=911, VALUEERROR=11599  [LOST=30, MASKED=2, BUSY_OPEN=48, STALE_rev4=820] (474,522 states) | ok [LOST=24, MASKED=2] (74,668 states) |
| ext: close(X) ∥ rec | 0,1 / 0 / 2 / 0 | CLOBBER=87, VALUEERROR=137  [STALE_rev4=214] (1,810/4,058 states) | ok (591/1,316 states) |
| ext: enter(X) ∥ open(Y) | 0 / 0 / 2 / 0 | CLOBBER=83, LOSTNOTE=2, VALUEERROR=319  [LOST=16, STALE_rev4=150] (13,035 states) | ok [LOST=7] (3,874 states) |
| greenlet: [close(X), open(X)] ∥ open(Y) | 0 / 0 / 0 / 2 | U1=754, A0=2705, LOSTNOTE=2, END=16  [LOST=12, BUSY_OPEN=494, STALE_rev4=21668] (177,464 states) | ok (9,893 states) |
| greenlet: [exit(X), rec] ∥ open(X) | 0 / 0 / 0 / 2 | ok [STALE_rev4=126901] (1,853,676 states) | ok (407,920 states) |

rev4 runs 66, 10,584,972 state hashes; rev5 runs 66, 1,211,299 state hashes
