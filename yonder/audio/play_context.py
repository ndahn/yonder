from __future__ import annotations
from typing import TYPE_CHECKING
from pathlib import Path
from dataclasses import dataclass, field

from yonder.enums import PropID, AttenuationProperty
from yonder.util import get_temp_dir
from yonder.wem import wem2wav

if TYPE_CHECKING:
    from yonder.types import Attenuation, HIRCNode, Soundbank


@dataclass
class PlayContext:
    bank: Soundbank
    vgmstream_exe: Path = None
    wem_search_paths: list[Path] = field(default_factory=list)

    properties: dict[PropID, float] = field(default_factory=dict)
    rtpc_x: dict[int, float] = field(default_factory=dict)
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
                raise ValueError(f"Could not locate wem for {source_id}")

            wav = wem2wav(self.vgmstream_exe, wem, tmp)[0]

        return wav

    def _merge_property(self, prop: PropID, value: float) -> float:
        if prop.is_accum_additive():
            return self.properties.get(prop, 0.0) + value

        return value

    def update_properties(
        self,
        *,
        properties: dict[PropID, float] = None,
        rtpc_y: dict[int, float] = None,
    ) -> None:
        if properties:
            for prop, val in properties.items():
                self.properties[prop] = self._merge_property(prop, val)

        if rtpc_y:
            from yonder.game import get_selected_game

            RtpcParams = get_selected_game().rtpc_params

            for param, val in rtpc_y.items():
                param_enum = RtpcParams(param)
                try:
                    prop = PropID[param_enum.name]
                    self.properties[prop] = self._merge_property(prop, val)
                except KeyError:
                    continue

    def merge(self, node: HIRCNode | PlayContext) -> PlayContext:
        from yonder.types.hirc_node import HIRCNode
        from yonder.types.mixins import PropertyMixin, RtpcMixin

        ctx = PlayContext(
            bank=self.bank,
            vgmstream_exe=self.vgmstream_exe,
            wem_search_paths=self.wem_search_paths,
            properties=dict(self.properties),
            # NOTE RTPCs and States are global and do not need to be copied,
            # we just track their values
            rtpc_x=self.rtpc_x,
            states=self.states,
            distance=self.distance,
            angle=self.angle,
        )

        if isinstance(node, HIRCNode):
            if isinstance(node, PropertyMixin):
                ctx.update_properties(
                    properties={p.prop_enum: p.value for p in node.properties}
                )

            # In wwise, each node can modify properties via rtpcs, which can easily lead to
            # unintended stacking of adjustments
            if isinstance(node, RtpcMixin):
                rtpc_y = node.get_rtpc_y_values(self.rtpc_x)
                ctx.update_properties(rtpc_y=rtpc_y)

            # TODO apply default states?

        elif isinstance(node, PlayContext):
            if self.bank != node.bank:
                raise ValueError("Cannot merge play contexts with different banks")

            # NOTE no rtpc game syncs to run our rtpc state through
            ctx.update_properties(properties=node.properties)
            ctx.rtpc_x |= node.rtpc_x
            ctx.states |= node.states

        else:
            raise TypeError(f"Invalid merge object {node}")

        return ctx

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
