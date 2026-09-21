use crate::protocol::{
    decode_register_value, decode_sensor_feedback, encode_clear_error_cmd, encode_disable_cmd,
    encode_enable_cmd, encode_feedback_request_cmd, encode_force_pos_cmd, encode_mit_cmd,
    encode_pos_vel_cmd, encode_register_read_cmd, encode_register_write_cmd, encode_set_zero_cmd,
    encode_store_params_cmd, encode_vel_cmd, is_register_reply, is_register_write_ack, status_name,
    Limits,
};
use crate::registers::{register_info, RegisterAccess, RegisterDataType};
use motor_core::bus::{CanBus, CanFrame};
use motor_core::device::MotorDevice;
use motor_core::error::{MotorError, Result};
use motor_core::model::{ModelCatalog, MotorModelSpec, PvTLimits, StaticModelCatalog};
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

const REGISTER_POLL_INTERVAL_MS: u64 = 2;
const SET_ZERO_SETTLE_MS: u64 = 20;
const ENSURE_MODE_SETTLE_MS: u64 = 20;
const ENSURE_MODE_REGISTER_READ_TIMEOUT_MS: u64 = 100;
const ENSURE_MODE_HOLD_POSITION_TIMEOUT_MS: u64 = 30;
const STORE_PARAMS_STATE_TIMEOUT_MS: u64 = 50;
const STORE_PARAMS_DISABLE_SETTLE_MS: u64 = 20;
const STORE_PARAMS_SETTLE_MS: u64 = 30;
const ENSURE_MODE_VERIFY_ATTEMPTS: usize = 3;
// Conservative shared retry gap across platforms, adapters, and transports.
// Future transport profiles may tune this separately, e.g. dm-serial 20ms and
// SocketCAN/PCAN 10ms.
const WRITE_REGISTER_ACK_TIMEOUT_MS: u64 = 50;
const WRITE_REGISTER_ACK_ATTEMPTS: usize = 3;
const WRITE_REGISTER_ACK_RETRY_GAP_MS: u64 = 20;
const ENSURE_MODE_VERIFY_RETRY_GAP_MS: u64 = 20;

const DAMIAO_MODELS: &[MotorModelSpec] = &[
    MotorModelSpec {
        vendor: "damiao",
        model: "3507",
        pmax: 12.566,
        vmax: 50.0,
        tmax: 5.0,
    },
    MotorModelSpec {
        vendor: "damiao",
        model: "4310",
        pmax: 12.5,
        vmax: 30.0,
        tmax: 10.0,
    },
    MotorModelSpec {
        vendor: "damiao",
        model: "4310P",
        pmax: 12.5,
        vmax: 50.0,
        tmax: 10.0,
    },
    MotorModelSpec {
        vendor: "damiao",
        model: "4340",
        pmax: 12.5,
        vmax: 10.0,
        tmax: 28.0,
    },
    MotorModelSpec {
        vendor: "damiao",
        model: "4340P",
        pmax: 12.5,
        vmax: 10.0,
        tmax: 28.0,
    },
    MotorModelSpec {
        vendor: "damiao",
        model: "4340_v20",
        pmax: 12.5,
        vmax: 20.0,
        tmax: 28.0,
    },
    MotorModelSpec {
        vendor: "damiao",
        model: "6006",
        pmax: 12.5,
        vmax: 45.0,
        tmax: 20.0,
    },
    MotorModelSpec {
        vendor: "damiao",
        model: "8006",
        pmax: 12.5,
        vmax: 45.0,
        tmax: 40.0,
    },
    MotorModelSpec {
        vendor: "damiao",
        model: "8009",
        pmax: 12.5,
        vmax: 45.0,
        tmax: 54.0,
    },
    MotorModelSpec {
        vendor: "damiao",
        model: "10010L",
        pmax: 12.5,
        vmax: 25.0,
        tmax: 200.0,
    },
    MotorModelSpec {
        vendor: "damiao",
        model: "10010",
        pmax: 12.5,
        vmax: 20.0,
        tmax: 200.0,
    },
    MotorModelSpec {
        vendor: "damiao",
        model: "H3510",
        pmax: 12.5,
        vmax: 280.0,
        tmax: 1.0,
    },
    MotorModelSpec {
        vendor: "damiao",
        model: "G6215",
        pmax: 12.5,
        vmax: 45.0,
        tmax: 10.0,
    },
    MotorModelSpec {
        vendor: "damiao",
        model: "H6220",
        pmax: 12.5,
        vmax: 45.0,
        tmax: 10.0,
    },
    MotorModelSpec {
        vendor: "damiao",
        model: "JH11",
        pmax: 12.5,
        vmax: 10.0,
        tmax: 12.0,
    },
    MotorModelSpec {
        vendor: "damiao",
        model: "6248P",
        pmax: 12.566,
        vmax: 20.0,
        tmax: 120.0,
    },
];

const DAMIAO_CATALOG: StaticModelCatalog = StaticModelCatalog {
    vendor_name: "damiao",
    models: DAMIAO_MODELS,
};

pub fn model_limits(model: &str) -> Option<(f32, f32, f32)> {
    DAMIAO_CATALOG
        .get(model)
        .map(|spec| (spec.pmax, spec.vmax, spec.tmax))
}

pub fn display_model_name(model: &str) -> &str {
    match model {
        "4340_v20" => "4340X",
        _ => model,
    }
}

