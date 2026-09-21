# 🧪 Référence de test de performance réelle reBot-DevArm

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
> Ce document fournit des données de test de performance de référence pour le reBot Arm B601-DM dans des conditions de travail normales et extrêmes.

> [!WARNING]
> **Différence de version** : Ce test est basé sur le reBot Arm B601-DM équipé de **moteurs Damiao version V4**. Les performances des versions V3 et antérieures diffèrent. Les données sont fournies à titre indicatif uniquement, les performances réelles doivent être vérifiées par des tests.

---

## 📋 Table des matières

- [⚡ Test de performance en conditions extrêmes](#-test-de-performance-en-conditions-extrêmes)
- [📈 Courbe de charge officielle](#-courbe-de-charge-officielle)
- [📝 Conclusion et recommandations](#-conclusion-et-recommandations)
- [🙋 Questions fréquentes (FAQ)](#-questions-fréquentes-faq)
- [📅 Historique des mises à jour](#-historique-des-mises-à-jour)
- [📞 Support technique](#-support-technique)

---

## ⚡ Test de performance en conditions extrêmes

### Conditions de test

**Test de mouvement dynamique** :
- Durée d’un mouvement : 5 s
- Mode de mouvement : mouvement alternatif
- Plage d’extension du bras : 5%~70% / 5%~100% de la portée nominale

**Test de maintien statique** :
- Posture de test : maintien statique sous charge
- Extension du bras : 70% / 100% de la portée nominale

### Résultats des tests

> 👉 **Conclusion principale** : La structure du bras est suffisamment robuste. L’arrêt du test est dû à la **protection contre la surchauffe du moteur n°2**. Charge recommandée **≤ 1,5 kg**, portée recommandée **< 70%**, et il est conseillé d’ajouter un refroidissement actif.

#### 1. Test de mouvement dynamique

| Plage du bras | Charge | Durée | Cause d’arrêt |
|----------|------|----------|----------|
| Mouvement alternatif 5%–70% | 1.5 kg | > 2 h | Température du moteur n°2 à 90°C, arrêt manuel |
| Mouvement alternatif 5%–70% | 2.5 kg | 40 min | Protection contre la surchauffe déclenchée |
| Mouvement alternatif 5%–100% | 1.5 kg | 45 min | Protection contre la surchauffe déclenchée |

#### 2. Test de maintien statique

| Position de test | Charge (kg) | Durée maximale | Cause d’arrêt |
|----------|-----------|--------------|----------|
| Maintien à 70% d’extension | 1.5 | 18 min | Protection contre la surchauffe |
| Maintien à 100% d’extension | 1.5 | 3 min | Protection contre la surchauffe |

---

## 📈 Courbe de charge officielle

![12Nm 负载曲线图](./images/12Nm.png)

<p align="center">Courbe de charge moteur série Damiao 43 version 12Nm</p>

---

## 📝 Conclusion et recommandations

### Recommandations d’utilisation

1. **Conditions recommandées**
   - Charge : < 1,5 kg
   - Rayon de travail : < 70% de la portée (450 mm)
   - Vitesse de mouvement : < 70% de la vitesse maximale
   - Température ambiante : 15 °C ~ 35 °C

2. **Recommandations de refroidissement**
   - Ajouter un refroidissement actif lors d’une utilisation prolongée à forte charge
   - Après 2 heures de fonctionnement continu, prévoir une pause de 10 à 15 minutes
   - Éviter l’exposition directe au soleil et les espaces confinés

---

## 🙋 Questions fréquentes (FAQ)

<details>
<summary><b>Q1 : Les performances diminuent-elles dans un environnement à haute température ?</b></summary>

Oui. Lorsque la température ambiante dépasse 35 °C ou que la température du moteur dépasse 75 °C, il est recommandé de réduire la charge et la vitesse afin de garantir la précision et la durée de vie. Une utilisation prolongée à haute température est déconseillée.

</details>

<details>
<summary><b>Q2 : Les données de test s’appliquent-elles à toutes les versions ?</b></summary>

Ce test est basé sur la version équipée de **moteurs Damiao V4**. Les performances des versions V3 et antérieures diffèrent, les données sont fournies à titre indicatif.

</details>

---

## 📅 Historique des mises à jour

| Version | Date | Contenu de mise à jour | Auteur |
|------|------|----------|------|
| v1.0 | 2026.04.01 | Version initiale, publication des données de test de performance de base | Équipe AI Robotics SeeedStudio |

---

## 📞 Support technique

Pour toute question concernant les tests de performance, n’hésitez pas à nous contacter :

- **Support technique** : yaohui.zhu@seeed.cc
- **Discord** : [Rejoindre la communauté](https://discord.gg/AbGuqJhDpQ)
- **Wiki** : [Consulter la base de connaissances](https://wiki.seeedstudio.com/robotics_page/)

---

<p align="center">
  <strong>🤖 reBot-DevArm - Un bras robotique open source pour chaque développeur</strong>
</p>