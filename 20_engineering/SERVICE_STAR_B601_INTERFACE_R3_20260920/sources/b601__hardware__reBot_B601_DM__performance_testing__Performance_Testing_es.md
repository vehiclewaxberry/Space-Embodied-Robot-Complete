# 🧪 Referencia de pruebas de rendimiento del reBot-DevArm en el robot real

<p align="center">
  <img src="./images/v1.0.png" alt="Cabecera de reBot-DevArm">
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
> Este documento proporciona datos de referencia de pruebas de rendimiento para el reBot Arm B601-DM en condiciones de trabajo normales y extremas.

> [!WARNING]
> **Aviso de versión**: Esta prueba se basa en el reBot Arm B601-DM equipado con **motores Damiao V4**. El rendimiento de las versiones V3 y anteriores es diferente. Los datos son solo orientativos; verifica el rendimiento con tus propias pruebas.

---

## 📋 Índice

- [⚡ Prueba de rendimiento en condiciones extremas](#-prueba-de-rendimiento-en-condiciones-extremas)
- [📈 Curva de carga oficial](#-curva-de-carga-oficial)
- [📝 Conclusiones y recomendaciones](#-conclusiones-y-recomendaciones)
- [🙋 Preguntas frecuentes (FAQ)](#-preguntas-frecuentes-faq)
- [📅 Registro de actualizaciones](#-registro-de-actualizaciones)
- [📞 Soporte técnico](#-soporte-técnico)

---

## ⚡ Prueba de rendimiento en condiciones extremas

### Condiciones de prueba

**Prueba de movimiento dinámico**:
- Duración de cada movimiento: 5 s
- Tipo de movimiento: vaivén
- Extensión del brazo en la prueba: 5 %–70 % / 5 %–100 % del alcance nominal

**Prueba de mantenimiento estático**:
- Postura de prueba: mantenimiento estático de la carga
- Extensión del brazo en la prueba: 70 % / 100 % del alcance nominal

### Resultados de la prueba

> 👉 **Conclusión clave**: La estructura mecánica es suficientemente resistente. La finalización de la prueba se debió a la **protección por sobrecalentamiento del motor n.º 2**. Se recomienda una carga de trabajo **≤ 1.5 kg**, una extensión de trabajo **< 70 % del alcance nominal** y el uso de refrigeración activa.

#### 1. Prueba de movimiento dinámico

| Extensión del brazo | Carga | Duración | Motivo de finalización |
|----------|------|----------|----------|
| Vaivén 5 %–70 % | 1.5 kg | > 2 h | El motor n.º 2 alcanzó 90 °C; detención manual |
| Vaivén 5 %–70 % | 2.5 kg | 40 min | Se activó la protección por sobrecalentamiento |
| Vaivén 5 %–100 % | 1.5 kg | 45 min | Se activó la protección por sobrecalentamiento |

#### 2. Prueba de mantenimiento estático

| Posición | Carga (kg) | Duración máxima | Motivo de finalización |
|----------|-----------|--------------|----------|
| Mantenimiento con extensión al 70 % | 1.5 | 18 min | Protección por sobrecalentamiento |
| Mantenimiento con extensión al 100 % | 1.5 | 3 min | Protección por sobrecalentamiento |

---

## 📈 Curva de carga oficial

![Curva de carga de 12 N·m](./images/12Nm.png)

<p align="center">Curva de carga de 12 N·m del motor Damiao serie 43</p>

---

## 📝 Conclusiones y recomendaciones

### Recomendaciones de uso

1. **Condiciones de trabajo recomendadas**
   - Carga: ≤ 1.5 kg
   - Extensión de trabajo: < 70 % del alcance nominal (450 mm)
   - Velocidad: < 70 % de la velocidad máxima
   - Temperatura ambiente: de 15 °C a 35 °C

2. **Recomendaciones de refrigeración**
   - Añadir refrigeración activa durante trabajos prolongados con alta carga
   - Después de 2 horas de funcionamiento continuo, dejar reposar 10-15 minutos
   - Evitar la exposición directa al sol y los espacios cerrados

---

## 🙋 Preguntas frecuentes (FAQ)

<details>
<summary><b>P1: ¿El rendimiento disminuye en entornos de alta temperatura?</b></summary>

Sí. Cuando la temperatura ambiente supera los 35 °C o la temperatura del motor supera los 75 °C, se recomienda reducir la carga y la velocidad para preservar la precisión y prolongar la vida útil.

</details>

<details>
<summary><b>P2: ¿Estos datos se aplican a todas las versiones?</b></summary>

Esta prueba se basa en la versión con **motores Damiao V4**. El rendimiento de las versiones V3 y anteriores es diferente.

</details>

---

## 📅 Registro de actualizaciones

| Versión | Fecha | Cambios | Autor |
|------|------|----------|------|
| v1.0 | 01/04/2026 | Versión inicial con datos básicos de pruebas de rendimiento | Equipo AI Robotics de SeeedStudio |

---

## 📞 Soporte técnico

Si tienes alguna pregunta sobre las pruebas de rendimiento, no dudes en contactar con nosotros:

- **Soporte técnico**: yaohui.zhu@seeed.cc
- **Discord**: [Únete a la comunidad](https://discord.gg/AbGuqJhDpQ)
- **Wiki**: [Consulta la base de conocimientos](https://wiki.seeedstudio.com/robotics_page/)

---

<p align="center">
  <strong>🤖 reBot-DevArm - Un brazo robótico de código abierto para todos los desarrolladores</strong>
</p>
