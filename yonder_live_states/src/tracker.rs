use std::{collections::HashMap, fs, path::Path};

use crate::{fnv1a_lowercase, state};

pub struct Tracker {
    game_object_id: u64,
    rtpcs: Vec<u32>,
    states: Vec<u32>,
    switches: Vec<u32>,
}

impl Tracker {
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

        for line in text.lines() {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }

            let Some((kind, name)) = line.split_once(':') else {
                continue;
            };
            let name = name.trim();
            let id = match name.strip_prefix('#') {
                Some(hash) => match hash.parse() {
                    Ok(id) => id,
                    Err(_) => continue,
                },
                None => fnv1a_lowercase(name),
            };

            match kind.trim() {
                "rtpc" => tracker.rtpcs.push(id),
                "state" => tracker.states.push(id),
                "switch" => tracker.switches.push(id),
                _ => {} // ignore malformed lines
            }
        }

        tracker
    }

    // queries every tracked sync and assembles a compact json blob
    pub fn poll_json(&self) -> String {
        let rtpc: HashMap<_, _> = self
            .rtpcs
            .iter()
            .filter_map(|id| Some((id, state::get_rtpc(*id, self.game_object_id)?)))
            .collect();

        let state: HashMap<_, _> = self
            .states
            .iter()
            .filter_map(|id| Some((id, state::get_state(*id)?)))
            .collect();

        let switch: HashMap<_, _> = self
            .switches
            .iter()
            .filter_map(|id| Some((id, state::get_switch(*id, self.game_object_id)?)))
            .collect();

        serde_json::json!({ "game_objet_id": self.game_object_id, "rtpc": rtpc, "state": state, "switch": switch }).to_string()
    }
}
