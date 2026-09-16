use std::{collections::HashMap, fs, path::Path};
use std::path::PathBuf;

use crate::{fnv1a_lowercase, state};

pub struct Tracker {
    game_object_id: u64,
    rtpcs: Vec<u32>,
    states: Vec<u32>,
    switches: Vec<u32>,
}

#[derive(serde::Deserialize)]
struct GameSyncs {
    #[serde(default)]
    rtpcs: Vec<String>,
    #[serde(default)]
    states: Vec<String>,
    #[serde(default)]
    switches: Vec<String>,
}

impl Tracker {
    /// load the tracker with the first yaml file in dir starting with "gamesyncs"
    pub fn load_from_dir(dir: &Path, game_object_id: u64) -> Self {
        let Some(path) = Self::find_gamesyncs_file(dir) else {
            return Self {
                game_object_id,
                rtpcs: Vec::new(),
                states: Vec::new(),
                switches: Vec::new(),
            };
        };

        Self::load(&path, game_object_id)
    }

    // finds the first "gamesyncs*.yaml"/"gamesyncs*.yml" file in a directory
    fn find_gamesyncs_file(dir: &Path) -> Option<PathBuf> {
        let entries = fs::read_dir(dir).ok()?;

        entries
            .filter_map(|entry| entry.ok())
            .map(|entry| entry.path())
            .find(|path| {
                let is_yaml = matches!(
                    path.extension().and_then(|ext| ext.to_str()),
                    Some("yaml") | Some("yml")
                );
                let starts_with_gamesyncs = path
                    .file_stem()
                    .and_then(|stem| stem.to_str())
                    .is_some_and(|stem| stem.starts_with("gamesyncs"));

                is_yaml && starts_with_gamesyncs
            })
    }

    // reads the game syncs file, one `kind:name` entry per line.
    // Kind is rtpc, state, or switch.
    // Name my start with a # followed by a number to designate a raw hash.
    // Empty lines and lines starting with # are ignored.
    pub fn load(path: &Path, game_object_id: u64) -> Self {
        let mut tracker = Self {
            game_object_id,
            rtpcs: Vec::new(),
            states: Vec::new(),
            switches: Vec::new(),
        };
        let Ok(text) = fs::read_to_string(path) else {
            return tracker;
        };

        let Ok(raw) = serde_yaml::from_str::<GameSyncs>(&text) else {
            return tracker;
        };

        // name is either an actual name or a hash starting with "#"
        let resolve = |name: &str| -> Option<u32> {
            let name = name.trim();
            match name.strip_prefix('#') {
                Some(hash) => hash.parse().ok(),
                None => Some(fnv1a_lowercase(name)),
            }
        };

        tracker.rtpcs = raw.rtpcs.iter().filter_map(|n| resolve(n)).collect();
        tracker.states = raw.states.iter().filter_map(|n| resolve(n)).collect();
        tracker.switches = raw.switches.iter().filter_map(|n| resolve(n)).collect();

        tracker
    }

    // queries every tracked sync and assembles a compact json blob
    pub fn query_gamesyncs(&self) -> String {
        let rtpcs: HashMap<_, _> = self
            .rtpcs
            .iter()
            // Could also pass -1 to ignore game-object-specific values
            .filter_map(|id| Some((id, state::get_rtpc(*id, self.game_object_id)?)))
            .collect();

        let states: HashMap<_, _> = self
            .states
            .iter()
            .filter_map(|id| Some((id, state::get_state(*id)?)))
            .collect();

        let switches: HashMap<_, _> = self
            .switches
            .iter()
            .filter_map(|id| Some((id, state::get_switch(*id, self.game_object_id)?)))
            .collect();

        serde_json::json!({ "game_objet_id": self.game_object_id, "rtpcs": rtpcs, "states": states, "switches": switches }).to_string()
    }
}