pub fn display_models(models: &[&'static str]) -> Vec<&'static str> {
    let mut out = Vec::new();
    for model in models {
        let display = display_model_name(model);
        if !out.contains(&display) {
            out.push(display);
        }
    }
    out
}

pub fn match_models_by_limits(pmax: f32, vmax: f32, tmax: f32, tol: f32) -> Vec<&'static str> {
    DAMIAO_MODELS
        .iter()
        .filter(|spec| {
            (spec.pmax - pmax).abs() <= tol
                && (spec.vmax - vmax).abs() <= tol
                && (spec.tmax - tmax).abs() <= tol
        })
        .map(|spec| spec.model)
        .collect()
}

pub fn suggest_models_by_limits(
    pmax: f32,
    vmax: f32,
    tmax: f32,
    top_n: usize,
) -> Vec<&'static str> {
    let mut scored: Vec<(&'static str, f32)> = DAMIAO_MODELS
        .iter()
        .map(|spec| {
            let d = (spec.pmax - pmax).powi(2)
                + (spec.vmax - vmax).powi(2)
                + (spec.tmax - tmax).powi(2);
            (spec.model, d.sqrt())
        })
        .collect();
    scored.sort_by(|a, b| a.1.total_cmp(&b.1));
    scored
        .into_iter()
        .take(top_n)
        .map(|(name, _)| name)
        .collect()
}

#[derive(Debug, Clone, Copy)]
pub enum ControlMode {
    Mit = 1,
    PosVel = 2,
    Vel = 3,
    ForcePos = 4,
}

#[derive(Debug, Clone, Copy)]
pub enum RegisterValue {
    Float(f32),
    UInt32(u32),
}

#[derive(Debug, Clone, Copy)]
pub struct MotorFeedbackState {
    pub can_id: u8,
    pub arbitration_id: u32,
    pub status_code: u8,
    pub status_name: &'static str,
    pub pos: f32,
    pub vel: f32,
    pub torq: f32,
    pub t_mos: f32,
    pub t_rotor: f32,
}

pub struct DamiaoMotor {
    pub motor_id: u16,
    pub feedback_id: u16,
    pub model: String,
    bus: Arc<dyn CanBus>,
    limits: PvTLimits,
    state: Mutex<Option<(MotorFeedbackState, Instant)>>,
    // Software-side guard for set-zero sequencing:
    // set_zero_position() is allowed only after disable() was issued.
    disabled_hint: AtomicBool,
    register_cache: Mutex<RegisterCache>,
}

#[derive(Debug, Clone, Copy)]
struct ModeSwitchState {
    hold_position: Option<f32>,
}

#[derive(Default)]
struct RegisterCache {
    values: HashMap<u8, RegisterValue>,
    reply_time: HashMap<u8, Instant>,
    write_ack_values: HashMap<u8, RegisterValue>,
    write_ack_time: HashMap<u8, Instant>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum RegisterFrameKind {
    Reply,
    WriteAck,
}

fn register_frame_kind(data: &[u8; 8]) -> Option<RegisterFrameKind> {
    if is_register_reply(data) {
        Some(RegisterFrameKind::Reply)
    } else if is_register_write_ack(data) {
        Some(RegisterFrameKind::WriteAck)
    } else {
        None
    }
}

fn register_value_matches(actual: RegisterValue, expected: RegisterValue) -> bool {
    match (actual, expected) {
        (RegisterValue::UInt32(actual), RegisterValue::UInt32(expected)) => actual == expected,
        (RegisterValue::Float(actual), RegisterValue::Float(expected)) => {
            actual.to_bits() == expected.to_bits()
        }
        _ => false,
    }
}

fn budget_cap(total: Duration, hard_cap: Duration, divisor: u32) -> Duration {
    (total / divisor)
        .max(Duration::from_millis(REGISTER_POLL_INTERVAL_MS))
        .min(hard_cap)
}

fn remaining_until(deadline: Instant) -> Option<Duration> {
    deadline.checked_duration_since(Instant::now())
}

fn capped_remaining(deadline: Instant, cap: Duration) -> Option<Duration> {
    remaining_until(deadline).map(|remaining| remaining.min(cap))
}

fn sleep_up_to_reserving(deadline: Instant, duration: Duration, reserve: Duration) {
    if let Some(remaining) = remaining_until(deadline) {
        if remaining > reserve {
            std::thread::sleep(duration.min(remaining - reserve));
        }
    }
}

impl DamiaoMotor {
    pub fn new(motor_id: u16, feedback_id: u16, model: &str, bus: Arc<dyn CanBus>) -> Result<Self> {
        let spec = DAMIAO_CATALOG
            .get(model)
            .ok_or_else(|| MotorError::InvalidArgument(format!("unknown Damiao model: {model}")))?;

        Ok(Self {
            motor_id,
            feedback_id,
            model: model.to_string(),
            bus,
            limits: PvTLimits::from_spec(spec),
            state: Mutex::new(None),
            disabled_hint: AtomicBool::new(true),
            register_cache: Mutex::new(RegisterCache::default()),
        })
    }

    fn send_raw(&self, arbitration_id: u32, data: [u8; 8]) -> Result<()> {
        self.bus.send(CanFrame {
            arbitration_id,
            data,
            dlc: 8,
            is_extended: false,
            is_rx: false,
        })
    }

    pub fn enable(&self) -> Result<()> {
        self.send_raw(self.motor_id.into(), encode_enable_cmd())?;
        self.disabled_hint.store(false, Ordering::Release);
        Ok(())
    }

    pub fn disable(&self) -> Result<()> {
        self.send_raw(self.motor_id.into(), encode_disable_cmd())?;
        self.disabled_hint.store(true, Ordering::Release);
        Ok(())
    }

    pub fn clear_error(&self) -> Result<()> {
        self.send_raw(self.motor_id.into(), encode_clear_error_cmd())
    }

    pub fn set_zero_position(&self) -> Result<()> {
        if !self.disabled_hint.load(Ordering::Acquire) {
            return Err(MotorError::InvalidArgument(format!(
                "motor 0x{:X} is not disabled; set_zero_position skipped. call disable() first",
                self.motor_id
            )));
        }
        self.send_raw(self.motor_id.into(), encode_set_zero_cmd())?;
        std::thread::sleep(Duration::from_millis(SET_ZERO_SETTLE_MS));
        Ok(())
    }

    pub fn send_cmd_mit(
        &self,
        target_position: f32,
        target_velocity: f32,
        stiffness: f32,
        damping: f32,
        feedforward_torque: f32,
    ) -> Result<()> {
        let data = encode_mit_cmd(
            target_position,
            target_velocity,
            feedforward_torque,
            stiffness,
            damping,
            Limits {
                p_min: self.limits.p_min,
                p_max: self.limits.p_max,
                v_min: self.limits.v_min,
                v_max: self.limits.v_max,
                t_min: self.limits.t_min,
                t_max: self.limits.t_max,
            },
        );
        self.send_raw(self.motor_id.into(), data)
    }

    pub fn send_cmd_pos_vel(&self, target_position: f32, velocity_limit: f32) -> Result<()> {
        self.send_raw(
            u32::from(0x100u16 + self.motor_id),
            encode_pos_vel_cmd(target_position, velocity_limit),
        )
    }

    pub fn send_cmd_vel(&self, target_velocity: f32) -> Result<()> {
        self.send_raw(
            u32::from(0x200u16 + self.motor_id),
            encode_vel_cmd(target_velocity),
        )
    }

    pub fn send_cmd_force_pos(
        &self,
        target_position: f32,
        velocity_limit: f32,
        torque_limit_ratio: f32,
    ) -> Result<()> {
        self.send_raw(
            u32::from(0x300u16 + self.motor_id),
            encode_force_pos_cmd(target_position, velocity_limit, torque_limit_ratio),
        )
    }

    pub fn ensure_control_mode(&self, mode: ControlMode, timeout: Duration) -> Result<()> {
        let desired = mode as u32;
        let deadline = Instant::now() + timeout;
        let mode_read_cap = budget_cap(
            timeout,
            Duration::from_millis(ENSURE_MODE_REGISTER_READ_TIMEOUT_MS),
            4,
        );
        let hold_read_cap = budget_cap(
            timeout,
            Duration::from_millis(ENSURE_MODE_HOLD_POSITION_TIMEOUT_MS),
            6,
        );
        let settle = Duration::from_millis(ENSURE_MODE_SETTLE_MS);
        let retry_gap = Duration::from_millis(ENSURE_MODE_VERIFY_RETRY_GAP_MS);
        let mut last_error;

        if let Some(read_timeout) = capped_remaining(deadline, mode_read_cap) {
            match self.get_register_u32(10, read_timeout) {
                Ok(current) if current == desired => return Ok(()),
                Ok(current) => {
                    last_error = Some(MotorError::Protocol(format!(
                        "control mode verify failed: expected {desired}, got {current}"
                    )));
                }
                Err(MotorError::Timeout(e)) => {
                    last_error = Some(MotorError::Timeout(e));
                }
                Err(e) => return Err(e),
            }
        } else {
            return Err(MotorError::Timeout(format!(
                "control mode verify timed out before register 10 could be read within {:?}",
                timeout
            )));
        }

        let switch_state = self.prepare_for_mode_switch(mode, deadline, hold_read_cap);
        self.write_register_u32(10, desired)?;
        sleep_up_to_reserving(deadline, settle, mode_read_cap);
        self.finish_mode_switch(mode, switch_state)?;

        for attempt in 0..ENSURE_MODE_VERIFY_ATTEMPTS {
            let Some(read_timeout) = capped_remaining(deadline, mode_read_cap) else {
                break;
            };
            match self.get_register_u32(10, read_timeout) {
                Ok(verify) if verify == desired => return Ok(()),
                Ok(verify) => {
                    last_error = Some(MotorError::Protocol(format!(
                        "control mode verify failed: expected {desired}, got {verify}"
                    )));
                }
                Err(MotorError::Timeout(e)) => {
                    last_error = Some(MotorError::Timeout(e));
                }
                Err(e) => return Err(e),
            }
            if attempt + 1 < ENSURE_MODE_VERIFY_ATTEMPTS {
                self.write_register_u32(10, desired)?;
                sleep_up_to_reserving(deadline, retry_gap, mode_read_cap);
                self.finish_mode_switch(mode, switch_state)?;
            }
        }

        Err(last_error.unwrap_or_else(|| {
            MotorError::Timeout(format!(
                "control mode verify timed out within total budget {:?}",
                timeout
            ))
        }))
    }

    fn prepare_for_mode_switch(
        &self,
        mode: ControlMode,
        deadline: Instant,
        hold_read_cap: Duration,
    ) -> ModeSwitchState {
        let hold_position = if matches!(
            mode,
            ControlMode::Mit | ControlMode::PosVel | ControlMode::ForcePos
        ) {
            capped_remaining(deadline, hold_read_cap)
                .and_then(|read_timeout| self.get_register_f32(80, read_timeout).ok())
        } else {
            None
        };

        let hold = hold_position.unwrap_or(0.0);
        // Clear every mode command channel before switching because the motor docs
        // require zeroing position, velocity, torque feedforward, kp, and kd.
        let _ = self.send_cmd_vel(0.0);
        let _ = self.send_cmd_pos_vel(hold, 0.0);
        let _ = self.send_cmd_force_pos(hold, 0.0, 0.0);
        let _ = self.send_cmd_mit(hold, 0.0, 0.0, 0.0, 0.0);

        ModeSwitchState { hold_position }
    }

    fn finish_mode_switch(&self, mode: ControlMode, switch_state: ModeSwitchState) -> Result<()> {
        match mode {
            ControlMode::Mit => {
                self.send_cmd_mit(
                    switch_state.hold_position.unwrap_or(0.0),
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                )?;
            }
            ControlMode::PosVel => {
                if let Some(position) = switch_state.hold_position {
                    self.send_cmd_pos_vel(position, 0.0)?;
                }
            }
            ControlMode::Vel => {
                self.send_cmd_vel(0.0)?;
            }
            ControlMode::ForcePos => {
                if let Some(position) = switch_state.hold_position {
                    self.send_cmd_force_pos(position, 0.0, 0.0)?;
                }
            }
        }
        Ok(())
    }

    pub fn request_register_reading(&self, rid: u8) -> Result<()> {
        if register_info(rid).is_none() {
            return Err(MotorError::InvalidArgument(format!(
                "unknown register rid {rid}"
            )));
        }
        self.send_raw(0x7FF, encode_register_read_cmd(self.motor_id, rid))
    }

    fn write_register_f32_once(&self, rid: u8, value: f32) -> Result<()> {
        self.send_raw(
            0x7FF,
            encode_register_write_cmd(self.motor_id, rid, value.to_le_bytes()),
        )
    }

    fn write_register_u32_once(&self, rid: u8, value: u32) -> Result<()> {
        self.send_raw(
            0x7FF,
            encode_register_write_cmd(self.motor_id, rid, value.to_le_bytes()),
        )
    }

    fn wait_for_write_ack(
        &self,
        rid: u8,
        expected: RegisterValue,
        timeout: Duration,
    ) -> Result<()> {
        let request_at = Instant::now();
        let deadline = request_at + timeout;
        loop {
            let ack = {
                let cache = self
                    .register_cache
                    .lock()
                    .map_err(|_| MotorError::Io("register cache lock poisoned".to_string()))?;
                cache
                    .write_ack_time
                    .get(&rid)
                    .copied()
                    .filter(|ts| *ts >= request_at)
                    .and_then(|_| cache.write_ack_values.get(&rid).copied())
            };
            if let Some(value) = ack {
                if register_value_matches(value, expected) {
                    return Ok(());
                }
                return Err(MotorError::Protocol(format!(
                    "register {rid} write ack mismatched expected {:?}, got {:?}",
                    expected, value
                )));
            }
            if Instant::now() >= deadline {
                return Err(MotorError::Timeout(format!(
                    "register {rid} write ack not received within {:?}",
                    timeout
                )));
            }
            std::thread::sleep(Duration::from_millis(REGISTER_POLL_INTERVAL_MS));
        }
    }

    fn wait_for_register_value(&self, rid: u8, timeout: Duration) -> Result<RegisterValue> {
        let request_at = Instant::now();
        self.request_register_reading(rid)?;
        let deadline = request_at + timeout;
        loop {
            let value = {
                let cache = self
                    .register_cache
                    .lock()
                    .map_err(|_| MotorError::Io("register cache lock poisoned".to_string()))?;
                cache
                    .reply_time
                    .get(&rid)
                    .copied()
                    .filter(|ts| *ts >= request_at)
                    .and_then(|_| cache.values.get(&rid).copied())
            };
            if let Some(value) = value {
                return Ok(value);
            }
            if Instant::now() >= deadline {
                return Err(MotorError::Timeout(format!(
                    "register {rid} not received within {:?}",
                    timeout
                )));
            }
            std::thread::sleep(Duration::from_millis(REGISTER_POLL_INTERVAL_MS));
        }
    }

    pub fn write_register_f32(&self, rid: u8, value: f32) -> Result<()> {
        let info = register_info(rid)
            .ok_or_else(|| MotorError::InvalidArgument(format!("unknown register rid {rid}")))?;
        if info.access != RegisterAccess::ReadWrite {
            return Err(MotorError::InvalidArgument(format!(
                "register {rid} is read-only"
            )));
        }
        if info.data_type != RegisterDataType::Float {
            return Err(MotorError::InvalidArgument(format!(
                "register {rid} expects float"
            )));
        }

        let expected = RegisterValue::Float(value);
        let mut last_error = None;
        for attempt in 0..WRITE_REGISTER_ACK_ATTEMPTS {
            self.write_register_f32_once(rid, value)?;
            match self.wait_for_write_ack(
                rid,
                expected,
                Duration::from_millis(WRITE_REGISTER_ACK_TIMEOUT_MS),
            ) {
                Ok(()) => return Ok(()),
                Err(err) => last_error = Some(err),
            }
            if attempt + 1 < WRITE_REGISTER_ACK_ATTEMPTS {
                std::thread::sleep(Duration::from_millis(WRITE_REGISTER_ACK_RETRY_GAP_MS));
            }
        }
        Err(last_error.unwrap_or_else(|| {
            MotorError::Timeout(format!("register {rid} write ack not received"))
        }))
    }

    pub fn write_register_u32(&self, rid: u8, value: u32) -> Result<()> {
        let info = register_info(rid)
            .ok_or_else(|| MotorError::InvalidArgument(format!("unknown register rid {rid}")))?;
        if info.access != RegisterAccess::ReadWrite {
            return Err(MotorError::InvalidArgument(format!(
                "register {rid} is read-only"
            )));
        }
        if info.data_type != RegisterDataType::UInt32 {
            return Err(MotorError::InvalidArgument(format!(
                "register {rid} expects uint32"
            )));
        }

        let expected = RegisterValue::UInt32(value);
        let mut last_error = None;
        for attempt in 0..WRITE_REGISTER_ACK_ATTEMPTS {
            self.write_register_u32_once(rid, value)?;
            match self.wait_for_write_ack(
                rid,
                expected,
                Duration::from_millis(WRITE_REGISTER_ACK_TIMEOUT_MS),
            ) {
                Ok(()) => return Ok(()),
                Err(err) => last_error = Some(err),
            }
            if attempt + 1 < WRITE_REGISTER_ACK_ATTEMPTS {
                std::thread::sleep(Duration::from_millis(WRITE_REGISTER_ACK_RETRY_GAP_MS));
            }
        }
        Err(last_error.unwrap_or_else(|| {
            MotorError::Timeout(format!("register {rid} write ack not received"))
        }))
    }

    pub fn store_parameters(&self) -> Result<()> {
        let already_disabled = matches!(
            self.request_fresh_state(Duration::from_millis(STORE_PARAMS_STATE_TIMEOUT_MS)),
            Ok(Some(state)) if state.status_code == 0x0
        );
        if !already_disabled {
            self.disable()?;
            std::thread::sleep(Duration::from_millis(STORE_PARAMS_DISABLE_SETTLE_MS));
        }
        self.send_raw(0x7FF, encode_store_params_cmd(self.motor_id))?;
        std::thread::sleep(Duration::from_millis(STORE_PARAMS_SETTLE_MS));
        Ok(())
    }

    pub fn request_motor_feedback(&self) -> Result<()> {
        self.send_raw(0x7FF, encode_feedback_request_cmd(self.motor_id))
    }

    pub fn get_register_u32(&self, rid: u8, timeout: Duration) -> Result<u32> {
        match self.wait_for_register_value(rid, timeout)? {
            RegisterValue::UInt32(value) => Ok(value),
            RegisterValue::Float(_) => Err(MotorError::Protocol(format!(
                "register {rid} holds float, not u32"
            ))),
        }
    }

    pub fn latest_state(&self) -> Option<MotorFeedbackState> {
        self.state
            .lock()
            .ok()
            .and_then(|s| s.map(|(state, _)| state))
    }

    pub fn request_fresh_state(&self, timeout: Duration) -> Result<Option<MotorFeedbackState>> {
        let request_at = Instant::now();
        self.request_motor_feedback()?;
        let deadline = request_at + timeout;
        loop {
            if let Some((state, ts)) = self
                .state
                .lock()
                .map_err(|_| MotorError::Io("state lock poisoned".to_string()))?
                .as_ref()
                .copied()
            {
                if ts >= request_at {
                    return Ok(Some(state));
                }
            }
            if Instant::now() >= deadline {
                return Ok(None);
            }
            std::thread::sleep(Duration::from_millis(REGISTER_POLL_INTERVAL_MS));
        }
    }

    fn process_feedback_frame_impl(&self, frame: CanFrame) -> Result<()> {
        if let Some(frame_kind) = register_frame_kind(&frame.data) {
            let (rid, raw) = match frame_kind {
                RegisterFrameKind::Reply => decode_register_value(frame.data)?,
                RegisterFrameKind::WriteAck => {
                    let rid = frame.data[3];
                    // decode_register_value() only accepts 0x33 reply frames; the
                    // write-ack path already validated the 0x55 marker and rid.
                    (
                        rid,
                        [frame.data[4], frame.data[5], frame.data[6], frame.data[7]],
                    )
                }
            };
            let info = register_info(rid)
                .ok_or_else(|| MotorError::Protocol(format!("unknown register in reply: {rid}")))?;
            let value = match info.data_type {
                RegisterDataType::Float => RegisterValue::Float(f32::from_le_bytes(raw)),
                RegisterDataType::UInt32 => RegisterValue::UInt32(u32::from_le_bytes(raw)),
            };
            let mut cache = self
                .register_cache
                .lock()
                .map_err(|_| MotorError::Io("register cache lock poisoned".to_string()))?;
            match frame_kind {
                RegisterFrameKind::Reply => {
                    cache.values.insert(rid, value);
                    cache.reply_time.insert(rid, Instant::now());
                }
                RegisterFrameKind::WriteAck => {
                    cache.write_ack_values.insert(rid, value);
                    cache.write_ack_time.insert(rid, Instant::now());
                }
            }
            return Ok(());
        }

        let decoded = decode_sensor_feedback(
            frame.data,
            Limits {
                p_min: self.limits.p_min,
                p_max: self.limits.p_max,
                v_min: self.limits.v_min,
                v_max: self.limits.v_max,
                t_min: self.limits.t_min,
                t_max: self.limits.t_max,
            },
        );
        let state = MotorFeedbackState {
            can_id: decoded.can_id,
            arbitration_id: frame.arbitration_id,
            status_code: decoded.status_code,
            status_name: status_name(decoded.status_code),
            pos: decoded.pos,
            vel: decoded.vel,
            torq: decoded.torq,
            t_mos: decoded.t_mos,
            t_rotor: decoded.t_rotor,
        };
        self.state
            .lock()
            .map_err(|_| MotorError::Io("state lock poisoned".to_string()))?
            .replace((state, Instant::now()));
        Ok(())
    }
    pub fn get_register_f32(&self, rid: u8, timeout: Duration) -> Result<f32> {
        match self.wait_for_register_value(rid, timeout)? {
            RegisterValue::Float(value) => Ok(value),
            RegisterValue::UInt32(_) => Err(MotorError::Protocol(format!(
                "register {rid} holds u32, not float"
            ))),
        }
    }
}

impl MotorDevice for DamiaoMotor {
    fn vendor(&self) -> &'static str {
        "damiao"
    }

    fn model(&self) -> &str {
        &self.model
    }

    fn motor_id(&self) -> u16 {
        self.motor_id
    }

    fn feedback_id(&self) -> u16 {
        self.feedback_id
    }

    fn enable(&self) -> Result<()> {
        DamiaoMotor::enable(self)
    }

    fn disable(&self) -> Result<()> {
        DamiaoMotor::disable(self)
    }

    fn accepts_frame(&self, frame: &CanFrame) -> bool {
        if frame.is_extended {
            return false;
        }
        frame.arbitration_id == u32::from(self.feedback_id)
            || (frame.dlc > 0 && (frame.data[0] & 0x0F) == (self.motor_id as u8 & 0x0F))
    }

    fn process_feedback_frame(&self, frame: CanFrame) -> Result<()> {
        self.process_feedback_frame_impl(frame)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use motor_core::test_support::MockBus;
    use std::time::{Duration, Instant};

    #[test]
    fn model_limits_and_matching_work() {
        let (pmax, vmax, tmax) = model_limits("4340P").expect("known model");
        assert_eq!(pmax, 12.5);
        assert_eq!(vmax, 10.0);
        assert_eq!(tmax, 28.0);

        let matched = match_models_by_limits(12.5, 10.0, 28.0, 0.01);
        assert!(matched.contains(&"4340"));
        assert!(matched.contains(&"4340P"));
    }

    #[test]
    fn custom_4340_alias_keeps_internal_name_unique_and_display_name_stable() {
        let (pmax, vmax, tmax) = model_limits("4340_v20").expect("known custom model");
        assert_eq!(pmax, 12.5);
        assert_eq!(vmax, 20.0);
        assert_eq!(tmax, 28.0);
        assert_eq!(display_model_name("4340_v20"), "4340X");
        assert_eq!(display_models(&["4340_v20"]), vec!["4340X"]);
    }

    #[test]
    fn suggest_models_returns_closest_first() {
        let suggested = suggest_models_by_limits(12.5, 9.9, 28.1, 3);
        assert!(!suggested.is_empty());
        assert!(suggested[0] == "4340" || suggested[0] == "4340P");
    }

    #[test]
    fn get_register_u32_times_out_when_no_feedback_arrives() {
        let bus: Arc<dyn CanBus> = Arc::new(MockBus::new());
        let motor = DamiaoMotor::new(0x01, 0x11, "4340P", bus).expect("create motor");
        let err = motor
            .get_register_u32(10, Duration::from_millis(1))
            .expect_err("timeout expected");
        assert!(matches!(err, MotorError::Timeout(_)));
    }

    #[test]
    fn get_register_u32_ignores_stale_cached_reply() {
        let bus: Arc<dyn CanBus> = Arc::new(MockBus::new());
        let motor = DamiaoMotor::new(0x01, 0x11, "4340P", bus).expect("create motor");

        let mut cache = motor.register_cache.lock().expect("register cache lock");
        cache.values.insert(10, RegisterValue::UInt32(2));
        cache.reply_time.insert(10, Instant::now());
        drop(cache);

        let err = motor
            .get_register_u32(10, Duration::from_millis(1))
            .expect_err("stale cache must not satisfy new request");
        assert!(matches!(err, MotorError::Timeout(_)));
    }

    #[test]
    fn ensure_control_mode_seeds_position_hold_after_switching_to_pos_vel() {
        let bus_impl = Arc::new(MockBus::new());
        let bus: Arc<dyn CanBus> = bus_impl.clone();
        let motor = Arc::new(DamiaoMotor::new(0x01, 0x11, "4340P", bus).expect("create motor"));
        let responder = Arc::clone(&motor);
        let bus_for_thread = Arc::clone(&bus_impl);

        let position = 1.25f32;
        let handle = std::thread::spawn(move || {
            let deadline = Instant::now() + Duration::from_millis(100);
            let mut replied_position = false;
            let mut replied_mode_ack = false;
            loop {
                let (saw_position_read, saw_mode_write, mode_read_count) = {
                    let sent = bus_for_thread.sent.lock().expect("sent lock");
                    (
                        sent.iter()
                            .any(|f| f.data == encode_register_read_cmd(0x01, 80)),
                        sent.iter().any(|f| {
                            f.data == encode_register_write_cmd(0x01, 10, 2u32.to_le_bytes())
                        }),
                        sent.iter()
                            .filter(|f| f.data == encode_register_read_cmd(0x01, 10))
                            .count(),
                    )
                };

                if saw_position_read && !replied_position {
                    responder
                        .process_feedback_frame_impl(CanFrame {
                            arbitration_id: 0x11,
                            data: [
                                0x01,
                                0x01,
                                0x33,
                                80,
                                position.to_le_bytes()[0],
                                position.to_le_bytes()[1],
                                position.to_le_bytes()[2],
                                position.to_le_bytes()[3],
                            ],
                            dlc: 8,
                            is_extended: false,
                            is_rx: true,
                        })
                        .expect("process position reply");
                    replied_position = true;
                }

                if saw_mode_write && !replied_mode_ack {
                    responder
                        .process_feedback_frame_impl(CanFrame {
                            arbitration_id: 0x11,
                            data: [0x01, 0x01, 0x55, 10, 2, 0, 0, 0],
                            dlc: 8,
                            is_extended: false,
                            is_rx: true,
                        })
                        .expect("process mode write ack");
                    replied_mode_ack = true;
                }

                if saw_mode_write && mode_read_count >= 2 {
                    responder
                        .process_feedback_frame_impl(CanFrame {
                            arbitration_id: 0x11,
                            data: [0x01, 0x01, 0x33, 10, 2, 0, 0, 0],
                            dlc: 8,
                            is_extended: false,
                            is_rx: true,
                        })
                        .expect("process mode reply");
                    return;
                }
                if Instant::now() >= deadline {
                    return;
                }
                std::thread::sleep(Duration::from_millis(1));
            }
        });

        motor
            .ensure_control_mode(ControlMode::PosVel, Duration::from_millis(20))
            .expect("ensure should switch to pos_vel");
        handle.join().expect("responder thread");

        let sent = bus_impl.sent.lock().expect("sent lock");
        let pos_read_idx = sent
            .iter()
            .position(|f| f.data == encode_register_read_cmd(0x01, 80))
            .expect("position read should be sent");
        let mode_write_idx = sent
            .iter()
            .position(|f| f.data == encode_register_write_cmd(0x01, 10, 2u32.to_le_bytes()))
            .expect("mode write should be sent");
        let hold_idx = sent
            .iter()
            .enumerate()
            .find(|(idx, f)| {
                *idx > mode_write_idx
                    && f.arbitration_id == 0x101
                    && f.data == encode_pos_vel_cmd(position, 0.0)
            })
            .map(|(idx, _)| idx)
            .expect("position hold command should be sent after mode write");
        assert!(
            pos_read_idx < mode_write_idx,
            "position read should happen before mode write"
        );
        assert!(
            mode_write_idx < hold_idx,
            "position hold should happen after mode write"
        );
    }

    #[test]
    fn ensure_control_mode_reads_position_before_switching_to_pos_vel() {
        let bus_impl = Arc::new(MockBus::new());
        let bus: Arc<dyn CanBus> = bus_impl.clone();
        let motor = Arc::new(DamiaoMotor::new(0x01, 0x11, "4340P", bus).expect("create motor"));
        let responder = Arc::clone(&motor);
        let bus_for_thread = Arc::clone(&bus_impl);

        let handle = std::thread::spawn(move || {
            let deadline = Instant::now() + Duration::from_millis(100);
            let mut replied_position = false;
            let mut replied_mode_ack = false;
            loop {
                let (saw_position_read, saw_mode_write, mode_read_count) = {
                    let sent = bus_for_thread.sent.lock().expect("sent lock");
                    (
                        sent.iter()
                            .any(|f| f.data == encode_register_read_cmd(0x01, 80)),
                        sent.iter().any(|f| {
                            f.data == encode_register_write_cmd(0x01, 10, 2u32.to_le_bytes())
                        }),
                        sent.iter()
                            .filter(|f| f.data == encode_register_read_cmd(0x01, 10))
                            .count(),
                    )
                };

                if saw_position_read && !replied_position {
                    responder
                        .process_feedback_frame_impl(CanFrame {
                            arbitration_id: 0x11,
                            data: [0x01, 0x01, 0x33, 80, 0, 0, 0, 0],
                            dlc: 8,
                            is_extended: false,
                            is_rx: true,
                        })
                        .expect("process position reply");
                    replied_position = true;
                }

                if saw_mode_write && !replied_mode_ack {
                    responder
                        .process_feedback_frame_impl(CanFrame {
                            arbitration_id: 0x11,
                            data: [0x01, 0x01, 0x55, 10, 2, 0, 0, 0],
                            dlc: 8,
                            is_extended: false,
                            is_rx: true,
                        })
                        .expect("process mode write ack");
                    replied_mode_ack = true;
                }

                if saw_mode_write && mode_read_count >= 2 {
                    responder
                        .process_feedback_frame_impl(CanFrame {
                            arbitration_id: 0x11,
                            data: [0x01, 0x01, 0x33, 10, 2, 0, 0, 0],
                            dlc: 8,
                            is_extended: false,
                            is_rx: true,
                        })
                        .expect("process mode reply");
                    return;
                }
                if Instant::now() >= deadline {
                    return;
                }
                std::thread::sleep(Duration::from_millis(1));
            }
        });

        motor
            .ensure_control_mode(ControlMode::PosVel, Duration::from_millis(20))
            .expect("ensure should switch to pos_vel");
        handle.join().expect("responder thread");

        let sent = bus_impl.sent.lock().expect("sent lock");
        let pos_read_idx = sent
            .iter()
            .position(|f| f.data == encode_register_read_cmd(0x01, 80))
            .expect("position read should be sent");
        let mode_write_idx = sent
            .iter()
            .position(|f| f.data == encode_register_write_cmd(0x01, 10, 2u32.to_le_bytes()))
            .expect("mode write should be sent");
        assert!(
            pos_read_idx < mode_write_idx,
            "position read should happen before mode write"
        );
    }

    #[test]
    fn ensure_control_mode_writes_when_initial_read_times_out() {
        let bus_impl = Arc::new(MockBus::new());
        let bus: Arc<dyn CanBus> = bus_impl.clone();
        let motor = Arc::new(DamiaoMotor::new(0x01, 0x11, "4340P", bus).expect("create motor"));
        let responder = Arc::clone(&motor);
        let bus_for_thread = Arc::clone(&bus_impl);

        let handle = std::thread::spawn(move || {
            let deadline = Instant::now() + Duration::from_millis(100);
            let mut replied_mode_ack = false;
            loop {
                let should_reply = {
                    let sent = bus_for_thread.sent.lock().expect("sent lock");
                    let saw_mode_write = sent
                        .iter()
                        .any(|f| f.data == encode_register_write_cmd(0x01, 10, 2u32.to_le_bytes()));
                    let mode_read_count = sent
                        .iter()
                        .filter(|f| f.data == encode_register_read_cmd(0x01, 10))
                        .count();
                    (saw_mode_write, mode_read_count)
                };
                if should_reply.0 && !replied_mode_ack {
                    responder
                        .process_feedback_frame_impl(CanFrame {
                            arbitration_id: 0x11,
                            data: [0x01, 0x01, 0x55, 10, 2, 0, 0, 0],
                            dlc: 8,
                            is_extended: false,
                            is_rx: true,
                        })
                        .expect("process write ack");
                    replied_mode_ack = true;
                }
                if should_reply.0 && should_reply.1 >= 2 {
                    responder
                        .process_feedback_frame_impl(CanFrame {
                            arbitration_id: 0x11,
                            data: [0x01, 0x01, 0x33, 10, 2, 0, 0, 0],
                            dlc: 8,
                            is_extended: false,
                            is_rx: true,
                        })
                        .expect("process register reply");
                    return;
                }
                if Instant::now() >= deadline {
                    return;
                }
                std::thread::sleep(Duration::from_millis(1));
            }
        });

        motor
            .ensure_control_mode(ControlMode::PosVel, Duration::from_millis(40))
            .expect("ensure should recover after initial read timeout within shared budget");
        handle.join().expect("responder thread");

        let sent = bus_impl.sent.lock().expect("sent lock");
        assert!(sent
            .iter()
            .any(|f| f.data == encode_register_write_cmd(0x01, 10, 2u32.to_le_bytes())));
    }

    #[test]
    fn ensure_control_mode_uses_shared_timeout_budget_and_reads_hold_position_once() {
        let bus_impl = Arc::new(MockBus::new());
        let bus: Arc<dyn CanBus> = bus_impl.clone();
        let motor = DamiaoMotor::new(0x01, 0x11, "4340P", bus).expect("create motor");

        let started = Instant::now();
        let err = motor
            .ensure_control_mode(ControlMode::PosVel, Duration::from_millis(180))
            .expect_err("verify timeout expected");
        let elapsed = started.elapsed();

        assert!(matches!(err, MotorError::Timeout(_)));
        assert!(
            elapsed < Duration::from_millis(600),
            "ensure_mode should use one total budget, elapsed={elapsed:?}"
        );

        let sent = bus_impl.sent.lock().expect("sent lock");
        let hold_reads = sent
            .iter()
            .filter(|f| f.data == encode_register_read_cmd(0x01, 80))
            .count();
        let mode_writes = sent
            .iter()
            .filter(|f| f.data == encode_register_write_cmd(0x01, 10, 2u32.to_le_bytes()))
            .count();
        assert_eq!(hold_reads, 1, "hold position should be read at most once");
        assert_eq!(
            mode_writes, ENSURE_MODE_VERIFY_ATTEMPTS,
            "mode write should still retry up to verify attempts"
        );
    }

    #[test]
    fn set_zero_requires_disable_first() {
        let bus: Arc<dyn CanBus> = Arc::new(MockBus::new());
        let motor = DamiaoMotor::new(0x01, 0x11, "4340P", bus).expect("create motor");

        motor.enable().expect("enable");
        let err = motor
            .set_zero_position()
            .expect_err("set_zero must fail when motor is not disabled");
        assert!(matches!(err, MotorError::InvalidArgument(_)));
    }

    #[test]
    fn set_zero_sends_command_after_disable() {
        let bus_impl = Arc::new(MockBus::new());
        let bus: Arc<dyn CanBus> = bus_impl.clone();
        let motor = DamiaoMotor::new(0x04, 0x14, "4310", bus).expect("create motor");

        motor.disable().expect("disable");
        motor.set_zero_position().expect("set_zero");

        let sent = bus_impl.sent.lock().expect("sent lock");
        let has_set_zero = sent.iter().any(|f| {
            f.arbitration_id == 0x04 && f.data == [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFE]
        });
        assert!(has_set_zero, "set_zero command frame should be sent");
    }

    #[test]
    fn store_parameters_sends_broadcast_store_frame() {
        let bus_impl = Arc::new(MockBus::new());
        let bus: Arc<dyn CanBus> = bus_impl.clone();
        let motor = DamiaoMotor::new(0x04, 0x14, "4310", bus).expect("create motor");

        motor.store_parameters().expect("store parameters");

        let sent = bus_impl.sent.lock().expect("sent lock");
        let has_store = sent
            .iter()
            .any(|f| f.arbitration_id == 0x7FF && f.data == encode_store_params_cmd(0x04));
        assert!(has_store, "store_parameters command frame should be sent");
    }

    #[test]
    fn store_parameters_disables_motor_before_store_without_reenabling() {
        let bus_impl = Arc::new(MockBus::new());
        let bus: Arc<dyn CanBus> = bus_impl.clone();
        let motor = DamiaoMotor::new(0x04, 0x14, "4310", bus).expect("create motor");

        motor.enable().expect("enable");
        motor.store_parameters().expect("store parameters");

        let sent = bus_impl.sent.lock().expect("sent lock");
        let disable_idx = sent
            .iter()
            .position(|f| f.arbitration_id == 0x04 && f.data == encode_disable_cmd())
            .expect("disable should be sent before store");
        let store_idx = sent
            .iter()
            .position(|f| f.arbitration_id == 0x7FF && f.data == encode_store_params_cmd(0x04))
            .expect("store should be sent");
        let enable_after_store = sent
            .iter()
            .skip(store_idx + 1)
            .any(|f| f.arbitration_id == 0x04 && f.data == encode_enable_cmd());
        assert!(
            disable_idx < store_idx,
            "disable should happen before store"
        );
        assert!(!enable_after_store, "store should not re-enable motor");
    }

    #[test]
    fn store_parameters_skips_disable_when_feedback_reports_disabled() {
        let bus_impl = Arc::new(MockBus::new());
        let bus: Arc<dyn CanBus> = bus_impl.clone();
        let motor = Arc::new(DamiaoMotor::new(0x04, 0x14, "4310", bus).expect("create motor"));
        let responder = Arc::clone(&motor);
        let bus_for_thread = Arc::clone(&bus_impl);

        let handle = std::thread::spawn(move || {
            let deadline = Instant::now() + Duration::from_millis(120);
            loop {
                let saw_feedback_request = {
                    let sent = bus_for_thread.sent.lock().expect("sent lock");
                    sent.iter().any(|f| {
                        f.arbitration_id == 0x7FF && f.data == encode_feedback_request_cmd(0x04)
                    })
                };
                if saw_feedback_request {
                    responder
                        .process_feedback_frame_impl(CanFrame {
                            arbitration_id: 0x14,
                            data: [0x04, 0, 0, 0, 0, 0, 0, 0],
                            dlc: 8,
                            is_extended: false,
                            is_rx: true,
                        })
                        .expect("process disabled feedback");
                    return;
                }
                if Instant::now() >= deadline {
                    return;
                }
                std::thread::sleep(Duration::from_millis(1));
            }
        });

        motor.store_parameters().expect("store parameters");
        handle.join().expect("responder thread");

        let sent = bus_impl.sent.lock().expect("sent lock");
        let has_disable = sent
            .iter()
            .any(|f| f.arbitration_id == 0x04 && f.data == encode_disable_cmd());
        let has_store = sent
            .iter()
            .any(|f| f.arbitration_id == 0x7FF && f.data == encode_store_params_cmd(0x04));
        assert!(
            !has_disable,
            "disable should be skipped when feedback already says disabled"
        );
        assert!(has_store, "store should still be sent");
    }

    #[test]
    fn write_register_u32_retries_until_write_ack_arrives() {
        let bus_impl = Arc::new(MockBus::new());
        let bus: Arc<dyn CanBus> = bus_impl.clone();
        let motor = Arc::new(DamiaoMotor::new(0x01, 0x11, "4340P", bus).expect("create motor"));
        let responder = Arc::clone(&motor);
        let bus_for_thread = Arc::clone(&bus_impl);

        let handle = std::thread::spawn(move || {
            let deadline = Instant::now() + Duration::from_millis(200);
            loop {
                let write_count = {
                    let sent = bus_for_thread.sent.lock().expect("sent lock");
                    sent.iter()
                        .filter(|f| {
                            f.data == encode_register_write_cmd(0x01, 10, 4u32.to_le_bytes())
                        })
                        .count()
                };
                if write_count >= 2 {
                    responder
                        .process_feedback_frame_impl(CanFrame {
                            arbitration_id: 0x11,
                            data: [0x01, 0x01, 0x55, 10, 4, 0, 0, 0],
                            dlc: 8,
                            is_extended: false,
                            is_rx: true,
                        })
                        .expect("process write ack");
                    return;
                }
                if Instant::now() >= deadline {
                    return;
                }
                std::thread::sleep(Duration::from_millis(1));
            }
        });

        motor
            .write_register_u32(10, 4)
            .expect("write should retry until ack arrives");
        handle.join().expect("responder thread");

        let sent = bus_impl.sent.lock().expect("sent lock");
        let write_count = sent
            .iter()
            .filter(|f| f.data == encode_register_write_cmd(0x01, 10, 4u32.to_le_bytes()))
            .count();
        assert!(write_count >= 2, "write should retry before ack arrives");
    }

    #[test]
    fn ensure_control_mode_seeds_force_pos_after_switch() {
        let bus_impl = Arc::new(MockBus::new());
        let bus: Arc<dyn CanBus> = bus_impl.clone();
        let motor = Arc::new(DamiaoMotor::new(0x01, 0x11, "4340P", bus).expect("create motor"));
        let responder = Arc::clone(&motor);
        let bus_for_thread = Arc::clone(&bus_impl);

        let position = 1.5f32;
        let handle = std::thread::spawn(move || {
            let deadline = Instant::now() + Duration::from_millis(120);
            let mut replied_position = false;
            let mut replied_mode_ack = false;
            loop {
                let (saw_position_read, saw_mode_write, mode_read_count) = {
                    let sent = bus_for_thread.sent.lock().expect("sent lock");
                    (
                        sent.iter()
                            .any(|f| f.data == encode_register_read_cmd(0x01, 80)),
                        sent.iter().any(|f| {
                            f.data == encode_register_write_cmd(0x01, 10, 4u32.to_le_bytes())
                        }),
                        sent.iter()
                            .filter(|f| f.data == encode_register_read_cmd(0x01, 10))
                            .count(),
                    )
                };

                if saw_position_read && !replied_position {
                    responder
                        .process_feedback_frame_impl(CanFrame {
                            arbitration_id: 0x11,
                            data: [
                                0x01,
                                0x01,
                                0x33,
                                80,
                                position.to_le_bytes()[0],
                                position.to_le_bytes()[1],
                                position.to_le_bytes()[2],
                                position.to_le_bytes()[3],
                            ],
                            dlc: 8,
                            is_extended: false,
                            is_rx: true,
                        })
                        .expect("process position reply");
                    replied_position = true;
                }

                if saw_mode_write && !replied_mode_ack {
                    responder
                        .process_feedback_frame_impl(CanFrame {
                            arbitration_id: 0x11,
                            data: [0x01, 0x01, 0x55, 10, 4, 0, 0, 0],
                            dlc: 8,
                            is_extended: false,
                            is_rx: true,
                        })
                        .expect("process mode write ack");
                    replied_mode_ack = true;
                }

                if saw_mode_write && mode_read_count >= 2 {
                    responder
                        .process_feedback_frame_impl(CanFrame {
                            arbitration_id: 0x11,
                            data: [0x01, 0x01, 0x33, 10, 4, 0, 0, 0],
                            dlc: 8,
                            is_extended: false,
                            is_rx: true,
                        })
                        .expect("process mode reply");
                    return;
                }
                if Instant::now() >= deadline {
                    return;
                }
                std::thread::sleep(Duration::from_millis(1));
            }
        });

        motor
            .ensure_control_mode(ControlMode::ForcePos, Duration::from_millis(20))
            .expect("ensure should switch to force_pos");
        handle.join().expect("responder thread");

        let sent = bus_impl.sent.lock().expect("sent lock");
        let mode_write_idx = sent
            .iter()
            .position(|f| f.data == encode_register_write_cmd(0x01, 10, 4u32.to_le_bytes()))
            .expect("mode write should be sent");
        let hold_idx = sent
            .iter()
            .enumerate()
            .find(|(idx, f)| {
                *idx > mode_write_idx
                    && f.arbitration_id == 0x301
                    && f.data == encode_force_pos_cmd(position, 0.0, 0.0)
            })
            .map(|(idx, _)| idx)
            .expect("force_pos hold command should be sent after mode write");
        assert!(
            mode_write_idx < hold_idx,
            "force_pos hold should happen after mode write"
        );
    }

    #[test]
    fn register_type_errors_name_expected_type() {
        let bus: Arc<dyn CanBus> = Arc::new(MockBus::new());
        let motor = DamiaoMotor::new(0x01, 0x11, "4340P", bus).expect("create motor");

        let f32_err = motor
            .write_register_f32(10, 1.0)
            .expect_err("u32 register should reject f32 write");
        assert!(
            f32_err.to_string().contains("expects float"),
            "unexpected error: {f32_err}"
        );

        let u32_err = motor
            .write_register_u32(22, 1)
            .expect_err("float register should reject u32 write");
        assert!(
            u32_err.to_string().contains("expects uint32"),
            "unexpected error: {u32_err}"
        );
    }
}
