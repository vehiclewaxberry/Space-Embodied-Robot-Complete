---
layout: home
title: DISCOWER ATMOS
permalink: /
---

Welcome to the DISCOWER Autonomy Testbed for Multi-purpose Orbiting Systems (ATMOS) documentation page. 

ATMOS is a free-flyer platform developed at the KTH Space Robotics Laboratory for testing and validating space systems. The platform is composed by an air-bearing support system for frictionless motion, a modular actuation plate compatible with solenoid thrusters and propeller-based actuation, and a payload support system for testing various accessories. ATMOS aims at being a state-of-the-art platform for space robotics testing and validation, with the aim of reducing ground-to-orbit testing costs and increasing the reliability of space systems.


<html>
<script type="module" src="https://unpkg.com/@google/model-viewer/dist/model-viewer.min.js"></script>
<model-viewer src="/3D/full_assy_wAttachments.glb" 
              alt="A 3D model" 
              ar 
              auto-rotate 
              camera-controls 
              shadow-intensity="1">
</model-viewer>
<style>
    model-viewer {
        width: 100%;
        height: 500px;
        background-color: var(background-color, #ffffff);
    }
</style>
</html>

Here you can see the 3D platform used in DISCOWER. In this website, we provide detailed setups on assembling such a free-flyer platform, including modular actuation plates and payload bays.

> ##### ATMOS in Augmented Reality
>
> Visualizing this website on Android allows you to see ATMOS in Augmented Reality. Just click the AR button on the 3D model above!
{: .block-tip }

### Changelog
The latest changes to the documentation can be found below:
- **2026-03-06**: 
  - Added MIT and UIUC to ATMOS-supported institutions
  - Updated Bill-of-Materials part 0212 with the correct version of the Festo Push-in T-connector (QSMT-6 instead of QST-6)
- **2026-02-19**:
  - Contributions from Caltech (Vivian Norum and Teagan Abeling) and MIT (Kareena Shah and Brooke Schmelz): 
    - Updated regulator part number for thruster module.
    - Updated baseplate aluminum profile height from 21cm to 23cm for extra clearance for thicker bottles
    - Added missing item on BOM (air-bearing to push-in tubing adapter)
- **2025-01-15**:
  - ATMOS website is now open-source! Feel free to send in Pull-Requests with updates to the documentation at [https://github.com/DISCOWER/w3_atmos](https://github.com/DISCOWER/w3_atmos)

- **2025-11-24**: 
  - Updated Jetson Box STL files in [Avionics Plate](https://atmos.discower.io/jekyll/2024-11-23-avionics.html#onboard-computer) to match latest version of ATMOS
  - Added aluminium profile height for each layer in [Base Plate](https://atmos.discower.io/jekyll/2024-11-21-baseplate.html#pneumatic-plate---attached), [Actuation Plate](http://127.0.0.1:4000/jekyll/2024-11-22-actuation.html#aluminium-profiles), and [Avionics Plate](https://atmos.discower.io/jekyll/2024-11-23-avionics.html#payload-aluminium-profiles)
  - Updated PX4 instructions in [Pixhawk Setup](https://atmos.discower.io/pages/PX4/) for the multiple connection options with UXRCE and MAVLink

## Citing this work

A preprint with information regarding ATMOS and the KTH Space Robotics Laboratory is [available on arXiv](https://arxiv.org/abs/2501.16973), with the latest version being published in [IEEE Transactions on Field Robotics](https://ieeexplore.ieee.org/document/11245595). If this work is useful for your research, consider citing:

```bibtex
@ARTICLE{11245595,
  author={Roque, Pedro and Phodapol, Sujet and Krantz, Elias and Lim, Jaeyoung and Verhagen, Joris and Jiang, Frank J. and Dörner, David and Mao, Huina and Tibert, Gunnar and Siegwart, Roland and Stenius, Ivan and Tumova, Jana and Fuglesang, Christer and Dimarogonas, Dimos V.},
  journal={IEEE Transactions on Field Robotics}, 
  title={Toward Open-Source and Modular Space Systems With ATMOS}, 
  year={2026},
  volume={3},
  number={},
  pages={141-161},
  keywords={Space vehicles;Robots;Hardware;Floors;Testing;Aerospace electronics;Attitude control;Orbits;MATLAB;Propulsion;Multirobot systems;orbital robotics},
  doi={10.1109/TFR.2025.3632772}}
```
<html>
<iframe src="https://drive.google.com/file/d/1IQ3zcbxwNgNY_v_4YbrNEkiCZEV_he8L/preview" width="100%" height="435" allow="autoplay"></iframe>
</html>