use std::{ffi::c_void, mem, net::UdpSocket, path::PathBuf, time::Duration};

use serde::Deserialize;
use windows::{
    Win32::{
        Foundation::{HINSTANCE, HMODULE, MAX_PATH},
        System::{LibraryLoader::GetModuleFileNameW, SystemServices::DLL_PROCESS_ATTACH},
    },
    core::BOOL,
};

mod state;
mod tracker;

use tracker::Tracker;

const CONFIG_FILE: &str = "yonder_live_states.yaml";
const SYNCS_FILE: &str = "game_syncs.txt";

fn fnv1a_lowercase(bytes: impl AsRef<[u8]>) -> u32 {
    bytes.as_ref().iter().fold(2166136261, |hash, byte| {
        hash.wrapping_mul(16777619) ^ byte.to_ascii_lowercase() as u32
    })
}

#[derive(Deserialize)]
struct Config {
    #[serde(default = "Config::default_udp_port")]
    udp_port: u16,
    #[serde(default)]
    game_object_id: u64,
    #[serde(default = "Config::default_poll_time_ms")]
    poll_time_ms: u64,
}

impl Config {
    fn default_udp_port() -> u16 {
        27172
    }

    fn default_poll_time_ms() -> u64 {
        200
    }

    // loads the yaml config, falling back to defaults if something goes awry
    fn load(path: &std::path::Path) -> Self {
        std::fs::read_to_string(path)
            .ok()
            .and_then(|text| serde_yaml::from_str(&text).ok())
            .unwrap_or(Config { udp_port: Self::default_udp_port(), game_object_id: 0, poll_time_ms: Self::default_poll_time_ms() })
    }
}

// create the socket for sending off our collected states
fn connect(port: u16) -> std::io::Result<UdpSocket> {
    let socket = UdpSocket::bind("0.0.0.0:0")?;
    socket.connect(("127.0.0.1", port))?;
    Ok(socket)
}

// directory this dll was loaded from
fn dll_dir(hmodule: HMODULE) -> PathBuf {
    let mut buf = [0u16; MAX_PATH as usize];
    let len = unsafe { GetModuleFileNameW(Some(hmodule), &mut buf) } as usize;
    PathBuf::from(String::from_utf16_lossy(&buf[..len]))
        .parent()
        .map(|p| p.to_path_buf())
        .unwrap_or_default()
}

fn run(dir: PathBuf) {
    let config = Config::load(&dir.join(CONFIG_FILE));
    let tracker = Tracker::load(&dir.join(SYNCS_FILE), config.game_object_id);
    let poll_interval = Duration::from_millis(config.poll_time_ms);

    let Ok(socket) = connect(config.udp_port) else { return };

    loop {
        let payload = tracker.poll_json();
        let _ = socket.send(payload.as_bytes());
        std::thread::sleep(poll_interval);
    }
}

#[unsafe(no_mangle)]
unsafe extern "system" fn DllMain(hmodule: HINSTANCE, reason: u32, _: *mut c_void) -> BOOL {
    if reason == DLL_PROCESS_ATTACH {
        // HMODULE doesn't have Send, so we just pass the path to the run method
        let hmodule: HMODULE = unsafe { mem::transmute(hmodule) };
        let dir = dll_dir(hmodule);
        std::thread::spawn(move || run(dir));
    }
 
    true.into()
}