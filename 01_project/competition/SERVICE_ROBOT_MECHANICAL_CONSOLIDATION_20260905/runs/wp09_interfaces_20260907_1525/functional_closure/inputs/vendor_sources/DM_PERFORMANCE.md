# 🧪 reBot-DevArm Real Machine Performance Testing Reference

<p align="center">
  <img src="./images/v1.0.png" alt="reBot-DevArm Banner">
</p>

<p align="center">
  <strong>
    <a href="./Performance_Testing_zh.md">简体中文</a> &nbsp;|&nbsp;
    <a href="./Performance_Testing.md">English</a> &nbsp;|&nbsp;
    <a href="./Performance_Testing_JP.md">日本語</a>&nbsp;|&nbsp;
    <a href="./Performance_Testing_Fr.md">français</a>&nbsp;|&nbsp;
    <a href="./Performance_Testing_es.md">Español</a>
  </strong>
</p>

> [!NOTE]
> This document provides reference performance test data for the reBot Arm B601-DM under normal and extreme working conditions.

> [!WARNING]
> **Version Notice**: This test is based on the reBot Arm B601-DM equipped with **Damiao V4 motors**. Performance differs for V3 and earlier versions. Data is for reference only; actual performance should be verified through real tests.

---

## 📋 Table of Contents

- [⚡ Extreme Working Performance Test](#-extreme-working-performance-test)
- [📈 Official Load Curve](#-official-load-curve)
- [📝 Conclusions and Recommendations](#-conclusions-and-recommendations)
- [🙋 FAQ](#-faq)
- [📅 Changelog](#-changelog)
- [📞 Technical Support](#-technical-support)

---

## ⚡ Extreme Working Performance Test

### Test Conditions

**Dynamic Motion Test**:
- Single motion duration: 5 s
- Motion mode: Reciprocating motion
- Test arm extension range: 5%~70% / 5%~100% rated reach

**Static Holding Test**:
- Test posture: Static load holding
- Test arm extension: 70% / 100% rated reach

### Test Results

> 👉 **Key Conclusion**: The mechanical structure is sufficiently strong. The test was terminated due to **motor #2 overheating protection**. Recommended working load **≤ 1.5 kg**, recommended working reach **< 70%**, and active cooling is advised.

#### 1. Dynamic Motion Test

| Arm Range | Load | Duration | Termination Reason |
|----------|------|----------|----------|
| 5%–70% reciprocating | 1.5 kg | > 2 h | Motor #2 reached 90°C, manually stopped |
| 5%–70% reciprocating | 2.5 kg | 40 min | Overheat protection triggered |
| 5%–100% reciprocating | 1.5 kg | 45 min | Overheat protection triggered |

#### 2. Static Holding Test

| Position | Load (kg) | Max Duration | Termination Reason |
|----------|-----------|--------------|----------|
| 70% extension hold | 1.5 | 18 min | Overheat protection |
| 100% extension hold | 1.5 | 3 min | Overheat protection |

---

## 📈 Official Load Curve

![12Nm Load Curve](./images/12Nm.png)

<p align="center">Damiao 43 Series Motor 12Nm Load Curve</p>

---

## 📝 Conclusions and Recommendations

### Usage Recommendations

1. **Recommended Working Conditions**
   - Load: < 1.5 kg
   - Working radius: < 70% reach (450 mm)
   - Speed: < 70% max speed
   - Ambient temperature: 15 °C ~ 35 °C

2. **Cooling Recommendations**
   - Add active cooling under long-term high load
   - After 2 hours of continuous operation, rest for 10~15 minutes
   - Avoid direct sunlight and enclosed environments

---

## 🙋 FAQ

<details>
<summary><b>Q1: Will performance degrade in high-temperature environments?</b></summary>

Yes. When ambient temperature exceeds 35 °C or motor temperature exceeds 75 °C, it is recommended to reduce load and speed to ensure accuracy and lifespan.

</details>

<details>
<summary><b>Q2: Is this data applicable to all versions?</b></summary>

This test is based on the **Damiao V4 motor** version. Performance differs for V3 and earlier versions.

</details>

---

## 📅 Changelog

| Version | Date | Changes | Author |
|------|------|----------|------|
| v1.0 | 2026.04.01 | Initial release with basic performance test data | SeeedStudio AI Robotics Team |

---

## 📞 Technical Support

If you have any questions regarding performance testing, feel free to contact us:

- **Technical Support**: yaohui.zhu@seeed.cc
- **Discord**: [Join Community](https://discord.gg/AbGuqJhDpQ)
- **Wiki**: [View Knowledge Base](https://wiki.seeedstudio.com/robotics_page/)

---

<p align="center">
  <strong>🤖 reBot-DevArm - An open-source robotic arm for every developer</strong>
</p>