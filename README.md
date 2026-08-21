# STARPWN 2026 Writeup

Write-ups and analysis scripts for **STARPWN 2026** challenges.

Since I did not participate in the on-site event, this repository excludes challenges that required physical attendance or venue-specific interaction. The goal of this repository is to document the solving process and provide reproducible analyses for anyone interested in CTFs, especially satellite, RF, and embedded security challenges.

Most write-ups include not only the final solution but also the analysis scripts and tools used during the solving process, allowing the results to be reproduced.

![Starpwn](/starpwn.png)

## Categories

- Communication & RF
  - Connect the dots
  - Deadly Parade
  - ...
- Forensics
- Ground Operations
- Misc
- ...

## Environment

- Ubuntu 22.04.5(5.15.0-185-generic)
- Python 3.10.12
- pymavlink
- scapy
- ccsdspy
- and various challenge-specific tools

Each challenge directory contains:

- `README.md` (write-up)
- Original challenge description
- Analysis scripts
- Solver / exploit
- Artifacts

## Summary

| Category | Challenges |
|----------|--------|
| Communication & RF | 6 |
| Forensics | 2 |
| Ground Operations | 2 |
| Misc | 7 |
| Physical | 1 |
| Space Communication & RF | 5 |
| Space Operations | 4 |
| **Total** | **27** |

---

## Challenges

All challenges started at 500 points, and the point values ​​listed below are based on the competition's closing date.

### 📡 Communication & RF

| # | Challenge | Points | Solves | Flag |
|---|-----------|--------|--------|------|
| 1 | [Connect the dots](./Communication_and_RF/Connect_the_dots/) | 477 | 123 | `starpwn{Beyond_Visual_Line_Of_Sight}` |
| 2 | [Deadly Parade](./Communication_and_RF/Deadly_Parade/) | 488 | 88 | `starpwn{Echo_Trail_Park}` |
| 3 | [Is that static...moving?](./Communication_and_RF/Is_that_static_moving/) | 500 | 16 | `STARPWN{sn0wf4ll_1n_$umm3r}` |
| 4 | [Nice day for fishing](./Communication_and_RF/Nice_day_for_fishing/) | 500 | 25 | `STARPWN.3_SP33DY_MMS1S.` |
| 5 | [One to Rule Them All](./Communication_and_RF/One_to_Rule_Them_All/) | 499 | 32 | `starpwn{machines_never_pledged_to_be_allegiant}` |
| 6 | [Walk the False Line](./Communication_and_RF/Walk_the_False_Line/) | 500 | 5 | `starpwn{autonomous_until_someone_speaks_louder}` |


### 🔍 Forensics

| # | Challenge | Points | Solves | Flag |
|---|-----------|--------|--------|------|
| 1 | [Follow the leak](./Forensics/Follow_the_leak/) | 451 | 177 | `flag{50rry_W15h_W3_C0uld_G0_70_7h3_M00n_70g37h3r}` |
| 2 | [Silent Horizon](./Forensics/Silent_Horizon/) | 500 | 25 | `STARPWN{450:SAT1208SAT1108SAT1307SAT1207!}` |

### 🖥️ Ground Operations

| # | Challenge | Points | Solves | Flag |
|---|-----------|--------|--------|------|
| 1 | [Space Infiltrations](./Ground_Operations/Space_Infiltrations/) | 483 | 105 | `STARPWN{9de48ee5d75bd14b45e48948f5b74914}` |
| 2 | [Vanguard Orbital Security](./Ground_Operations/Vanguard_Orbital_Security/) | 480 | 115 | `STARPWN{k1ck_1091c_70_7h3_cu28_4nd_d0_7h3_1mp0551813}` |

### 🎲 Misc

| # | Challenge | Points | Solves | Flag |
|---|-----------|--------|--------|------|
| 1 | [DEAD//LIGHT](./Misc/DEAD_LIGHT/) | 500 | 25 | `STARPWN{DEAD_SIGN_RETURNS}` |
| 2 | [Oversized Downlink](./Misc/Oversized_Downlink/) | 450 | 178 | `STARPWN{lsb_st3g0_1n_th3_d0wnl1nk_ch4nnel}` | 
| 3 | [Strange Holos 1](./Misc/Strange_Holos_1/) | 478 | 113 | `NERF HERDER` |
| 4 | [Strange Holos 2](./Misc/Strange_Holos_2/) | 488 | 90 | `BOLDLY GO` |
| 5 | [Strange Holos 3](./Misc/Strange_Holos_3/) | 443 | 191 | `Bow ties are cool!` |
| 6 | [Strange Holos 4](./Misc/Strange_Holos_4/) | 470 | 140 | `I AM SORRY DAVE, I CANT DO THAT` |
| 7 | [Strange Holos 5](./Misc/Strange_Holos_5/) | 442 | 193 | `so long and thanks for all the phish` |

### 📻 Physical

| # | Challenge | Points | Solves | Flag |
|---|-----------|--------|--------|------|
| 1 | [Rogue Ground Station](./Physical/Rogue_Ground_Station/) | 500 | 2 | `flag(CAFE0000,DF400000}` |

### 🛰️ Space Communication & RF

| # | Challenge | Points | Solves | Flag |
|---|-----------|--------|--------|------|
| 1 | [Beaconing from above](./Space_Communication_and_RF/Beaconing_from_above/) | 431 | 209 | `STARPWN{B34C0N_D3C0D3D_V14_R4D10}` |
| 2 | [Glittercity OST1](./Space_Communication_and_RF/Glittercity_OST1/) | 497 | 48 | `STARPWN{Syn7h_v1be$_fr0m_0rb1t}` |
| 3 | [Glittercity OST2](./Space_Communication_and_RF/Glittercity_OST2/) | 500 | 17 | `STARPWN{THIS_WAS_OFF_TOO_MUCH}` |
| 4 | [Silent Beacon](./Space_Communication_and_RF/Silent_Beacon/) | 454 | 171 | `STARPWN{h0us3k33p1ng_4n0m4ly}` |
| 5 | [Starry hacks](./Space_Communication_and_RF/Starry_hacks/) | 490 | 83 | `STARPWN{7h20u9h_v1c702y_my_ch41n5_423_820k3n}` |

### 🚀 Space Operations

| # | Challenge | Points | Solves | Flag |
|---|-----------|--------|--------|------|
| 1 | [Orbital Integrity](./Space_Operation/Orbital_Integrity/) | 421 | 224 | `STARPWN{2911565936}` |
| 2 | [Time to Intercept](./Space_Operation/Time_to_Intercept/) | 473 | 132 | `STARPWN{h0hm4nn_tr4nsf3r_1nt3rc3pt}` |
| 3 | [Time to Intercept -V2](./Space_Operation/Time_to_Intercept_V2/) | 494 | 65 | `STARPWN{dont_print_th3_answer_}` |
| 4 | [Tumbling Through Space](./Space_Operation/Tumbling_Through_Space/) | 471 | 137 | `STARPWN{d3tumbl3_m4st3r_sp4c3_0p5}` |
