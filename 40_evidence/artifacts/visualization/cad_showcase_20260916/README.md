# WP03 展示副本归档入口

2026-09-21 全项目整理时，已对以下三份展示 STEP 与工程域规范源逐文件核对大小及 SHA-256，并删除本目录中的相同副本，共 830,303,108 B。规范源、生成脚本和原 `viewer_launch.log` 保留。

| 展示状态 | 保留的 STEP | 可编辑生成源 |
|---|---|---|
| 作业态 | [servicer_service.step](../../../../20_engineering/service_robot_wp03_spacecraft_body_r1/servicer_service.step) | [生成脚本](../../../../20_engineering/service_robot_wp03_spacecraft_body_r1/servicer_service.step.py) |
| 释放态 | [servicer_released.step](../../../../20_engineering/service_robot_wp03_spacecraft_body_r1/servicer_released.step) | [生成脚本](../../../../20_engineering/service_robot_wp03_spacecraft_body_r1/servicer_released.step.py) |
| 停泊态 | [servicer_parking.step](../../../../20_engineering/service_robot_wp03_spacecraft_body_r1/servicer_parking.step) | [生成脚本](../../../../20_engineering/service_robot_wp03_spacecraft_body_r1/servicer_parking.step.py) |

WP03 是上游设计来源。后续集成总装入口为 [R6H 原生总装](../../../../20_engineering/SERVICE_STAR_CORE_INSTALLATION_R6H_20260920/native/SERVICE_STAR_SERVICE_R6H.SLDASM)，可移植版本见[硬件精简设计包](../../../../20_engineering/SERVICE_STAR_HARDWARE_COMPACT_20260921/README.md)。

逐文件删除及恢复映射见[执行回执](../../../../01_project/governance/WORKSPACE_ORGANIZATION_20260921/LARGE_DUPLICATE_CLEANUP_EXECUTED.json)。如历史展示流程确需原路径，将规范源按原文件名复制回本目录并校验回执哈希即可；不用重新生成 CAD。
