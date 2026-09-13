use std::{ffi::c_void, mem, net::UdpSocket, path::PathBuf};

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
}

impl Config {
    fn default_udp_port() -> u16 {
        27172
    }

    // loads the yaml config, falling back to defaults if something goes awry
    fn load(path: &std::path::Path) -> Self {
        std::fs::read_to_string(path)
            .ok()
            .and_then(|text| serde_yaml::from_str(&text).ok())
            .unwrap_or(Config { udp_port: Self::default_udp_port(), game_object_id: 0 })
    }
}

// binds a socket to listen for trigger datagrams on the configured port
fn listen(port: u16) -> std::io::Result<UdpSocket> {
    UdpSocket::bind(("0.0.0.0", port))
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
    let tracker = Tracker::load_from_dir(&dir, config.game_object_id);

    let Ok(socket) = listen(config.udp_port) else { return };
    let mut trigger_buf = [0u8; 512];

    loop {
        // block until a trigger arrives, then reply to its sender
        let Ok((_, sender)) = socket.recv_from(&mut trigger_buf) else { continue };
        let payload = tracker.query_gamesyncs();
        let _ = socket.send_to(payload.as_bytes(), sender);
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