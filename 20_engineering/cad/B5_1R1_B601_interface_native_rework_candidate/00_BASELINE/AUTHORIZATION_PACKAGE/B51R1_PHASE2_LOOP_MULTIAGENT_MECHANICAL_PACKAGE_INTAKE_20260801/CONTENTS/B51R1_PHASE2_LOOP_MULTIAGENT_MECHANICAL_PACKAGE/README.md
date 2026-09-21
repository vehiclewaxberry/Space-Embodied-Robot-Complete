# B5.1R1 Phase 2 Loop + Multi-Agent Mechanical Package

本包包含：

- `CODEX_B51R1_PHASE2_LOOP_MULTIAGENT_MASTER_PROMPT.md`
  - 完整机械工程总编排提示词；
  - 当前首先只执行 S00 离线 G1；
  - 不会自动授权 SolidWorks。
- `B51R1_PHASE2_G1_EXPERT_ADJUDICATION_RECOMMENDATION.yaml`
  - datum、唯一原生命名和 CAD—URDF 数值容差建议；
  - 必须由人类签署才生效。
- `B51R1_PHASE2_MULTIAGENT_REVIEW_MATRIX.csv`
  - 各审查 Agent、攻击对象和 Gate 影响。
- `B51R1_S01_EXACT_AUTHORIZATION_TEXT.txt`
  - G1 通过后由项目 Owner 原样发送的 S01 单次授权文本。

当前不授权 S01，不修改用户本地工程文件。
