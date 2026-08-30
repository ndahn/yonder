from __future__ import annotations
from typing import TYPE_CHECKING
from pathlib import Path
from dataclasses import dataclass, field

from yonder.types.mixins import PropertyMixin, RtpcMixin
from yonder.enums import PropID, AttenuationProperty
from yonder.util import get_temp_dir, logger
from yonder.wem import wem2wav

if TYPE_CHECKING:
    from yonder.types import Attenuation, HIRCNode, Soundbank


@dataclass
class PlayContext:
    bank: Soundbank
    vgmstream_exe: Path = None
    wem_search_paths: list[Path] = field(default_factory=list)

    properties: dict[PropID, float] = field(default_factory=dict)
    rtpcs: dict[int, float] = field(default_factory=dict)
    states: dict[int, int] = field(default_factory=dict)
    distance: float = 0.0
    angle: float = 0.0

    @property
    def attenuation(self) -> Attenuation:
        nid = int(self.properties.get(PropID.AttenuationID, 0))
        return self.bank.get(nid)

    def get_wav_for_source(self, source_id: int) -> Path:
        tmp = get_temp_dir()
        wav = tmp / f"{source_id}.wav"

        if not wav.is_file():
            wem = self.bank.get_wem_path(source_id, search_paths=self.wem_search_paths)
            if not wem:
                logger.warning(f"Could not locate wem for {source_id}")
                return None

            wav = wem2wav(self.vgmstream_exe, wem, tmp)[0]

        return wav

    def merge(self, node: HIRCNode | PlayContext) -> PlayContext:
        from yonder.types.hirc_node import HIRCNode
        from yonder.game import get_selected_game

        properties = dict(self.properties)

        # RTPCs and States are global and do not need to be copied, we just track their values
        rtpcs = self.rtpcs
        states = self.states

        def merge_properties(prop: PropID, val: float) -> None:
            if prop.is_accumulating():
                properties.setdefault(prop, 0.0)
                properties[prop] += prop.value
            else:
                properties[prop] = prop.value

        if isinstance(node, HIRCNode):
            if isinstance(node, PropertyMixin):
                for prop in node.properties:
                    merge_properties(prop.prop_enum, prop.value)

            # In wwise, each node can modify the property via rtpc, which can easily lead to
            # unintended stacking of adjustments
            if isinstance(node, RtpcMixin):
                rtpc_values = node.get_rtpc_values(self.rtpcs)
                RtpcParams = get_selected_game().rtpc_params

                for param, val in rtpc_values.items():
                    param_enum = RtpcParams(param)
                    try:
                        prop = PropID[param_enum.name]
                        merge_properties(prop, val)
                    except KeyError:
                        continue

        elif isinstance(node, PlayContext):
            if self.bank != node.bank:
                raise ValueError("Cannot merge play contexts with different banks")

            for prop, val in node.properties.items():
                merge_properties(prop, val)

            rtpcs |= node.rtpcs
            states |= node.states

        else:
            raise TypeError(f"Invalid merge object {node}")

        return PlayContext(
            bank=self.bank,
            vgmstream_exe=self.vgmstream_exe,
            wem_search_paths=self.wem_search_paths,
            properties=properties,
            rtpcs=rtpcs,
            states=states,
            distance=self.distance,
            angle=self.angle,
        )

    def get_effective_volume(self) -> float:
        vol = self.properties.get(PropID.Volume, 0.0)

        att = self.attenuation
        if att:
            vol += att.get_attenuated_value(
                AttenuationProperty.Volume, self.distance, self.angle
            )

        # In DB
        return vol

    def get_effective_hpf(self) -> float:
        hpf = self.properties.get(PropID.HPF, 0.0)

        att = self.attenuation
        if att:
            hpf += att.get_attenuated_value(
                AttenuationProperty.HPF, self.distance, self.angle
            )

        # In cents
        return max(0.0, min(100.0, hpf))

    def get_effective_lpf(self) -> float:
        lpf = self.properties.get(PropID.LPF, 0.0)

        att = self.attenuation
        if att:
            lpf += att.get_attenuated_value(
                AttenuationProperty.LPF, self.distance, self.angle
            )

        # In cents
        return max(0.0, min(100.0, lpf))
