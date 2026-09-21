---
title: Pixhawk Setup
author: Elias Krantz
date: 2025-02-03
category: Jekyll
layout: post
---
This guide outlines the firmware setup process of the ATMOS Freeflyers' onboard microcontroller, the Pixhawk 6X Mini.

# PX4 Autopilot

We use PX4 Autopilot as the firmware for the Pixhawk 6X Mini, openly available here: [PX4 at GitHub](https://github.com/PX4/PX4-Autopilot). To begin, clone the PX4 repository to your local machine:

1. Clone the PX4 repository to your local machine:
   ```bash
   git clone git@github.com:PX4/PX4-Autopilot.git --recursive
   ```

2. Navigate to the cloned `PX4-Autopilot` directory and install the required packages:
   ```bash
   bash ./Tools/setup/ubuntu.sh
   ```
   After this step, rebooting your machine is recommended.

3. Build PX4 messages for ROS 2.  
   To communicate with the Pixhawk via ROS 2, you need its PX4 messages (available here: [PX4-msgs at GitHub](https://github.com/PX4/px4_msgs)) on your local machine.
   ```bash
   mkdir -p ~/px4_ws/src/
   cd ~/px4_ws/src/
   git clone git@github.com:PX4/px4_msgs.git
   cd ~/px4_ws
   colcon build
   source install/setup.bash 
   ```

4. Configure PX4 topics for ROS 2.  
   The ROS 2 topics PX4 publishes (`fmu/out/`) and subscribes to (`fmu/in/`) are defined by `dds_topics.yaml` in the `PX4-Autopilot` directory. We recommend replacing this file with our version before firmware installation.  
   Download ATMOS' [dds_topics.yaml](/assets/px4_autopilot/dds_topics.yaml) and replace the ones found at `PX4-Autopilot/src/modules/uxrce_dds_client/dds_topics.yaml`.

## Firmware Installation

To upload the PX4 firmware to the Pixhawk controller:

1. Connect the Pixhawk to your computer via serial.
2. Navigate to the cloned `PX4-Autopilot` directory.
3. Upload the firmware using:

```bash
make px4_fmu-v6x_spacecraft upload
```

## Setting a Default Namespace

We recommend setting a default ROS 2 namespace for PX4 using the `PX4_UXRCE_DDS_NS` parameter. Specify it during firmware upload:

```bash
PX4_UXRCE_DDS_NS=<namespace> make px4_fmu-v6x_spacecraft upload
```

# Vehicle Configuration and QGroundControl

QGroundControl is the ground control station used to interface with PX4 from a local machine. It is openly available here: [QGroundControl at GitHub](https://github.com/mavlink/qgroundcontrol).

> ##### QGround Control Version
>
> Until the spacecraft feature is available in QGroundControl stable releases, we recommend using the latest daily build version available here: [QGroundControl Daily Builds](https://docs.qgroundcontrol.com/master/en/qgc-user-guide/releases/daily_builds.html#daily-builds).
{: .block-tip }

## Setting up QGroundControl

To build QGroundControl for Linux Ubuntu, you first need:
```bash
sudo usermod -a -G dialout $USER
sudo apt-get remove modemmanager -y
sudo apt install gstreamer1.0-plugins-bad gstreamer1.0-libav gstreamer1.0-gl -y
sudo apt install libfuse2 -y
sudo apt install libxcb-xinerama0 libxkbcommon-x11-0 libxcb-cursor-dev -y
```

Logout and login again to enable the change to user permissions.

After downloading QGroundControl, make it executable:
```bash
chmod +x ./QGroundControl-x86_64.AppImage
```

To launch it, simply run:
```bash
./QGroundControl-x86_64.AppImage
```

## PX4 Vehicle Setup

Once QGroundControl is installed, follow these steps:

1. **Connect the Pixhawk to QGroundControl**
   - Open QGroundControl and connect the Pixhawk to configure the PX4.
   - Navigate to **Vehicle Setup**.

2. **Calibrate the RC (First-time Setup)**
   - Go to Airframe and select **Spacecraft** as the vehicle type, followed by "KTH ATMOS Freeflyer". QGroundControl will prompt you to reboot PX4.
   - Go to the **Radio** tab and follow the calibration procedure.
   - Go to the **Flight Modes** tab and assign flight modes to RC switches:
     - One switch for ARMING/DISARMING.
     - One for MANUAL/ACRO/POSITION.
     - One for OFFBOARD ON/OFF. 

3. **PX4 IP Setup**:
   - In QGroundControl, navigate to **Analyze Tools -> MAVLink Console**.
   - Set PX4 IP address **in MAVLink Console** with:
      ```bash
      echo DEVICE=eth0 > /fs/microsd/net.cfg
      echo BOOTPROTO=fallback >> /fs/microsd/net.cfg
      echo IPADDR=192.168.0.10 >> /fs/microsd/net.cfg
      echo NETMASK=255.255.255.0 >>/fs/microsd/net.cfg
      echo ROUTER=192.168.0.254 >>/fs/microsd/net.cfg
      echo DNS=192.168.0.254 >>/fs/microsd/net.cfg
      ```
   - Reboot the PX4 controller to apply the settings.
      - Either power cycle the Pixhawk or reboot it via **Vehicle Setup -> Parameters -> Tools -> Reboot Vehicle**.

   - In **MAVLink Console**, verify that the IP is set correctly after reboot:
      ```bash
      netman showw
      ```
      Once completed, PX4 should be ready to communicate with the onboard computer.

4. **Configure Parameters**
   - Go to the **Parameters** tab.
   - UXRCE DDS Configuration:
     The PX4 runs a UXRCE-DDS client to expose local UORB topics to the ROS 2 environment.
     - First, ensure that UXRCE runs on boot by ensuring that the parameter `UXRCE_DDS_CFG` is set to `Ethernet` (ATMOS with Pixhawk 6X uses Ethernet), in case you are using an ethernet connection between PX4 and the onboard computer. If using serial communication, set it to the corresponding serial configuration for your board.
      - **For Ethernet-connected Pixhawk**: Next we need to ensure that UXRCE-DDS can connect to the onboard computer IP address. This is controlled with the parameter `UXRCE_DDS_AG_IP` via an integer value. We are using `192.168.0.1`, which is mapped to `-1062731775`. Set this parameter to the agent's IP mapping. For other mappings, run:
         ```bash
         python3 Tools/convert_ip.py "<IP-address>"
         ```
      - **For Serial-connected Pixhawk**: Set the parameter `UXRCE_DDS_CFG` to the corresponding serial configuration for your board. Then, select the serial port and baudrate parameters (`SER_{port}_BAUD`). Higher baudrate settings are recommended for better performance (e.g., 921600 or higher), but may degrade performance on longer/poor cabling. Also ensure that Mavlink over serial is disabled on the selected port by checking that `MAV_{0,1,2}_CONFIG` are set to a different serial port than `UXRCE_DDS_CFG` or `Disabled`.

    - MAVLink Configuration:
      ATMOS uses MAVLink over USB to provide an interface to the ground control station / QGroundControl. To use this functionality, ensure that the following parameters are set:
         - `SYS_USB_AUTO` is set to `Auto-detect` or `MAVLink`.
         - If using multiple ATMOS, assign each PX4 controller a unique MAVLink system ID using the `MAV_SYS_ID` parameter.

    - Reboot the PX4 controller
       - Either power cycle the Pixhawk or reboot it via **Parameters -> Tools -> Reboot Vehicle**.

# PX4 Setup Completed

Now we are ready to set up the Nvidia Jetson Orin NX. Please proceed to the next page.
