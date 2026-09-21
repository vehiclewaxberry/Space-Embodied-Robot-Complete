# WP03 有限姿态筛查

固定根变换 S=[90,0,125.15] mm；所有候选双指15 mm。OPEN_PARKING保持开放停放语义，未定义发射收拢。

包络当前包含完整accepted臂、母线核心、M3R来源边界及两侧三叶翼（每叶300×200×2.5，WP03固定偏置R2）；WP03新增随星保持器/连接器/线束尚待实例收据，不能据本表宣称完整整星装箱可行。

| 姿态 | q/deg | 已知部件包络XYZ/mm | 8关节限位 | 自表面筛查 |
|---|---|---|---|---|
| OPEN_PARKING_REFERENCE | [0, -30, -60, 40, 0, 0] | 504.808 × 256.800 × 758.480 | True | SOURCE_REFERENCE_35_BODY_PAIRS_SURFACE_DISJOINT_FINGER_UNKNOWN |
| SERVICE_WORK_REFERENCE | [0, -80, -70, 30, 0, 0] | 694.475 × 1442.300 × 715.166 | True | SOURCE_REFERENCE_35_BODY_PAIRS_SURFACE_DISJOINT_FINGER_UNKNOWN |
| EXISTING_CANDIDATE_2 | [0, -30, -80, 60, 0, 0] | 444.543 × 256.800 × 810.967 | True | NONADJACENT_BODY_PAIRS_SURFACE_DISJOINT_FINGER_UNKNOWN |
| EXISTING_CANDIDATE_3 | [0, -45, -75, 30, 0, 0] | 551.131 × 256.800 × 821.242 | True | NONADJACENT_BODY_PAIRS_SURFACE_DISJOINT_FINGER_UNKNOWN |
| EXISTING_CANDIDATE_4 | [0, -60, -90, 50, 0, 0] | 589.251 × 256.800 × 844.597 | True | NONADJACENT_BODY_PAIRS_SURFACE_DISJOINT_FINGER_UNKNOWN |

仅评价已登记的三个候选；原stow自交负例保留在源JSON，未改名选用。筛查采用严格AABB分离、近区原始三角面裁剪和VTK FirstContact；AABB重叠不自动判碰撞。

accepted STL指/指、闭体包含和姿态间连续路径仍为UNKNOWN。已有名义BRep双指15 mm间隙3.8 mm单独引用，不替代accepted STL验证。

复现：`python pose_screen.py`；所有绝对极值、责任配对与来源hash见results/POSE_SCREEN.json。